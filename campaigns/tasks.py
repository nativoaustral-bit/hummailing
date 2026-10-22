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

from django.db.models import Q
from .models import Campaign, CampaignLink, TrackingEvent
from contacts.models import Contact
from organizations.models import SuppressionEntry

from .utils import make_absolute_image_url

logger = logging.getLogger(__name__)

def render_blocks_to_html(blocks_data, campaign, contact=None, base_site_url=None, is_broadcast=False):
    """
    Convierte los bloques JSON y el tema visual en HTML profesional con colores globales.
    Reemplaza enlaces con URLs de seguimiento para detectar clics y conversiones.
    Garantiza que todas las imágenes sean URLs absolutas públicas para renderizar en clientes de correo.
    
    - Para Broadcasts (is_broadcast=True):
      - Adapta variables a Handlebars de Resend ({{{FIRST_NAME|Hola}}}, {{{company|}}}, etc.)
      - Enlaza CTA a /t/{token}/?e={{{EMAIL}}} para atribuir clicks individualmente sin tokens hardcodeados
      - Enlaza desuscripción a {{{RESEND_UNSUBSCRIBE_URL}}}
    - Para Envíos individuales/pruebas (is_broadcast=False):
      - Reemplaza tokens con el contacto específico
    """
    base_site_url = (base_site_url or getattr(settings, 'SITE_URL', 'https://mailing.humm.cl')).rstrip('/')

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
            raw_logo = content.get('logo_url', '').strip()
            logo_url = make_absolute_image_url(raw_logo, base_site_url)
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
            raw_url = content.get('url', '')
            url = make_absolute_image_url(raw_url, base_site_url)
            if url:
                html += f'<div style="padding: 16px 32px; text-align: center;"><img src="{url}" style="max-width: 100%; height: auto; border-radius: 6px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);"></div>'
                
        elif b_type == 'cta':
            text = content.get('text', 'Más Información')
            raw_url = content.get('url', '#')
            
            # Enlazar con CampaignLink para seguimiento y conversiones
            target_url = raw_url
            if raw_url and raw_url != '#':
                link_obj = CampaignLink.objects.filter(campaign=campaign, original_url=raw_url).first()
                if link_obj and link_obj.token:
                    if is_broadcast:
                        # En broadcasts: usar variable de interpolación de Resend {{{EMAIL}}}
                        # Evita reutilizar el ID o token de una sola persona para toda la audiencia
                        target_url = f"{base_site_url}/t/{link_obj.token}/?e=" + "{{{EMAIL}}}"
                    elif contact:
                        target_url = f"{base_site_url}/t/{link_obj.token}/?c={contact.id}"
                    
            html += f'<div style="text-align: center; padding: 28px 32px;"><a href="{target_url}" style="display: inline-block; background-color: {button_bg}; color: {button_text}; font-weight: bold; padding: 14px 34px; border-radius: 6px; font-size: 14px; text-transform: uppercase; letter-spacing: 0.08em; text-decoration: none; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);">{text}</a></div>'
            
        elif b_type == 'footer':
            org_name = campaign.organization.trade_name if campaign.organization else "Humm"
            if is_broadcast:
                # Regla 6: En Broadcasts incluir {{{RESEND_UNSUBSCRIBE_URL}}}
                unsub_url = "{{{RESEND_UNSUBSCRIBE_URL}}}"
            elif contact:
                from core.security import generate_unsubscribe_token
                token = generate_unsubscribe_token(contact)
                camp_param = f"?camp={campaign.id}" if campaign and campaign.id else ""
                unsub_url = f"{base_site_url}/unsubscribe/{token}/{camp_param}"
            else:
                unsub_url = "{{{RESEND_UNSUBSCRIBE_URL}}}"
                
            html += f'<div style="margin-top: 28px; padding: 24px 32px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; text-align: center; font-size: 12px; color: #64748b;">'
            html += f'<p style="margin: 0;">© {timezone.now().year} {org_name} — Vía Hummailing. Recibes este correo porque estás suscrito a nuestras novedades.</p>'
            html += f'<p style="margin-top: 10px;"><a href="{unsub_url}" style="color: {button_bg}; text-decoration: underline;">Cancelar suscripción / Darse de baja</a></p>'
            html += '</div>'

    html += '</div>'

    # Personalización de variables según el modo
    if is_broadcast:
        # Formato de variables de Resend Broadcasts
        html = html.replace('{{ first_name }}', '{{{FIRST_NAME|Hola}}}').replace('{{first_name}}', '{{{FIRST_NAME|Hola}}}')
        html = html.replace('{{ last_name }}', '{{{LAST_NAME|}}}').replace('{{last_name}}', '{{{LAST_NAME|}}}')
        html = html.replace('{{ company }}', '{{{company|}}}').replace('{{company}}', '{{{company|}}}')
        html = html.replace('{{ email }}', '{{{EMAIL}}}').replace('{{email}}', '{{{EMAIL}}}')
    elif contact:
        first_name = contact.first_name if contact.first_name else "Hola"
        html = html.replace('{{ first_name }}', first_name).replace('{{first_name}}', first_name)
        company = contact.company if contact.company else ""
        html = html.replace('{{ company }}', company).replace('{{company}}', company)
        html = html.replace('{{ email }}', contact.email).replace('{{email}}', contact.email)

    return html


