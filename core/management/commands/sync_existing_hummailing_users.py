"""
Comando de backfill controlado para sincronizar usuarios históricos de Hummailing hacia HCC.
Aplica exactamente la misma semántica de activación que producción:
- Requiere evidencia combinada: Campaign.status == 'sent' Y al menos un TrackingEvent(event_type='sent').
- Identifica únicamente al usuario con atribución personal fidedigna (campaign.created_by).
- NO asigna arbitrariamente campañas sin titular a un org_admin (registra SKIPPED_NO_RELIABLE_USER).
- Emite eventos con event_id determinista: hummailing-activation-user-{user_id}.
- Utiliza la fecha real de la primera campaña enviada (sent_at) como occurred_at.
- Soporta --dry-run obligatorio antes de ejecución en producción.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import User, HCCOutboxEvent, HCCOutboxStatus
from core.services.hcc_service import enqueue_tool_activation, dispatch_outbox_event
from campaigns.models import Campaign, TrackingEvent


class Command(BaseCommand):
    help = 'Descubre y encola activaciones históricas legítimas de usuarios de Hummailing hacia HCC.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula el proceso informando usuarios candidatos y omisiones sin escribir en DB ni llamar a HCC.'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Límite máximo de usuarios a procesar (default: 100).'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']

        self.stdout.write(self.style.NOTICE(
            f"=== BACKFILL HUMMAILING -> HCC (Dry-Run: {dry_run} | Límite: {limit}) ==="
        ))

        # 1. Auditar campañas que tienen evidencia real de envío exitoso
        sent_campaigns = Campaign.objects.filter(status='sent').order_by('sent_at', 'created_at')
        
        # Mapear campañas que realmente tuvieron entregas
        campaigns_with_sends = set(
            TrackingEvent.objects.filter(
                campaign__in=sent_campaigns,
                event_type='sent'
            ).values_list('campaign_id', flat=True).distinct()
        )

        candidates = []
        skipped = []

        # Evaluar usuarios activos
        users = User.objects.filter(is_active=True).order_by('id')[:limit]

        for user in users:
            event_id = f"hummailing-activation-user-{user.id}"
            already_synced = HCCOutboxEvent.objects.filter(event_id=event_id).exists()
            if already_synced:
                skipped.append((user, "ALREADY_SYNCED", f"Ya tiene evento outbox ({event_id})"))
                continue

            # Buscar la primera campaña legítima creada/operada por este usuario
            user_campaigns = sent_campaigns.filter(
                created_by=user,
                id__in=campaigns_with_sends
            )

            first_campaign = user_campaigns.first()

            if first_campaign:
                occurred_at = first_campaign.sent_at or first_campaign.created_at or timezone.now()
                candidates.append({
                    'user': user,
                    'campaign': first_campaign,
                    'occurred_at': occurred_at,
                    'event_id': event_id,
                })
            else:
                # Verificar si su organización tiene campañas pero no creadas por él
                if user.organization:
                    org_has_campaigns = sent_campaigns.filter(
                        organization=user.organization,
                        id__in=campaigns_with_sends
                    ).exists()
                    if org_has_campaigns:
                        skipped.append((user, "SKIPPED_NO_RELIABLE_USER", f"Org '{user.organization.name}' tiene campañas pero no atribuibles de forma fiable a este usuario"))
                        continue
                skipped.append((user, "NO_QUALIFYING_CAMPAIGNS", "Sin campañas enviadas con entregas registradas"))

        # Reporte de resultados
        self.stdout.write(self.style.NOTICE(f"Usuarios candidatos encontrados: {len(candidates)}"))
        self.stdout.write(self.style.NOTICE(f"Usuarios omitidos / no califican: {len(skipped)}"))

        if candidates:
            self.stdout.write(self.style.SUCCESS("--- CANDIDATOS PARA ACTIVACION ---"))
            for c in candidates:
                u = c['user']
                camp = c['campaign']
                occ = c['occurred_at']
                org_name = u.organization.name if u.organization else 'Sin Org'
                self.stdout.write(
                    f"[CANDIDATO] User ID={u.id} ({u.username}, {u.email}) | Org: {org_name} | "
                    f"Primera Campaña: ID={camp.id} '{camp.name}' | Fecha: {occ}"
                )

        if skipped:
            self.stdout.write(self.style.WARNING("--- CASOS OMITIDOS ---"))
            for u, reason, detail in skipped:
                self.stdout.write(f"[OMITIDO: {reason}] User ID={u.id} ({u.username}): {detail}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                "[DRY-RUN COMPLETADO] No se realizaron escrituras en base de datos ni llamadas de red."
            ))
            return

        # Ejecución real
        enqueued_count = 0
        dispatched_count = 0

        for c in candidates:
            user = c['user']
            camp = c['campaign']
            occ = c['occurred_at']

            outbox_event, created = enqueue_tool_activation(user, campaign=camp, occurred_at=occ)
            if created:
                enqueued_count += 1
                self.stdout.write(f"Encolado {outbox_event.event_id} (PENDING)... intentando despacho inmediato...")
                res = dispatch_outbox_event(outbox_event)
                if res.get('success'):
                    dispatched_count += 1
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Entregado exitosamente a HCC (HTTP {res.get('status_code')})."))
                else:
                    self.stdout.write(self.style.WARNING(f"  ✗ Pendiente para replay: {res.get('error')}"))

        self.stdout.write(self.style.SUCCESS(
            f"[BACKFILL COMPLETADO] Encolados: {enqueued_count} | Entregados a HCC: {dispatched_count}"
        ))
