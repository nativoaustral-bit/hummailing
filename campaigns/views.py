import json
import uuid
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.safestring import mark_safe

from .models import Campaign, CampaignLink, CampaignTemplate, CampaignSchedule
from contacts.models import Segment, Tag, Contact
from organizations.models import ActivityLog
from .tasks import send_campaign_task
from core.permissions import role_required

logger = logging.getLogger(__name__)

@login_required
def campaign_list(request):
    org = request.organization
    campaigns = Campaign.objects.filter(organization=org).prefetch_related('schedules').order_by('-created_at') if org else Campaign.objects.none()
    return render(request, 'campaigns/list.html', {'campaigns': campaigns})

@login_required
@role_required(['org_admin', 'campaign_editor'])
def campaign_create(request):

    org = request.organization
    if not org:
        messages.error(request, "No tienes una organización activa seleccionada.")
        return redirect('campaigns:list')
        
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        subject = request.POST.get('subject', '').strip()
        preheader = request.POST.get('preheader', '').strip()
        segment_id = request.POST.get('segment')
        tag_id = request.POST.get('target_tag')
        
        segment = Segment.objects.filter(id=segment_id, organization=org).first() if segment_id else None
        target_tag = Tag.objects.filter(id=tag_id, organization=org).first() if tag_id else None
        
        # Valores por defecto de la organización
        sender_name = org.default_sender_name or "Hummailing"
        sender_email = org.default_sender_email or "hola@humm.cl"
        reply_to = org.default_reply_to or "hola@humm.cl"
        
        # Bloques iniciales por defecto atractivos con Hummailing
        initial_blocks = [
            {"type": "header"},
            {"type": "title", "content": {"text": "¡Novedades exclusivas para ti!"}},
            {"type": "text", "content": {"text": "Hola {{ first_name }},\n\nQueremos contarte acerca de nuestras soluciones diseñadas para potenciar a {{ company }}."}},
            {"type": "cta", "content": {"text": "MÁS INFORMACIÓN", "url": "https://www.humm.cl", "link_type": "conversion", "service_interest": "Interés en Servicios"}},
            {"type": "footer"}
        ]
        
        campaign = Campaign.objects.create(
            organization=org,
            name=name,
            subject=subject,
            preheader=preheader,
            sender_name=sender_name,
            sender_email=sender_email,
            reply_to=reply_to,
            segment=segment,
            target_tag=target_tag,
            content_blocks=initial_blocks,
            created_by=request.user
        )
        
        ActivityLog.objects.create(
            organization=org,
            user=request.user,
            action="Creación de Campaña",
            details=f"Se creó el borrador de campaña '{campaign.name}'."
        )
        
        return redirect('campaigns:editor', campaign_id=campaign.id)
        
    segments = Segment.objects.filter(organization=org)
    tags = Tag.objects.filter(organization=org)
    return render(request, 'campaigns/create.html', {'segments': segments, 'tags': tags})

@login_required
@role_required(['org_admin', 'campaign_editor'])
def campaign_duplicate(request, campaign_id):
    org = request.organization
    campaign = get_object_or_404(Campaign, id=campaign_id, organization=org)
    
    new_campaign = Campaign.objects.create(
        organization=org,
        name=f"Copia de {campaign.name}",
        subject=campaign.subject,
        preheader=campaign.preheader,
        sender_name=campaign.sender_name,
        sender_email=campaign.sender_email,
        reply_to=campaign.reply_to,
        segment=campaign.segment,
        target_tag=campaign.target_tag,
        content_blocks=campaign.content_blocks,
        status='draft',
        created_by=request.user
    )
    
    messages.success(request, f"Campaña duplicada como '{new_campaign.name}'.")
    return redirect('campaigns:editor', campaign_id=new_campaign.id)