def ensure_resend_contact_property(key='company', prop_type='string'):
    """Garantiza que la propiedad personalizada de contacto exista en el esquema de Resend."""
    try:
        props = resend.ContactProperties.list()
        data = props.get('data', []) if isinstance(props, dict) else getattr(props, 'data', [])
        for p in data:
            p_key = p.get('key') if isinstance(p, dict) else getattr(p, 'key', '')
            if p_key == key:
                return True
        resend.ContactProperties.create({'key': key, 'type': prop_type})
        return True
    except Exception as e:
        logger.warning(f"Aviso al verificar/crear propiedad '{key}' en Resend: {e}")
        return False


def get_or_create_resend_topic(org):
    """
    Obtiene o crea un Topic de suscripción exclusivo por organización para multiempresa.
    Respeta preferencias por empresa.
    """
    if not org:
        return None
    if org.resend_topic_id:
        try:
            resend.Topics.get(id=org.resend_topic_id)
            return org.resend_topic_id
        except Exception:
            pass # Recrear si no existe remotamente

    topic_name = f"Org {org.id} - {org.trade_name or org.name}"[:50]
    try:
        t_list = resend.Topics.list()
        data = t_list.get('data', []) if isinstance(t_list, dict) else getattr(t_list, 'data', [])
        for t in data:
            t_name = t.get('name') if isinstance(t, dict) else getattr(t, 'name', '')
            if t_name == topic_name or t_name == (org.trade_name or org.name)[:50]:
                t_id = t.get('id') if isinstance(t, dict) else getattr(t, 'id', '')
                org.resend_topic_id = t_id
                org.save(update_fields=['resend_topic_id'])
                return t_id
    except Exception as list_err:
        logger.warning(f"Error listando topics en Resend: {list_err}")

    try:
        new_topic = resend.Topics.create({
            'name': topic_name,
            'default_subscription': 'opt_in',
            'description': f"Comunicaciones de {org.trade_name or org.name}"
        })
        t_id = new_topic.get('id') if isinstance(new_topic, dict) else getattr(new_topic, 'id', None)
        if t_id:
            org.resend_topic_id = t_id
            org.save(update_fields=['resend_topic_id'])
            return t_id
    except Exception as create_err:
        logger.warning(f"Aviso: No se pudo crear topic para organización {org.id}: {create_err}")
    return None


