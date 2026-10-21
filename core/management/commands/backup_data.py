import os
import sys
import json
import time
import shutil
import tarfile
import zipfile
import sqlite3
import hashlib
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model
from organizations.models import Organization, SuppressionEntry, ActivityLog
from contacts.models import Contact, Tag, Segment
from campaigns.models import Campaign, CampaignLink, TrackingEvent
from opportunities.models import Opportunity
from core.models import Lead

User = get_user_model()

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

class Command(BaseCommand):
    help = "Genera un backup consistente de la base de datos SQLite y del directorio media/ con checksums y manifiesto."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dest',
            type=str,
            help='Directorio de destino para almacenar el backup empaquetado (por defecto en ubicación privada fuera de webroot)'
        )
        parser.add_argument(
            '--keep-days',
            type=int,
            default=14,
            help='Días de retención para rotar backups antiguos (por defecto 14 días)'
        )
        parser.add_argument(
            '--offsite-dest',
            type=str,
            help='Directorio o ruta off-site donde sincronizar una copia adicional'
        )

    def handle(self, *args, **options):
        start_time = time.time()
        timestamp_str = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        
        # 1. Definir directorio de destino fuera del DocumentRoot
        if options.get('dest'):
            backup_dir = Path(options['dest'])
        else:
            private_home = Path.home() / 'private' / 'hummailing_backups'
            if private_home.parent.exists():
                backup_dir = private_home
            else:
                backup_dir = settings.BASE_DIR / 'backups' / 'automated'
        
        backup_dir.mkdir(parents=True, exist_ok=True)
        temp_work_dir = backup_dir / f"tmp_{timestamp_str}"
        temp_work_dir.mkdir(parents=True, exist_ok=True)

        try:
            self.stdout.write(f"Iniciando backup consistente Hummailing [{timestamp_str}]...")

            from django.db import connection
            backup_db_file = temp_work_dir / 'db.sqlite3'
            db_name = str(connection.settings_dict.get('NAME') or settings.DATABASES['default']['NAME'])
            self.stdout.write(f"Respaldando base de datos activa ({db_name})...")

            connection.ensure_connection()
            if 'memory' in db_name or ':memory:' in db_name:
                dump = '\n'.join(connection.connection.iterdump())
                dst_conn = sqlite3.connect(backup_db_file)
                dst_conn.executescript(dump)
                dst_conn.close()
            else:
                src_conn = sqlite3.connect(f"file:{os.path.abspath(db_name)}?mode=ro", uri=True)
                dst_conn = sqlite3.connect(backup_db_file)
                src_conn.backup(dst_conn)
                dst_conn.close()
                src_conn.close()

            # Comprobar integridad del backup SQLite generado
            chk_conn = sqlite3.connect(backup_db_file)
            integrity_result = chk_conn.execute("PRAGMA integrity_check;").fetchone()[0]
            chk_conn.close()
            if integrity_result != 'ok':
                raise RuntimeError(f"Fallo de integridad en el backup SQLite: {integrity_result}")

            db_hash = sha256_file(backup_db_file)
            db_size = backup_db_file.stat().st_size

            # 2. Respaldo comprimido del directorio media/
            media_dir = Path(settings.MEDIA_ROOT)
            media_tar_file = temp_work_dir / 'media.tar.gz'
            media_files_count = 0
            
            self.stdout.write(f"Respaldando archivos multimedia ({media_dir})...")
            if media_dir.exists():
                with tarfile.open(media_tar_file, "w:gz") as tar:
                    for root, dirs, files in os.walk(media_dir):
                        for file in files:
                            full_path = os.path.join(root, file)
                            rel_path = os.path.relpath(full_path, media_dir)
                            tar.add(full_path, arcname=rel_path)
                            media_files_count += 1
            else:
                with tarfile.open(media_tar_file, "w:gz") as tar:
                    pass

            media_hash = sha256_file(media_tar_file)
            media_size = media_tar_file.stat().st_size

            # 3. Generar Manifiesto de Integridad con conteos de registros
            user_count = User.objects.count()
            org_count = Organization.objects.count()
            contact_count = Contact.objects.count()
            tag_count = Tag.objects.count()
            campaign_count = Campaign.objects.count()
            opportunity_count = Opportunity.objects.count()
            lead_count = Lead.objects.count()
            suppression_count = SuppressionEntry.objects.count()

            manifest = {
                'timestamp': timestamp_str,
                'created_at': datetime.now().isoformat(),
                'version': 'HUMM-RELEASE-GATE-v2.1',
                'database': {
                    'engine': 'sqlite3',
                    'filename': 'db.sqlite3',
                    'size_bytes': db_size,
                    'sha256': db_hash,
                    'integrity': integrity_result,
                    'records': {
                        'users': user_count,
                        'organizations': org_count,
                        'contacts': contact_count,
                        'tags': tag_count,
                        'campaigns': campaign_count,
                        'opportunities': opportunity_count,
                        'leads': lead_count,
                        'suppressions': suppression_count,
                    }
                },
                'media': {
                    'filename': 'media.tar.gz',
                    'size_bytes': media_size,
                    'sha256': media_hash,
                    'files_count': media_files_count,
                }
            }

            manifest_file = temp_work_dir / 'manifest.json'
            with open(manifest_file, 'w', encoding='utf-8') as mf:
                json.dump(manifest, mf, indent=2, ensure_ascii=False)

            # 4. Empaquetar el archivo final ZIP
            final_zip_name = f"hummailing_backup_{timestamp_str}.zip"
            final_zip_path = backup_dir / final_zip_name

            with zipfile.ZipFile(final_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(backup_db_file, arcname='db.sqlite3')
                zf.write(media_tar_file, arcname='media.tar.gz')
                zf.write(manifest_file, arcname='manifest.json')

            final_hash = sha256_file(final_zip_path)
            duration = round(time.time() - start_time, 2)

            self.stdout.write(self.style.SUCCESS(
                f"\n=== BACKUP HUMMAILING COMPLETADO EXITOSAMENTE ({duration}s) ===\n"
                f"Archivo: {final_zip_path}\n"
                f"Tamaño: {final_zip_path.stat().st_size} bytes\n"
                f"SHA-256: {final_hash}\n"
                f"Registros: {user_count} users, {org_count} orgs, {contact_count} contacts, {campaign_count} campaigns\n"
                f"Archivos media: {media_files_count}"
            ))

            # 5. Copia off-site automática si está configurada
            offsite_dest = options.get('offsite_dest') or os.environ.get('OFFSITE_BACKUP_DEST')
            if offsite_dest:
                dest_str = str(offsite_dest)
                if ':' in dest_str and not Path(dest_str).is_absolute():
                    self.stdout.write(f"Sincronizando copia off-site remota vía rsync hacia {dest_str}...")
                    subprocess.run(['rsync', '-avz', str(final_zip_path), dest_str], check=True)
                    self.stdout.write(self.style.SUCCESS(f"✓ Copia off-site remota transferida a: {dest_str}"))
                else:
                    offsite_path = Path(dest_str)
                    offsite_path.mkdir(parents=True, exist_ok=True)
                    dest_file = offsite_path / final_zip_name
                    shutil.copy2(final_zip_path, dest_file)
                    
                    # Validación criptográfica inmediata del archivo transferido
                    transferred_sha = sha256_file(dest_file)
                    if transferred_sha != final_hash:
                        raise RuntimeError(f"Fallo de integridad en transferencia off-site: {transferred_sha} != {final_hash}")
                    self.stdout.write(self.style.SUCCESS(
                        f"✓ Copia off-site transferida y validada por SHA-256 ({transferred_sha[:16]}...) hacia: {dest_file}"
                    ))

            # 6. Rotación de backups antiguos (política de retención de 14 días)
            keep_days = options.get('keep_days', 14)
            cutoff_date = datetime.now() - timedelta(days=keep_days)
            for item in backup_dir.glob("hummailing_backup_*.zip"):
                try:
                    file_mtime = datetime.fromtimestamp(item.stat().st_mtime)
                    if file_mtime < cutoff_date:
                        item.unlink()
                        self.stdout.write(f"Backup antiguo rotado y eliminado: {item.name}")
                except Exception:
                    pass

            return str(final_zip_path)

        finally:
            if temp_work_dir.exists():
                shutil.rmtree(temp_work_dir, ignore_errors=True)