@login_required
@role_required(['org_admin'])
def campaign_delete(request, campaign_id):
    org = request.organization
    if request.method == 'POST':
        campaign = get_object_or_404(Campaign, id=campaign_id, organization=org)
        name = campaign.name
        campaign.delete()
        messages.success(request, f"Campaña '{name}' eliminada.")
    return redirect('campaigns:list')

@role_required(['org_admin', 'campaign_editor'])
def campaign_editor(request, campaign_id):
    try:
        org = request.organization
        if getattr(request.user, 'is_humm_master_admin', False) and (not org or not Campaign.objects.filter(id=campaign_id, organization=org).exists()):
            campaign = get_object_or_404(Campaign, id=campaign_id)
        else:
            campaign = get_object_or_404(Campaign, id=campaign_id, organization=org)
    except Exception as e:
        if request.method == 'POST':
            return JsonResponse({'status': 'error', 'message': f"No se encontró la campaña o acceso denegado: {str(e)}"}, status=404)
        raise

    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.body else {}
            blocks = data.get('blocks', [])
            theme = data.get('theme', {
                'header_bg': '#173960',
                'button_bg': '#0C6FAC',
                'button_text': '#ffffff',
                'canvas_bg': '#ffffff'
            })
            campaign.content_blocks = {
                'theme': theme,
                'blocks': blocks
            }
            campaign.save()
            
            # Sincronizar CampaignLinks para enlaces de conversión y tracking de forma segura
            for block in blocks:
                if block.get('type') == 'cta':
                    url = block.get('content', {}).get('url', '').strip()
                    text = block.get('content', {}).get('text', '').strip()
                    link_type = block.get('content', {}).get('link_type', 'conversion')
                    service_interest = block.get('content', {}).get('service_interest', text)
                    
                    if url and url != '#':
                        try:
                            link_obj = CampaignLink.objects.filter(campaign=campaign, original_url=url).first()
                            if not link_obj:
                                link_obj = CampaignLink.objects.create(
                                    campaign=campaign,
                                    original_url=url,
                                    link_type=link_type,
                                    service_interest=service_interest,
                                    token=uuid.uuid4().hex[:12]
                                )
                            else:
                                link_obj.link_type = link_type
                                link_obj.service_interest = service_interest
                                if not link_obj.token:
                                    link_obj.token = uuid.uuid4().hex[:12]
                                link_obj.save(update_fields=['link_type', 'service_interest', 'token'])
                        except Exception as link_err:
                            logger.warning(f"Error sincronizando enlace CTA '{url}': {link_err}")
                            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            try:
                logger.error(f"Error guardando contenido de campaña {campaign_id}: {tb}")
            except Exception:
                pass
            return JsonResponse({
                'status': 'error', 
                'message': f"Error al procesar el guardado: {str(e)}",
                'traceback': tb
            }, status=200)
            
    raw_blocks = campaign.content_blocks or []
    if isinstance(raw_blocks, dict):
        theme = raw_blocks.get('theme', {
            'header_bg': '#173960',
            'button_bg': '#0C6FAC',
            'button_text': '#ffffff',
            'canvas_bg': '#ffffff'
        })
        blocks = raw_blocks.get('blocks', [])
    else:
        theme = {
            'header_bg': '#173960',
            'button_bg': '#0C6FAC',
            'button_text': '#ffffff',
            'canvas_bg': '#ffffff'
        }
        blocks = raw_blocks

    blocks_json = mark_safe(json.dumps(blocks))
    theme_json = mark_safe(json.dumps(theme))
    
    # Programaciones pendientes existentes
    existing_schedules = list(campaign.schedules.filter(status='pending').order_by('scheduled_at').values('scheduled_at'))
    schedules_json = mark_safe(json.dumps([
        {
            'date': s['scheduled_at'].strftime('%Y-%m-%d'),
            'time': s['scheduled_at'].strftime('%H:%M')
        } for s in existing_schedules
    ]))
    
    return render(request, 'campaigns/editor.html', {
        'campaign': campaign,
        'blocks_json': blocks_json,
        'theme_json': theme_json,
        'schedules_json': schedules_json
    })

