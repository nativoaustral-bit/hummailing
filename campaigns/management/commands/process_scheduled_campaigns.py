import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from campaigns.models import CampaignSchedule, Campaign
from campaigns.tasks import send_campaign_task

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Procesa y despacha las campañas programadas cuya fecha y hora ya se ha cumplido.'

    def handle(self, *args, **options):
        now = timezone.now()
        pending_schedules = CampaignSchedule.objects.filter(
            status='pending',
            scheduled_at__lte=now
        ).select_related('campaign', 'campaign__organization')

        count = pending_schedules.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] No hay envíos programados pendientes."))
            return

        self.stdout.write(self.style.NOTICE(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Procesando {count} envío(s) programado(s)..."))

        for schedule in pending_schedules:
            campaign = schedule.campaign
            self.stdout.write(f" -> Despachando Campaña ID={campaign.id} ('{campaign.name}') programada para {schedule.scheduled_at}...")

            schedule.status = 'processing'
            schedule.save(update_fields=['status'])

            try:
                # Ejecutar el despacho de la campaña
                send_campaign_task(campaign.id)

                schedule.status = 'completed'
                schedule.sent_at = timezone.now()
                schedule.save(update_fields=['status', 'sent_at'])

                # Verificar si quedan más programaciones pendientes para esta campaña
                has_more_pending = CampaignSchedule.objects.filter(
                    campaign=campaign,
                    status='pending'
                ).exists()

                if not has_more_pending:
                    campaign.status = 'sent'
                    campaign.save(update_fields=['status'])

                self.stdout.write(self.style.SUCCESS(f"    ✓ Completado con éxito (Schedule ID={schedule.id})."))
            except Exception as e:
                schedule.status = 'failed'
                schedule.save(update_fields=['status'])
                logger.error(f"Error al procesar schedule {schedule.id}: {e}")
                self.stdout.write(self.style.ERROR(f"    ✗ Error: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Procesamiento finalizado."))