def get_or_create_resend_segment(campaign):
    """
    Crea o reutiliza un segmento exclusivo por organización y campaña en Resend.
    Gestiona automáticamente la cuota de segmentos de Resend (máximo 3 en plan gratuito).
    """
    if campaign.resend_segment_id:
        try:
            resend.Segments.get(id=campaign.resend_segment_id)
            return campaign.resend_segment_id
        except Exception:
            pass # Recrear si fue borrado en Resend

    seg_name = f"Camp {campaign.id} - {campaign.name[:25]} ({timezone.now().strftime('%y%m%d%H%M')})"[:50]

    # Si tenemos 3 o más segmentos en la cuenta, liberar espacio eliminando segmentos antiguos
    try:
        seg_list = resend.Segments.list()
        data = seg_list.get('data', []) if isinstance(seg_list, dict) else getattr(seg_list, 'data', [])
        if len(data) >= 3:
            logger.info(f"Cuota de segmentos al límite ({len(data)}/3). Liberando segmento antiguo para campaña {campaign.id}...")
            for s in data:
                s_name = s.get('name', '') if isinstance(s, dict) else getattr(s, 'name', '')
                s_id = s.get('id') if isinstance(s, dict) else getattr(s, 'id', '')
                if s_name != 'General' and (s_name.startswith('Camp ') or 'Test' in s_name):
                    try:
                        resend.Segments.remove(id=s_id)
                        logger.info(f"Segmento '{s_name}' ({s_id}) liberado con éxito.")
                        break
                    except Exception as rm_err:
                        logger.warning(f"No se pudo liberar segmento {s_id}: {rm_err}")
    except Exception as list_err:
        logger.warning(f"Error listando segmentos en Resend: {list_err}")

    # 2. Intentar crear el nuevo segmento
    try:
        new_seg = resend.Segments.create({'name': seg_name})
        seg_id = new_seg.get('id') if isinstance(new_seg, dict) else getattr(new_seg, 'id', None)
        if not seg_id:
            raise ValueError(f"Resend no retornó un id de segmento válido: {new_seg}")
        campaign.resend_segment_id = seg_id
        campaign.save(update_fields=['resend_segment_id'])
        return seg_id
    except Exception as create_err:
        # Si aún falla por límite de segmentos, intentar liberar cualquier segmento Camp y reintentar
        err_str = str(create_err)
        if "3 segments" in err_str or "Upgrade to add more" in err_str:
            try:
                seg_list = resend.Segments.list()
                data = seg_list.get('data', []) if isinstance(seg_list, dict) else getattr(seg_list, 'data', [])
                for s in data:
                    s_name = s.get('name', '') if isinstance(s, dict) else getattr(s, 'name', '')
                    s_id = s.get('id') if isinstance(s, dict) else getattr(s, 'id', '')
                    if s_name != 'General':
                        resend.Segments.remove(id=s_id)
                        new_seg = resend.Segments.create({'name': seg_name})
                        seg_id = new_seg.get('id') if isinstance(new_seg, dict) else getattr(new_seg, 'id', None)
                        if seg_id:
                            campaign.resend_segment_id = seg_id
                            campaign.save(update_fields=['resend_segment_id'])
                            return seg_id
            except Exception:
                pass
        raise


def sync_contacts_to_resend_segment(contacts, segment_id, org):
    """
    Sincroniza destinatarios automáticamente antes del envío:
    - Sincroniza correo, nombre y propiedades necesarias (empresa).
    - Respeta bajas y bloqueos existentes en Resend y en Hummailing.
    - Nunca reactiva automáticamente un contacto.
    - Añade los contactos habilitados al segmento exclusivo.
    Retorna lista de contactos sincronizados y cantidad de bajas detectadas.
    """
    synced_contacts = []
    skipped_unsub = 0

    for contact in contacts:
        contact_unsub_in_resend = False
        try:
            existing = resend.Contacts.get(email=contact.email)
            if existing:
                if existing.get('unsubscribed') is True:
                    contact_unsub_in_resend = True
                else:
                    contact_id = existing.get('id')
                    contact.resend_id = contact_id
                    contact.save(update_fields=['resend_id'])

                    update_data = {
                        'id': contact_id,
                        'first_name': contact.first_name or '',
                        'last_name': contact.last_name or '',
                    }
                    if contact.company:
                        update_data['properties'] = {'company': contact.company}
                    try:
                        resend.Contacts.update(update_data)
                    except Exception as upd_err:
                        logger.warning(f"Aviso actualizando contacto {contact.email} en Resend: {upd_err}")
        except Exception:
            # Contacto no registrado aún en Resend, crearlo
            create_data = {
                'email': contact.email,
                'first_name': contact.first_name or '',
                'last_name': contact.last_name or '',
                'unsubscribed': False,
            }
            if contact.company:
                create_data['properties'] = {'company': contact.company}
            try:
                created = resend.Contacts.create(create_data)
                contact_id = created.get('id') if isinstance(created, dict) else getattr(created, 'id', None)
                if contact_id:
                    contact.resend_id = contact_id
                    contact.save(update_fields=['resend_id'])
            except Exception as create_err:
                logger.error(f"Fallo al crear contacto {contact.email} en Resend: {create_err}")
                raise create_err

        if contact_unsub_in_resend:
            # Regla 2: Respeta bajas existentes; nunca reactives automáticamente un contacto
            skipped_unsub += 1
            contact.status = 'unsubscribed'
            contact.save(update_fields=['status'])
            SuppressionEntry.objects.get_or_create(
                organization=org,
                email=contact.email,
                defaults={'reason': 'unsub'}
            )
            logger.info(f"Contacto {contact.email} omitido de envío por baja previa en Resend.")
            continue

        # Asociar al segmento exclusivo de la campaña
        try:
            resend.ContactSegments.add({
                'segment_id': segment_id,
                'email': contact.email
            })
            synced_contacts.append(contact)
        except Exception as add_err:
            err_msg = str(add_err).lower()
            if 'already' in err_msg or 'exists' in err_msg or 'conflict' in err_msg:
                synced_contacts.append(contact)
            else:
                logger.error(f"Error asociando {contact.email} al segmento {segment_id}: {add_err}")
                raise add_err

    return synced_contacts, skipped_unsub