@login_required
def campaign_preview(request, campaign_id):
    org = request.organization
    campaign = get_object_or_404(Campaign, id=campaign_id, organization=org)
    return render(request, 'campaigns/preview.html', {'campaign': campaign})

import threading

def dispatch_campaign_task(campaign_id, test_email=None, eta=None, sender_user_id=None):
    """
    Despacha la tarea de envío vía Celery o ejecuta en hilo en segundo plano
    si Redis/Celery no está activo en el servidor.
    """
    try:
        if eta:
            send_campaign_task.apply_async((campaign_id,), eta=eta, kwargs={'sender_user_id': sender_user_id})
        elif test_email:
            send_campaign_task.delay(campaign_id, test_email=test_email)
        else:
            send_campaign_task.delay(campaign_id, sender_user_id=sender_user_id)
    except Exception as e:
        # Fallback inmediato en segundo plano
        t = threading.Thread(
            target=send_campaign_task,
            args=(campaign_id,),
            kwargs={'test_email': test_email, 'sender_user_id': sender_user_id}
        )
        t.daemon = True
        t.start()

@role_required(['org_admin', 'campaign_editor'])
def campaign_send(request, campaign_id):

    org = request.organization
    campaign = get_object_or_404(Campaign, id=campaign_id, organization=org)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.body else {}
            is_test = data.get('is_test', False)
            test_email = data.get('test_email', '').strip()
            
            if is_test and test_email:
                # Envío de prueba a un solo correo
                dispatch_campaign_task(campaign.id, test_email=test_email)
                ActivityLog.objects.create(
                    organization=org,
                    user=request.user,
                    action="Envío de Prueba",
                    details=f"Envío de prueba de '{campaign.name}' enviado a {test_email}."
                )
                return JsonResponse({'status': 'success', 'message': f'Correo de prueba enviado a {test_email}'})
                
            schedules_list = data.get('schedules', [])
            # Compatibilidad si envían scheduled_at individual
            single_scheduled = data.get('scheduled_at')
            if single_scheduled and not schedules_list:
                schedules_list = [single_scheduled]
                
            # Filtrar y parsear fechas válidas
            valid_datetimes = []
            for dt_str in schedules_list:
                if isinstance(dt_str, dict):
                    d_val = dt_str.get('date')
                    t_val = dt_str.get('time')
                    if d_val and t_val:
                        dt_str = f"{d_val}T{t_val}:00"
                    elif d_val:
                        dt_str = f"{d_val}T09:00:00"
                    else:
                        continue
                        
                if dt_str and isinstance(dt_str, str) and dt_str.strip():
                    dt = parse_datetime(dt_str.strip())
                    if dt:
                        valid_datetimes.append(dt)
                        
            if valid_datetimes:
                # Limpiar programaciones pendientes previas
                CampaignSchedule.objects.filter(campaign=campaign, status='pending').delete()
                
                valid_datetimes.sort()
                for dt in valid_datetimes:
                    CampaignSchedule.objects.create(
                        campaign=campaign,
                        scheduled_at=dt,
                        status='pending'
                    )
                    
                campaign.scheduled_at = valid_datetimes[0]
                campaign.status = 'scheduled'
                campaign.save(update_fields=['scheduled_at', 'status'])
                
                formatted_dates = ", ".join([dt.strftime('%d/%m/%Y %H:%M') for dt in valid_datetimes])
                ActivityLog.objects.create(
                    organization=org,
                    user=request.user,
                    action="Programación de Campaña",
                    details=f"Campaña '{campaign.name}' programada para {len(valid_datetimes)} fecha(s): {formatted_dates}."
                )
                return JsonResponse({
                    'status': 'success',
                    'message': f'Campaña programada exitosamente para {len(valid_datetimes)} fecha(s).'
                })
            else:
                # Envío Inmediato
                campaign.status = 'sending'
                campaign.sent_at = timezone.now()
                campaign.save(update_fields=['status', 'sent_at'])
                dispatch_campaign_task(campaign.id, sender_user_id=request.user.id)
                ActivityLog.objects.create(
                    organization=org,
                    user=request.user,
                    action="Despacho de Campaña",
                    details=f"Campaña '{campaign.name}' enviada a la cola de despacho inmediato."
                )
                return JsonResponse({
                    'status': 'success',
                    'message': 'Campaña enviada de inmediato a todos los destinatarios.'
                })
                
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'method_not_allowed'}, status=405)


