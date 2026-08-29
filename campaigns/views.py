import json
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.utils.safestring import mark_safe

from .models import Campaign, CampaignLink, CampaignTemplate
from contacts.models import Segment, Tag, Contact
from organizations.models import ActivityLog
from .tasks import send_campaign_task

@login_required
def campaign_list(request):
    org = request.organization
    campaigns = Campaign.objects.filter(organization=org).order_by('-created_at') if org else Campaign.objects.none()
    return render(request, 'campaigns/list.html', {'campaigns': campaigns})

@login_required
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
def campaign_delete(request, campaign_id):
    org = request.organization
    if request.method == 'POST':
        campaign = get_object_or_404(Campaign, id=campaign_id, organization=org)
        name = campaign.name
        campaign.delete()
        messages.success(request, f"Campaña '{name}' eliminada.")
    return redirect('campaigns:list')

@login_required
def campaign_editor(request, campaign_id):
    org = request.organization
    campaign = get_object_or_404(Campaign, id=campaign_id, organization=org)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
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
            
            # Sincronizar CampaignLinks para enlaces de conversión y tracking
            for block in blocks:
                if block.get('type') == 'cta':
                    url = block.get('content', {}).get('url', '').strip()
                    text = block.get('content', {}).get('text', '').strip()
                    link_type = block.get('content', {}).get('link_type', 'conversion')
                    service_interest = block.get('content', {}).get('service_interest', text)
                    
                    if url and url != '#':
                        link_obj, created = CampaignLink.objects.get_or_create(
                            campaign=campaign,
                            original_url=url,
                            defaults={
                                'link_type': link_type,
                                'service_interest': service_interest,
                                'token': uuid.uuid4().hex[:12]
                            }
                        )
                        if not link_obj.token:
                            link_obj.token = uuid.uuid4().hex[:12]
                            link_obj.save()
                            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
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
    
    return render(request, 'campaigns/editor.html', {
        'campaign': campaign,
        'blocks_json': blocks_json,
        'theme_json': theme_json
    })

@login_required
def campaign_preview(request, campaign_id):
    org = request.organization
    campaign = get_object_or_404(Campaign, id=campaign_id, organization=org)
    return render(request, 'campaigns/preview.html', {'campaign': campaign})

@login_required
def campaign_send(request, campaign_id):
    org = request.organization
    campaign = get_object_or_404(Campaign, id=campaign_id, organization=org)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.body else {}
            scheduled_at_str = data.get('scheduled_at')
            is_test = data.get('is_test', False)
            test_email = data.get('test_email', '').strip()
            
            if is_test and test_email:
                # Envío de prueba a un solo correo
                send_campaign_task.delay(campaign.id, test_email=test_email)
                ActivityLog.objects.create(
                    organization=org,
                    user=request.user,
                    action="Envío de Prueba",
                    details=f"Envío de prueba de '{campaign.name}' enviado a {test_email}."
                )
                return JsonResponse({'status': 'success', 'message': f'Correo de prueba enviado a {test_email}'})
                
            if scheduled_at_str:
                campaign.scheduled_at = parse_datetime(scheduled_at_str)
                campaign.status = 'scheduled'
                campaign.save()
                send_campaign_task.apply_async((campaign.id,), eta=campaign.scheduled_at)
                ActivityLog.objects.create(
                    organization=org,
                    user=request.user,
                    action="Programación de Campaña",
                    details=f"Campaña '{campaign.name}' programada para {campaign.scheduled_at}."
                )
            else:
                campaign.status = 'sending'
                campaign.save()
                send_campaign_task.delay(campaign.id)
                ActivityLog.objects.create(
                    organization=org,
                    user=request.user,
                    action="Despacho de Campaña",
                    details=f"Campaña '{campaign.name}' enviada a la cola de despacho."
                )
                
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'method_not_allowed'}, status=405)


import os
from PIL import Image
from django.conf import settings

@login_required
def upload_image(request):
    if request.method != 'POST' or 'image' not in request.FILES:
        return JsonResponse({'status': 'error', 'message': 'No se envió ningún archivo de imagen.'}, status=400)
        
    image_file = request.FILES['image']
    
    # 1. Validar límite de tamaño: Máximo 200 KB (200 * 1024 bytes)
    max_size = 200 * 1024
    if image_file.size > max_size:
        return JsonResponse({
            'status': 'error',
            'message': f'La imagen pesa {image_file.size // 1024} KB. El tamaño máximo permitido es 200 KB.'
        }, status=400)
        
    # 2. Validar extensión permitida
    ext = os.path.splitext(image_file.name)[1].lower()
    allowed_extensions = ['.png', '.jpg', '.jpeg', '.webp', '.svg', '.gif']
    if ext not in allowed_extensions:
        return JsonResponse({
            'status': 'error',
            'message': 'Formato no soportado. Formatos válidos: PNG, JPG, JPEG, WEBP, SVG o GIF.'
        }, status=400)
        
    # 3. Guardar y procesar dimensiones máximas
    logos_dir = settings.MEDIA_ROOT / 'logos'
    os.makedirs(logos_dir, exist_ok=True)
    
    clean_filename = f"logo_{uuid.uuid4().hex[:10]}{ext}"
    file_path = logos_dir / clean_filename
    
    if ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif']:
        try:
            with Image.open(image_file) as img:
                # Dimensiones recomendadas para logos en email (máximo 600px ancho, 200px alto)
                max_w, max_h = 600, 200
                if img.width > max_w or img.height > max_h:
                    img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
                
                # Guardar optimizado
                if ext in ['.jpg', '.jpeg']:
                    img.convert('RGB').save(file_path, 'JPEG', quality=85, optimize=True)
                elif ext == '.png':
                    img.save(file_path, 'PNG', optimize=True)
                else:
                    img.save(file_path)
        except Exception:
            with open(file_path, 'wb+') as dest:
                for chunk in image_file.chunks():
                    dest.write(chunk)
    else:
        # SVG
        with open(file_path, 'wb+') as dest:
            for chunk in image_file.chunks():
                dest.write(chunk)
                
    media_url = f"{settings.MEDIA_URL}logos/{clean_filename}"
    return JsonResponse({
        'status': 'success',
        'url': media_url,
        'filename': clean_filename,
        'message': 'Imagen cargada y optimizada con éxito.'
    })
