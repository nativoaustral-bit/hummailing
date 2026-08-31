from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from contacts.models import Contact
from campaigns.models import Campaign, TrackingEvent
from opportunities.models import Opportunity
from organizations.models import ActivityLog
from .models import Lead

def landing_page(request):
    # Guardar UTMs de la URL en la sesión si vienen presentes
    for param in ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content']:
        if param in request.GET:
            request.session[param] = request.GET.get(param, '')

    context = {
        'current_year': timezone.now().year,
        'utm_source': request.session.get('utm_source', request.GET.get('utm_source', '')),
        'utm_medium': request.session.get('utm_medium', request.GET.get('utm_medium', '')),
        'utm_campaign': request.session.get('utm_campaign', request.GET.get('utm_campaign', '')),
        'utm_term': request.session.get('utm_term', request.GET.get('utm_term', '')),
        'utm_content': request.session.get('utm_content', request.GET.get('utm_content', '')),
    }
    return render(request, 'landing.html', context)


def capture_lead(request):
    if request.method != 'POST':
        return redirect('landing')

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', '')

    # 1. Verificación Honeypot anti-spam
    honeypot = request.POST.get('website_hp', '').strip()
    if honeypot:
        # Si el bot rellenó el campo oculto, simular éxito silencioso sin guardar basura
        msg = "Gracias por tu interés. El equipo de Humm se pondrá en contacto contigo."
        if is_ajax:
            return JsonResponse({'success': True, 'message': msg})
        messages.success(request, msg)
        return redirect(reverse('landing') + '#contacto')

    # 2. Extracción de datos
    name = request.POST.get('name', '').strip()
    company_name = request.POST.get('company_name', '').strip()
    email = request.POST.get('email', '').strip()
    phone = request.POST.get('phone', '').strip()
    message = request.POST.get('message', '').strip()
    privacy_policy = request.POST.get('privacy_policy')

    # 3. Validación
    errors = {}
    if not name:
        errors['name'] = 'Por favor ingresa tu nombre.'
    if not company_name:
        errors['company_name'] = 'Por favor indica el nombre de tu emprendimiento o empresa.'
    if not email or '@' not in email or '.' not in email:
        errors['email'] = 'Por favor ingresa un correo electrónico válido.'
    if not phone:
        errors['phone'] = 'Por favor ingresa un número de teléfono o WhatsApp de contacto.'
    if not privacy_policy:
        errors['privacy_policy'] = 'Debes aceptar las políticas de privacidad para continuar.'

    if errors:
        if is_ajax:
            return JsonResponse({'success': False, 'errors': errors}, status=400)
        for field, err in errors.items():
            messages.error(request, err)
        return render(request, 'landing.html', {
            'form_data': request.POST,
            'current_year': timezone.now().year,
            'scroll_to_contact': True,
        })

    # 4. Detección de IP y UTMs
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        ip_address = x_forwarded.split(',')[0].strip()
    else:
        ip_address = request.META.get('REMOTE_ADDR')

    utm_source = request.POST.get('utm_source') or request.session.get('utm_source', '')
    utm_medium = request.POST.get('utm_medium') or request.session.get('utm_medium', '')
    utm_campaign = request.POST.get('utm_campaign') or request.session.get('utm_campaign', '')
    utm_term = request.POST.get('utm_term') or request.session.get('utm_term', '')
    utm_content = request.POST.get('utm_content') or request.session.get('utm_content', '')

    # 5. Persistencia en Base de Datos
    Lead.objects.create(
        name=name,
        company_name=company_name,
        email=email,
        phone=phone,
        message=message,
        privacy_accepted=True,
        source='landing_hummailing',
        utm_source=utm_source,
        utm_medium=utm_medium,
        utm_campaign=utm_campaign,
        utm_term=utm_term,
        utm_content=utm_content,
        ip_address=ip_address,
        status='pending'
    )

    success_msg = "Gracias por tu interés. El equipo de Humm se pondrá en contacto contigo."
    
    if is_ajax:
        return JsonResponse({'success': True, 'message': success_msg})

    messages.success(request, success_msg)
    return redirect(reverse('landing') + '#contacto')


@login_required

def dashboard(request):
    if request.user.is_humm_master_admin and not request.session.get('impersonate_org_id'):
        # Si es admin Humm y no está en soporte de ninguna org, redirigir al panel de administración de clientes
        return redirect('organizations:admin_dashboard')
        
    org = request.organization
    contacts_qs = Contact.objects.filter(organization=org) if org else Contact.objects.none()
    campaigns_qs = Campaign.objects.filter(organization=org) if org else Campaign.objects.none()
    opportunities_qs = Opportunity.objects.filter(organization=org) if org else Opportunity.objects.none()
    
    total_contacts = contacts_qs.count()
    active_contacts = contacts_qs.filter(status='active').count()
    total_campaigns = campaigns_qs.count()
    recent_campaigns = campaigns_qs.order_by('-created_at')[:5]
    scheduled_campaigns = campaigns_qs.filter(status='scheduled').order_by('scheduled_at')[:5]
    
    # Métricas de embudo
    total_delivered = TrackingEvent.objects.filter(campaign__organization=org, event_type='delivered').count() if org else 0
    total_opens = TrackingEvent.objects.filter(campaign__organization=org, event_type='open').count() if org else 0
    total_clicks = TrackingEvent.objects.filter(campaign__organization=org, event_type='click').count() if org else 0
    total_bounces = TrackingEvent.objects.filter(campaign__organization=org, event_type__startswith='bounce').count() if org else 0
    total_unsubs = TrackingEvent.objects.filter(campaign__organization=org, event_type='unsub').count() if org else 0
    total_opportunities = opportunities_qs.count()
    new_opportunities = opportunities_qs.filter(status='new').count()
    
    context = {
        'total_contacts': total_contacts,
        'active_contacts': active_contacts,
        'total_campaigns': total_campaigns,
        'recent_campaigns': recent_campaigns,
        'scheduled_campaigns': scheduled_campaigns,
        'total_delivered': total_delivered,
        'total_opens': total_opens,
        'total_clicks': total_clicks,
        'total_bounces': total_bounces,
        'total_unsubs': total_unsubs,
        'total_opportunities': total_opportunities,
        'new_opportunities': new_opportunities,
    }
    return render(request, 'core/dashboard.html', context)

@login_required
def change_password(request):
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password1 = request.POST.get('new_password1', '')
        new_password2 = request.POST.get('new_password2', '')
        
        if not request.user.check_password(current_password):
            messages.error(request, "La contraseña actual no es correcta.")
            return render(request, 'core/change_password.html')
            
        if len(new_password1) < 6:
            messages.error(request, "La nueva contraseña debe tener al menos 6 caracteres.")
            return render(request, 'core/change_password.html')
            
        if new_password1 != new_password2:
            messages.error(request, "Las contraseñas nuevas no coinciden.")
            return render(request, 'core/change_password.html')
            
        request.user.set_password(new_password1)
        request.user.must_change_password = False
        request.user.save()
        update_session_auth_hash(request, request.user)
        
        ActivityLog.objects.create(
            organization=request.organization,
            user=request.user,
            action="Cambio de Contraseña",
            details="El usuario actualizó su contraseña con éxito."
        )
        
        messages.success(request, "¡Tu contraseña ha sido actualizada exitosamente!")
        return redirect('dashboard')
        
    return render(request, 'core/change_password.html')

@login_required
def my_account(request):
    return render(request, 'core/my_account.html')
