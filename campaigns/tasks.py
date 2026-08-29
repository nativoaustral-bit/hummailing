import logging
from django.utils import timezone
from django.conf import settings
try:
    from celery import shared_task
except Exception:
    def shared_task(func):
        class TaskWrapper:
            def __init__(self, f):
                self.f = f
            def __call__(self, *args, **kwargs):
                return self.f(*args, **kwargs)
            def delay(self, *args, **kwargs):
                return self.f(*args, **kwargs)
            def apply_async(self, args=(), kwargs=None, **options):
                return self.f(*args, **(kwargs or {}))
        return TaskWrapper(func)

import resend

from .models import Campaign, CampaignLink, TrackingEvent
from contacts.models import Contact
from organizations.models import SuppressionEntry

logger = logging.getLogger(__name__)

def render_blocks_to_html(blocks_data, campaign, contact=None, base_site_url="http://localhost:8000"):
    """
    Convierte los bloques JSON y el tema visual en HTML profesional con colores globales.
    Reemplaza enlaces con URLs de seguimiento para detectar clics y conversiones.
    """
    if isinstance(blocks_data, dict):
        theme = blocks_data.get('theme', {})
        blocks = blocks_data.get('blocks', [])
    else:
        theme = {}
        blocks = blocks_data or []
        
    header_bg = theme.get('header_bg', '#173960')
    button_bg = theme.get('button_bg', '#0C6FAC')
    button_text = theme.get('button_text', '#ffffff')
    canvas_bg = theme.get('canvas_bg', '#ffffff')
    
    # Luminancia y contraste automático para el encabezado
    is_light_header = header_bg.lower() in ['#ffffff', '#f8fafc', '#f1f5f9', 'white', '#fff']
    header_text_color = '#1e293b' if is_light_header else '#ffffff'
    header_sub_color = '#64748b' if is_light_header else '#99c5d7'
    
    html = f'<div style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; background: {canvas_bg}; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">'
    
    for block in blocks:
        b_type = block.get('type')
        content = block.get('content', {})
        
        if b_type == 'header':
            logo_url = content.get('logo_url', '').strip()
            company_name = content.get('company_name', '').strip() or (campaign.organization.trade_name if campaign.organization else "Hummailing")
            subtitle = content.get('subtitle', '').strip()
            
            html += f'<div style="text-align: center; padding: 26px 20px; background-color: {header_bg}; color: {header_text_color};">'
            if logo_url:
                html += f'<img src="{logo_url}" alt="{company_name}" style="max-height: 55px; max-width: 240px; margin: 0 auto; display: block; height: auto;">'
                if subtitle:
                    html += f'<p style="font-size: 12px; color: {header_sub_color}; margin: 8px 0 0 0; letter-spacing: 0.05em;">{subtitle}</p>'
            else:
                html += f'<h1 style="font-size: 20px; font-weight: 800; letter-spacing: 0.12em; color: {header_text_color}; margin: 0; text-transform: uppercase;">{company_name}</h1>'
                if subtitle:
                    html += f'<p style="font-size: 11px; color: {header_sub_color}; margin: 4px 0 0 0; letter-spacing: 0.05em;">{subtitle}</p>'
            html += '</div>'
            
        elif b_type == 'title':
            text = content.get('text', '')
            html += f'<div style="padding: 28px 32px 12px 32px;"><h2 style="font-size: 22px; font-weight: bold; color: #173960; margin: 0; line-height: 1.3;">{text}</h2></div>'
            
        elif b_type == 'text':
            text = content.get('text', '').replace('\n', '<br>')
            html += f'<div style="padding: 8px 32px;"><div style="color: #334155; font-size: 15px; line-height: 1.6;">{text}</div></div>'
            
        elif b_type == 'image':
            url = content.get('url', '')
            if url:
                html += f'<div style="padding: 16px 32px; text-align: center;"><img src="{url}" style="max-width: 100%; height: auto; border-radius: 6px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);"></div>'
                
        elif b_type == 'cta':
            text = content.get('text', 'Más Información')
            raw_url = content.get('url', '#')
            
            # Enlazar con CampaignLink para seguimiento si tenemos el contacto
            target_url = raw_url
            if contact and raw_url and raw_url != '#':
                link_obj = CampaignLink.objects.filter(campaign=campaign, original_url=raw_url).first()
                if link_obj and link_obj.token:
                    target_url = f"{base_site_url}/t/{link_obj.token}/?c={contact.id}"
                    
            html += f'<div style="text-align: center; padding: 28px 32px;"><a href="{target_url}" style="display: inline-block; background-color: {button_bg}; color: {button_text}; font-weight: bold; padding: 14px 34px; border-radius: 6px; font-size: 14px; text-transform: uppercase; letter-spacing: 0.08em; text-decoration: none; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);">{text}</a></div>'
            
        elif b_type == 'footer':
            org_name = campaign.organization.trade_name if campaign.organization else "Humm"
            unsub_url = "#"
            if contact:
                unsub_url = f"{base_site_url}/unsubscribe/direct/?c={contact.id}&camp={campaign.id}"
                
            html += f'<div style="margin-top: 28px; padding: 24px 32px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; text-align: center; font-size: 12px; color: #64748b;">'
            html += f'<p style="margin: 0;">© {timezone.now().year} {org_name} — Vía Hummailing. Recibes este correo porque estás suscrito a nuestras novedades.</p>'
            html += f'<p style="margin-top: 10px;"><a href="{unsub_url}" style="color: {button_bg}; text-decoration: underline;">Cancelar suscripción / Darse de baja</a></p>'
            html += '</div>'

    html += '</div>'
    return html
    return html

