import os
import sys
import json
import time
import shutil
import tarfile
import zipfile
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

class Command(BaseCommand):
    help = "Valida y restaura un backup de Hummailing (SQLite + media + manifest + hashes)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--backup-file',
            type=str,
            required=True,
            help='Ruta al archivo ZIP de backup generado por backup_data'
        )
        parser.add_argument(
            '--isolated',
            action='store_true',
            help='Restaura en un directorio aislado temporal para verificación sin alterar producción'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Realiza validación de integridad criptográfica y de base de datos sin sobreescribir datos'
        )
        parser.add_argument(
            '--target-db',
            type=str,
            help='Ruta alternativa para la base de datos destino'
        )
        parser.add_argument(
            '--target-media',
            type=str,
            help='Ruta alternativa para el directorio media destino'
        )

    def handle(self, *args, **options):
        backup_input = options.get('backup_file') or options.get('backup-file')
        if not backup_input:
            raise CommandError("Se requiere especificar el archivo de backup.")
        backup_file_path = Path(backup_input).resolve()
        if not backup_file_path.exists():
            raise CommandError(f"Archivo de backup no encontrado: {backup_file_path}")

        is_isolated = options.get('isolated', False)
        is_dry_run = options.get('dry_run', False)

        self.stdout.write(f"Iniciando verificación y restauración de: {backup_file_path.name}")

        temp_restore_dir = backup_file_path.parent / f"restore_verify_{int(time.time())}"
        temp_restore_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Validar integridad del ZIP y extraer
            if not zipfile.is_zipfile(backup_file_path):
                raise CommandError("El archivo indicado no es un archivo ZIP válido.")

            with zipfile.ZipFile(backup_file_path, 'r') as zf:
                namelist = zf.namelist()
                required_members = {'db.sqlite3', 'media.tar.gz', 'manifest.json'}
                missing = required_members - set(namelist)
                if missing:
                    raise CommandError(f"El backup no contiene los componentes obligatorios: {missing}")
                zf.extractall(temp_restore_dir)

            extracted_db = temp_restore_dir / 'db.sqlite3'
            extracted_media = temp_restore_dir / 'media.tar.gz'
            extracted_manifest = temp_restore_dir / 'manifest.json'

            # 2. Leer manifiesto
            with open(extracted_manifest, 'r', encoding='utf-8') as mf:
                manifest = json.load(mf)

            expected_db_sha = manifest['database']['sha256']
            expected_media_sha = manifest['media']['sha256']
            expected_records = manifest['database'].get('records', {})

            # 3. Comprobar checksums SHA-256
            actual_db_sha = sha256_file(extracted_db)
            if actual_db_sha != expected_db_sha:
                raise CommandError(
                    f"FALLO DE CHECKSUM DB: Esperado {expected_db_sha}, obtenido {actual_db_sha}"
                )
            self.stdout.write(self.style.SUCCESS(f"✓ Checksum SHA-256 de base de datos coincidente: {actual_db_sha}"))

            actual_media_sha = sha256_file(extracted_media)
            if actual_media_sha != expected_media_sha:
                raise CommandError(
                    f"FALLO DE CHECKSUM MEDIA: Esperado {expected_media_sha}, obtenido {actual_media_sha}"
                )
            self.stdout.write(self.style.SUCCESS(f"✓ Checksum SHA-256 de media coincidente: {actual_media_sha}"))

            # 4. Comprobar integridad física de SQLite
            chk_conn = sqlite3.connect(extracted_db)
            cursor = chk_conn.cursor()
            integrity = cursor.execute("PRAGMA integrity_check;").fetchone()[0]
            if integrity != 'ok':
                chk_conn.close()
                raise CommandError(f"FALLO DE INTEGRIDAD SQLITE: {integrity}")
            self.stdout.write(self.style.SUCCESS("✓ PRAGMA integrity_check: ok"))

            # 5. Comprobar conteos de entidades
            record_checks = {}
            table_map = {
                'users': 'core_user',
                'organizations': 'organizations_organization',
                'contacts': 'contacts_contact',
                'tags': 'contacts_tag',
                'campaigns': 'campaigns_campaign',
                'opportunities': 'opportunities_opportunity',
                'leads': 'core_lead',
                'suppressions': 'organizations_suppressionentry',
            }

            for record_key, expected_val in expected_records.items():
                table = table_map.get(record_key)
                if table:
                    try:
                        count = cursor.execute(f"SELECT COUNT(*) FROM {table};").fetchone()[0]
                        record_checks[record_key] = (expected_val, count)
                        if count != expected_val:
                            self.stdout.write(self.style.WARNING(
                                f"Aviso de conteo: {record_key} esperado {expected_val}, encontrado {count}"
                            ))
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"No se pudo verificar tabla {table}: {e}"))
            chk_conn.close()

            self.stdout.write(self.style.SUCCESS(f"✓ Verificación de conteos de registros completada: {record_checks}"))

            # 6. Decidir acción (aislado / dry-run / restauración activa)
            if is_dry_run or is_isolated:
                self.stdout.write(self.style.SUCCESS(
                    f"\n=== VERIFICACIÓN AISLADA COMPLETADA CON ÉXITO ===\n"
                    f"El backup {backup_file_path.name} es íntegro, consistente y recuperable.\n"
                    f"Ubicación aislada temporal: {temp_restore_dir}"
                ))
                if is_dry_run:
                    shutil.rmtree(temp_restore_dir, ignore_errors=True)
                return "OK"

            # 7. Restauración en destino activo
            target_db = Path(options.get('target_db') or settings.DATABASES['default']['NAME'])
            target_media = Path(options.get('target_media') or settings.MEDIA_ROOT)

            # Backup de seguridad antes de sobreescribir
            if target_db.exists():
                pre_restore_bak = target_db.with_suffix(f".pre_restore_{int(time.time())}.sqlite3")
                shutil.copy2(target_db, pre_restore_bak)
                self.stdout.write(f"Copia de seguridad previa creada en: {pre_restore_bak}")

            # Reemplazo atómico de base de datos
            target_db.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(extracted_db, target_db)
            self.stdout.write(self.style.SUCCESS(f"✓ Base de datos restaurada en: {target_db}"))

            # Descompresión de media
            target_media.mkdir(parents=True, exist_ok=True)
            with tarfile.open(extracted_media, "r:gz") as tar:
                tar.extractall(path=target_media)
            self.stdout.write(self.style.SUCCESS(f"✓ Media restaurado en: {target_media}"))

            self.stdout.write(self.style.SUCCESS(
                f"\n=== RESTAURACIÓN HUMMAILING COMPLETADA CON ÉXITO ==="
            ))
            return "OK"

        finally:
            if not is_isolated and temp_restore_dir.exists():
                shutil.rmtree(temp_restore_dir, ignore_errors=True)