import os
from PIL import Image
from django.conf import settings

@login_required
@role_required(['org_admin', 'campaign_editor'])
def upload_image(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido.'}, status=405)
        
    if 'image' not in request.FILES:
        return JsonResponse({'status': 'error', 'message': 'No se envió ningún archivo de imagen.'}, status=400)
        
    image_file = request.FILES['image']
    
    # 1. Validar límite de tamaño: Hasta 2 MB (2 * 1024 * 1024 bytes)
    max_size = 2 * 1024 * 1024
    if image_file.size > max_size:
        return JsonResponse({
            'status': 'error',
            'message': f'La imagen pesa {(image_file.size / (1024*1024)):.1f} MB. El tamaño máximo permitido es 2 MB.'
        }, status=400)
        
    # 2. Validar extensión permitida (Rechazar terminantemente SVG para evitar Stored XSS)
    ext = os.path.splitext(image_file.name)[1].lower()
    if ext == '.svg':
        return JsonResponse({
            'status': 'error',
            'message': 'El formato SVG no está permitido por motivos de seguridad. Por favor utiliza PNG, JPG, JPEG o WEBP.'
        }, status=400)
        
    allowed_extensions = ['.png', '.jpg', '.jpeg', '.webp']
    if ext not in allowed_extensions:
        return JsonResponse({
            'status': 'error',
            'message': 'Formato no soportado. Formatos válidos: PNG, JPG, JPEG o WEBP.'
        }, status=400)
        
    # 3. Validación estricta con Pillow (verificar que sea una imagen raster real y no código camuflado)
    try:
        with Image.open(image_file) as test_img:
            test_img.verify()
        image_file.seek(0)
    except Exception:
        return JsonResponse({
            'status': 'error',
            'message': 'El archivo subido no es una imagen válida o se encuentra corrupto.'
        }, status=400)
        
    # 4. Guardar y procesar dimensiones máximas
    try:
        logos_dir = settings.MEDIA_ROOT / 'logos'
        os.makedirs(logos_dir, exist_ok=True)
        
        clean_filename = f"logo_{uuid.uuid4().hex[:12]}{ext}"
        file_path = logos_dir / clean_filename
        
        with Image.open(image_file) as img:
            max_w, max_h = 800, 400
            if img.width > max_w or img.height > max_h:
                img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            
            if ext in ['.jpg', '.jpeg']:
                img.convert('RGB').save(file_path, 'JPEG', quality=85, optimize=True)
            elif ext == '.png':
                img.save(file_path, 'PNG', optimize=True)
            elif ext == '.webp':
                img.save(file_path, 'WEBP', quality=85)
            else:
                img.save(file_path)
                    
        host = request.get_host()
        proto = 'https' if not host.startswith('127.0.0.1') and not host.startswith('localhost') else request.scheme
        media_url = f"{proto}://{host}{settings.MEDIA_URL}logos/{clean_filename}"
        
        return JsonResponse({
            'status': 'success',
            'url': media_url,
            'filename': clean_filename,
            'message': 'Imagen cargada y optimizada con éxito.'
        })
    except Exception as e:
        logger.error(f"Error procesando imagen: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error al procesar la imagen en el servidor.'
        }, status=500)