@shared_task
def send_campaign_task(campaign_id, test_email=None):
    try:
        campaign = Campaign.objects.select_related('organization').get(id=campaign_id)
    except Campaign.DoesNotExist:
        logger.error(f"Campaign {campaign_id} not found.")
        return

    # Preparar Resend API Key
    resend.api_key = settings.RESEND_API_KEY
    if not resend.api_key or resend.api_key == 're_placeholder_key':
        logger.warning("Resend API Key is not configured correctly.")

    org = campaign.organization

    if test_email:
        # Caso 1: Envío de prueba individual
        test_contact, _ = Contact.objects.get_or_create(
            organization=org,
            email=test_email.strip().lower(),
            defaults={'first_name': 'Prueba', 'last_name': 'Hummailing'}
        )
        personalized_html = render_blocks_to_html(campaign.content_blocks, campaign, contact=test_contact)
        personalized_html = personalized_html.replace('{{ first_name }}', test_contact.first_name)
        personalized_html = personalized_html.replace('{{first_name}}', test_contact.first_name)
        personalized_html = personalized_html.replace('{{ company }}', 'Empresa de Prueba')
        personalized_html = personalized_html.replace('{{company}}', 'Empresa de Prueba')

        try:
            params = {
                "from": f"{campaign.sender_name} <{campaign.sender_email}>",
                "to": test_email.strip().lower(),
                "subject": f"[PRUEBA] {campaign.subject}",
                "html": personalized_html,
            }
            if campaign.reply_to:
                params["reply_to"] = campaign.reply_to

            resend.Emails.send(params)
            logger.info(f"Test email sent to {test_email}")
        except Exception as e:
            logger.error(f"Error sending test email to {test_email}: {e}")
        return

    # Caso 2: Envío Masivo Real
    campaign.status = 'sending'
    campaign.sent_at = timezone.now()
    campaign.save(update_fields=['status', 'sent_at'])

    # Exclusiones de la organización
    suppressed_emails = set(SuppressionEntry.objects.filter(
        Q(organization=org) | Q(organization__isnull=True)
    ).values_list('email', flat=True))

    contacts = Contact.objects.filter(organization=org, status='active').exclude(email__in=suppressed_emails)
    if campaign.target_tag:
        contacts = contacts.filter(tags=campaign.target_tag)

    success_count = 0
    error_count = 0

    for contact in contacts:
        # Generar HTML con personalización
        html_content = render_blocks_to_html(campaign.content_blocks, campaign, contact=contact)
        
        first_name = contact.first_name if contact.first_name else "Hola"
        html_content = html_content.replace('{{ first_name }}', first_name).replace('{{first_name}}', first_name)
        
        company = contact.company if contact.company else ""
        html_content = html_content.replace('{{ company }}', company).replace('{{company}}', company)

        try:
            params = {
                "from": f"{campaign.sender_name} <{campaign.sender_email}>",
                "to": contact.email,
                "subject": campaign.subject,
                "html": html_content,
            }
            if campaign.reply_to:
                params["reply_to"] = campaign.reply_to

            response = resend.Emails.send(params)
            success_count += 1
            
            # Registrar evento de envío
            TrackingEvent.objects.create(
                campaign=campaign,
                contact=contact,
                event_type='sent'
            )
            logger.info(f"Sent email to {contact.email}, ID: {response.get('id')}")
        except Exception as e:
            error_count += 1
            TrackingEvent.objects.create(
                campaign=campaign,
                contact=contact,
                event_type='error'
            )
            logger.error(f"Error sending to {contact.email}: {e}")

    campaign.status = 'sent'
    campaign.save(update_fields=['status'])
    logger.info(f"Campaign {campaign_id} dispatch completed. Success: {success_count}, Errors: {error_count}")
