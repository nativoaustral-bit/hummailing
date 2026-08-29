from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from contacts.models import Contact
from campaigns.models import Campaign, TrackingEvent
from opportunities.models import Opportunity
from organizations.models import ActivityLog

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
