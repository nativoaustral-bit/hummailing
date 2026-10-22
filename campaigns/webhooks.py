import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Campaign, CampaignLink, TrackingEvent
from contacts.models import Contact
from organizations.models import SuppressionEntry
from opportunities.models import Opportunity

logger = logging.getLogger(__name__)

@csrf_exempt
def resend_webhook(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'method_not_allowed'}, status=405)

    try:
        payload = json.loads(request.body)
        event_type = payload.get('type')
        data = payload.get('data', {})
        
        # 1. Extraer Email del destinatario
        email = None
        to_data = data.get('to')
        if isinstance(to_data, list) and len(to_data) > 0:
            email = to_data[0]
        elif isinstance(to_data, str):
            email = to_data
        elif data.get('email'):
            email = data.get('email')

        if email:
            email = email.strip().lower()

        # 2. Identificar la Campaña mediante broadcast_id
        broadcast_id = data.get('broadcast_id')
        campaign = None
        if broadcast_id:
            campaign = Campaign.objects.filter(broadcast_id=broadcast_id).first()

        # Fallback 1: Buscar campaign_id en tags
        if not campaign:
            tags = data.get('tags', {})
            camp_id = None
            if isinstance(tags, dict):
                camp_id = tags.get('campaign_id')
            elif isinstance(tags, list):
                for t in tags:
                    if isinstance(t, dict) and t.get('name') == 'campaign_id':
                        camp_id = t.get('value')
                        break
            if camp_id:
                campaign = Campaign.objects.filter(id=camp_id).first()

        # Fallback 2: Buscar campaña más reciente enviada a este correo
        if not campaign and email:
            campaign = Campaign.objects.filter(events__contact__email=email).order_by('-sent_at').first()

        org = campaign.organization if campaign else None

        # 3. Identificar el Contacto (aislado por organización de la campaña)
        contact = None
        if email:
            if org:
                contact = Contact.objects.filter(organization=org, email=email).first()
            if not contact:
                contact = Contact.objects.filter(email=email).first()
                if contact and not org:
                    org = contact.organization

        # 4. Mapear tipos de eventos de Resend
        event_map = {
            'email.sent': 'sent',
            'email.delivered': 'delivered',
            'email.opened': 'open',
            'email.clicked': 'click',
            'email.bounced': 'bounce_perm',
            'email.complained': 'spam',
            'email.suppressed': 'bounce_perm',
            'contact.updated': 'contact_updated',
        }
        internal_event_type = event_map.get(event_type)

        # Manejo de contact.updated (por ejemplo clic en {{{RESEND_UNSUBSCRIBE_URL}}})
        if event_type == 'contact.updated':
            if data.get('unsubscribed') is True:
                internal_event_type = 'unsub'
            else:
                return JsonResponse({'status': 'ignored', 'reason': 'contact_updated_not_unsub'})

        if not internal_event_type:
            return JsonResponse({'status': 'ignored', 'reason': f'unhandled_event: {event_type}'})

        # 5. Reflejar bajas, quejas y rebotes en Hummailing
        if internal_event_type in ['unsub', 'spam']:
            if contact:
                contact.status = 'unsubscribed' if internal_event_type == 'unsub' else 'spam'
                contact.save(update_fields=['status'])
                SuppressionEntry.objects.get_or_create(
                    organization=org,
                    email=email,
                    defaults={'reason': internal_event_type}
                )
        elif internal_event_type in ['bounce_perm', 'bounce_temp']:
            if contact:
                contact.status = 'bounced'
                contact.save(update_fields=['status'])
                SuppressionEntry.objects.get_or_create(
                    organization=org,
                    email=email,
                    defaults={'reason': 'bounce_perm'}
                )

        # 6. Registrar TrackingEvent y conversión comercial (Deduplicado)
        if campaign and contact:
            link_obj = None
            if internal_event_type == 'click':
                clicked_link_url = data.get('click', {}).get('link', '')
                if clicked_link_url:
                    link_obj = CampaignLink.objects.filter(campaign=campaign, original_url=clicked_link_url).first()
                    if not link_obj:
                        for cl in CampaignLink.objects.filter(campaign=campaign):
                            if cl.token and cl.token in clicked_link_url:
                                link_obj = cl
                                break

                # Conversión de clic a Oportunidad Comercial
                if link_obj and link_obj.link_type == 'conversion':
                    topic = link_obj.service_interest or "Interés general en servicio"
                    title = f"Interés de {contact.first_name or contact.email} - {topic}"
                    Opportunity.objects.get_or_create(
                        organization=campaign.organization,
                        contact=contact,
                        campaign=campaign,
                        link=link_obj,
                        defaults={
                            'title': title,
                            'interest_topic': topic,
                            'status': 'new',
                            'priority': 'high',
                            'notes': f"Generado vía webhook de Resend tras clic en: {link_obj.original_url}"
                        }
                    )

            # Evitar registrar eventos duplicados
            already_exists = TrackingEvent.objects.filter(
                campaign=campaign,
                contact=contact,
                event_type=internal_event_type,
                link=link_obj
            ).exists()

            if not already_exists:
                ip_addr = data.get('click', {}).get('ipAddress') or None
                user_agent = data.get('click', {}).get('userAgent', '')
                TrackingEvent.objects.create(
                    campaign=campaign,
                    contact=contact,
                    event_type=internal_event_type,
                    link=link_obj,
                    ip_address=ip_addr,
                    user_agent=user_agent
                )
                logger.info(f"Webhook registrado exitosamente: {internal_event_type} ({email}) - Campaña {campaign.id}")
            else:
                logger.info(f"Webhook duplicado ignorado: {internal_event_type} ({email}) - Campaña {campaign.id}")

        return JsonResponse({'status': 'success', 'event': internal_event_type})
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