def _trigger_hcc_activation_safe(campaign, sender_user_id):
    """Evaluación segura de activación para HCC sin afectar el flujo de la campaña."""
    if sender_user_id:
        try:
            from core.models import User
            from core.services.hcc_service import check_and_trigger_activation
            sender_user = User.objects.filter(id=sender_user_id).first()
            check_and_trigger_activation(campaign, sender_user=sender_user)
        except Exception as hcc_exc:
            logger.warning(f"Aviso operacional: Error en evaluación de activación HCC para campaña {campaign.id}: {type(hcc_exc).__name__}: {str(hcc_exc)[:150]}")


@shared_task
def send_campaign_task(campaign_id, test_email=None, sender_user_id=None):
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

    # =========================================================================
    # CASO 1: Envío de prueba individual (Usa estrictamente /emails)
    # =========================================================================
    if test_email:
        test_contact, _ = Contact.objects.get_or_create(
            organization=org,
            email=test_email.strip().lower(),
            defaults={'first_name': 'Prueba', 'last_name': 'Hummailing'}
        )
        personalized_html = render_blocks_to_html(campaign.content_blocks, campaign, contact=test_contact, is_broadcast=False)
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
            logger.info(f"Test email sent to {test_email} via /emails")
        except Exception as e:
            logger.error(f"Error sending test email to {test_email}: {e}")
        return

    # =========================================================================
    # CASO 2: Envío Masivo Real de Campaña (Usa estrictamente /broadcasts)
    # =========================================================================

    # Regla 1: No reprocesar campañas históricas o ya enviadas
    if campaign.status == 'sent':
        logger.info(f"Campaña {campaign.id} ya figura como enviada ('sent'). No se reprocesa.")
        return

    # Regla 5: Idempotencia - verificar si ya existe broadcast_id previo y su estado en Resend
    if campaign.broadcast_id:
        try:
            existing_bc = resend.Broadcasts.get(id=campaign.broadcast_id)
            remote_status = existing_bc.get('status') if isinstance(existing_bc, dict) else getattr(existing_bc, 'status', None)
            if remote_status in ['sent', 'sending', 'queued']:
                logger.info(f"Broadcast {campaign.broadcast_id} ya se encuentra en estado remoto '{remote_status}'. Evitando reenvío duplicado.")
                campaign.status = 'sent'
                campaign.broadcast_status = remote_status
                campaign.sent_at = campaign.sent_at or timezone.now()
                campaign.save(update_fields=['status', 'broadcast_status', 'sent_at'])
                return
            elif remote_status == 'draft':
                logger.info(f"Broadcast {campaign.broadcast_id} existente en borrador. Despachando envío...")
                resend.Broadcasts.send({"broadcast_id": campaign.broadcast_id})
                campaign.status = 'sent'
                campaign.broadcast_status = 'sent'
                campaign.sent_at = timezone.now()
                campaign.save(update_fields=['status', 'broadcast_status', 'sent_at'])
                _trigger_hcc_activation_safe(campaign, sender_user_id)
                return
        except Exception as bc_check_err:
            logger.warning(f"Error consultando broadcast existente {campaign.broadcast_id}: {bc_check_err}")

    # Pasar a estado 'sending' mientras sincroniza y despacha
    campaign.status = 'sending'
    campaign.save(update_fields=['status'])

    # 1. Obtener destinatarios habilitados
    suppressed_emails = set(SuppressionEntry.objects.filter(
        Q(organization=org) | Q(organization__isnull=True)
    ).values_list('email', flat=True))

    contacts = Contact.objects.filter(organization=org, status='active').exclude(email__in=suppressed_emails)
    if campaign.target_tag:
        contacts = contacts.filter(tags=campaign.target_tag)

    contacts = contacts.distinct()
    contact_count = contacts.count()

    # Regla 7: Respetar cuota de contactos de marketing (límite gratis de 1.000 contactos)
    if contact_count > 1000:
        campaign.status = 'draft'
        campaign.error_message = f"La campaña tiene {contact_count} contactos, superando la cuota máxima permitida (1.000 contactos)."
        campaign.save(update_fields=['status', 'error_message'])
        logger.error(f"Campaña {campaign.id} bloqueada por superar cuota de marketing gratuita: {contact_count} contactos.")
        return

    if contact_count == 0:
        campaign.status = 'draft'
        campaign.error_message = "No existen destinatarios activos habilitados en la audiencia seleccionada."
        campaign.save(update_fields=['status', 'error_message'])
        logger.info(f"Campaña {campaign.id} sin destinatarios disponibles.")
        return

    # 2. Sincronizar Topics, Segmento y Contactos con Resend
    try:
        topic_id = get_or_create_resend_topic(org)
        segment_id = get_or_create_resend_segment(campaign)
        ensure_resend_contact_property('company', 'string')

        synced_contacts, skipped_unsub = sync_contacts_to_resend_segment(contacts, segment_id, org)
        if len(synced_contacts) == 0:
            campaign.status = 'draft'
            campaign.error_message = "Todos los contactos seleccionados están dados de baja o bloqueados."
            campaign.save(update_fields=['status', 'error_message'])
            logger.warning(f"Campaña {campaign.id}: 0 contactos habilitados tras sincronización ({skipped_unsub} bajas).")
            return
    except Exception as sync_err:
        campaign.status = 'draft'
        campaign.error_message = f"Error de sincronización con Resend: {sync_err}"
        campaign.save(update_fields=['status', 'error_message'])
        logger.error(f"Fallo de sincronización para campaña {campaign.id}: {sync_err}")
        return

    # 3. Construir HTML de Broadcast y Crear Broadcast remoto
    try:
        broadcast_html = render_blocks_to_html(campaign.content_blocks, campaign, is_broadcast=True)
        broadcast_params = {
            "segment_id": segment_id,
            "from": f"{campaign.sender_name} <{campaign.sender_email}>",
            "subject": campaign.subject,
            "html": broadcast_html,
            "name": f"{campaign.name[:45]} (#{campaign.id})",
        }
        if topic_id:
            broadcast_params["topic_id"] = topic_id
        if campaign.reply_to:
            broadcast_params["reply_to"] = campaign.reply_to

        bc_create_res = resend.Broadcasts.create(broadcast_params)
        bc_id = bc_create_res.get('id') if isinstance(bc_create_res, dict) else getattr(bc_create_res, 'id', None)
        if not bc_id:
            raise ValueError(f"Resend no retornó un broadcast_id válido: {bc_create_res}")

        # Guardar broadcast_id ANTES de enviar
        campaign.broadcast_id = bc_id
        campaign.broadcast_status = 'draft'
        campaign.error_message = ''
        campaign.save(update_fields=['broadcast_id', 'broadcast_status', 'error_message'])
        logger.info(f"Broadcast {bc_id} registrado previamente en Hummailing para campaña {campaign.id}.")
    except Exception as bc_err:
        campaign.status = 'draft'
        campaign.error_message = f"Fallo al crear Broadcast en Resend: {bc_err}"
        campaign.save(update_fields=['status', 'error_message'])
        logger.error(f"Error al crear broadcast para campaña {campaign.id}: {bc_err}")
        # IMPORTANTE: NO caer en /emails como alternativa
        return

    # 4. Enviar el Broadcast remotamente
    try:
        send_res = resend.Broadcasts.send({"broadcast_id": campaign.broadcast_id})
        logger.info(f"Broadcast {campaign.broadcast_id} enviado exitosamente: {send_res}")
        campaign.status = 'sent'
        campaign.sent_at = timezone.now()
        campaign.broadcast_status = 'sent'
        campaign.save(update_fields=['status', 'sent_at', 'broadcast_status'])
    except Exception as send_err:
        campaign.status = 'draft'
        campaign.error_message = f"Error al despachar el broadcast {campaign.broadcast_id}: {send_err}"
        campaign.save(update_fields=['status', 'error_message'])
        logger.error(f"Error enviando broadcast {campaign.broadcast_id}: {send_err}")
        # IMPORTANTE: NO caer en /emails como alternativa
        return

    # 5. Registrar eventos de envío (TrackingEvent) para los contactos sincronizados
    for contact in synced_contacts:
        if not TrackingEvent.objects.filter(campaign=campaign, contact=contact, event_type='sent').exists():
            TrackingEvent.objects.create(
                campaign=campaign,
                contact=contact,
                event_type='sent'
            )

    logger.info(f"Campaña {campaign.id} completada vía Broadcasts. Destinatarios: {len(synced_contacts)}")

    # 6. Activación HCC
    _trigger_hcc_activation_safe(campaign, sender_user_id)

