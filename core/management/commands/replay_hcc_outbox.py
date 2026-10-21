"""
Comando para reintentar el despacho de eventos PENDING en el outbox de HCC.
Diseñado para ejecutarse periódicamente mediante cron cPanel en HostGator.
Reintenta eventos ya existentes; NUNCA crea eventos nuevos.
"""

from django.core.management.base import BaseCommand
from core.models import HCCOutboxEvent, HCCOutboxStatus
from core.services.hcc_service import dispatch_outbox_event


class Command(BaseCommand):
    help = 'Reintenta el envío de eventos HCCOutboxEvent con estado PENDING hacia HCC v0.1.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=20,
            help='Número máximo de eventos a procesar en esta ejecución (default: 20).'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra los eventos pendientes sin realizar llamadas HTTP.'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        dry_run = options['dry_run']

        pendientes = list(
            HCCOutboxEvent.objects.filter(status=HCCOutboxStatus.PENDING).order_by('created_at')[:limit]
        )

        total = len(pendientes)
        self.stdout.write(self.style.NOTICE(f"[REPLAY OUTBOX] Encontrados {total} eventos PENDING (límite: {limit})."))

        if total == 0:
            self.stdout.write(self.style.SUCCESS("No hay eventos pendientes de sincronización."))
            return

        if dry_run:
            for ev in pendientes:
                self.stdout.write(f"[DRY-RUN] Pendiente: {ev.event_id} (Tipo: {ev.event_type}, Intentos: {ev.attempts})")
            return

        exitos = 0
        fallas = 0

        for ev in pendientes:
            self.stdout.write(f"Despachando {ev.event_id} (intento #{ev.attempts + 1})...")
            res = dispatch_outbox_event(ev)
            if res.get('success'):
                exitos += 1
                self.stdout.write(self.style.SUCCESS(f"  ✓ Entregado exitosamente (HTTP {res.get('status_code')})."))
            else:
                fallas += 1
                err_type = 'PERMANENTE (ERROR)' if res.get('is_permanent') else 'TRANSITORIO (PENDING)'
                self.stdout.write(self.style.WARNING(f"  ✗ Falló: {res.get('error')} [{err_type}]"))

        self.stdout.write(self.style.SUCCESS(
            f"[REPLAY OUTBOX COMPLETADO] Total: {total} | Éxitos: {exitos} | Reintentos pendientes/fallas: {fallas}"
        ))
