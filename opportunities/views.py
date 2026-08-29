import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.db.models import Q
from django.core.paginator import Paginator

from .models import Opportunity
from campaigns.models import CampaignLink, TrackingEvent, Campaign
from contacts.models import Contact
from organizations.models import SuppressionEntry, ActivityLog
from core.models import User

@login_required
def opportunity_list(request):
    org = request.organization
    status = request.GET.get('status', '').strip()
    query = request.GET.get('q', '').strip()
    
    opportunities = Opportunity.objects.filter(organization=org).select_related('contact', 'campaign', 'assigned_to').order_by('-created_at') if org else Opportunity.objects.none()
    
    if status:
        opportunities = opportunities.filter(status=status)
    if query:
        opportunities = opportunities.filter(
            Q(title__icontains=query) | 
            Q(contact__first_name__icontains=query) | 
            Q(contact__last_name__icontains=query) | 
            Q(contact__email__icontains=query) |
            Q(contact__company__icontains=query)
        )
        
    paginator = Paginator(opportunities, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    # Conteo por estado
    status_counts = {}
    for code, label in Opportunity.STATUS_CHOICES:
        count = Opportunity.objects.filter(organization=org, status=code).count() if org else 0
        status_counts[code] = {'label': label, 'count': count}
        
    context = {
        'page_obj': page_obj,
        'status_counts': status_counts,
        'current_status': status,
        'query': query,
    }
    return render(request, 'opportunities/list.html', context)

@login_required
def opportunity_detail(request, opp_id):
    org = request.organization
    opportunity = get_object_or_404(Opportunity, id=opp_id, organization=org)
    org_users = User.objects.filter(organization=org) if org else User.objects.none()
    
    if request.method == 'POST':
        opportunity.status = request.POST.get('status', opportunity.status)
        opportunity.priority = request.POST.get('priority', opportunity.priority)
        assigned_id = request.POST.get('assigned_to')
        opportunity.assigned_to = User.objects.filter(id=assigned_id).first() if assigned_id else None
        opportunity.notes = request.POST.get('notes', '').strip()
        opportunity.next_action = request.POST.get('next_action', '').strip()
        follow_up = request.POST.get('follow_up_date', '').strip()
        opportunity.follow_up_date = follow_up if follow_up else None
        opportunity.save()
        
        messages.success(request, f"Oportunidad '{opportunity.title}' actualizada.")
        return redirect('opportunities:list')
        
    context = {
        'opportunity': opportunity,
        'org_users': org_users,
        'status_choices': Opportunity.STATUS_CHOICES,
        'priority_choices': Opportunity.PRIORITY_CHOICES,
    }
    return render(request, 'opportunities/detail.html', context)

def redirect_tracked_link(request, token):
    """
    Ruta pública para registrar clics en enlaces de campañas y crear Oportunidades ante enlaces de conversión.
    """
    link = get_object_or_404(CampaignLink, token=token)
    contact_id = request.GET.get('c')
    
    contact = None
    if contact_id:
        contact = Contact.objects.filter(id=contact_id, organization=link.campaign.organization).first()
        
    # Registrar evento de clic
    if contact:
        TrackingEvent.objects.create(
            campaign=link.campaign,
            contact=contact,
            event_type='click',
            link=link,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Si el enlace es de tipo 'conversión', creamos o actualizamos la Oportunidad Comercial
        if link.link_type == 'conversion':
            topic = link.service_interest or "Interés general en servicio"
            title = f"Interés de {contact.first_name or contact.email} - {topic}"
            
            # Evitar duplicados recientes para el mismo contacto y link
            opp, created = Opportunity.objects.get_or_create(
                organization=link.campaign.organization,
                contact=contact,
                campaign=link.campaign,
                link=link,
                defaults={
                    'title': title,
                    'interest_topic': topic,
                    'status': 'new',
                    'priority': 'high',
                    'notes': f"Generado automáticamente tras hacer clic en: {link.original_url}"
                }
            )
            
    return HttpResponseRedirect(link.original_url)

def unsubscribe_contact(request, token):
    """
    Ruta pública para cancelar suscripción.
    """
    # Token contiene org_id y contact_id
    contact_id = request.GET.get('c')
    campaign_id = request.GET.get('camp')
    
    contact = Contact.objects.filter(id=contact_id).first() if contact_id else None
    campaign = Campaign.objects.filter(id=campaign_id).first() if campaign_id else None
    
    if contact:
        contact.status = 'unsubscribed'
        contact.save(update_fields=['status'])
        
        # Registrar en la lista de supresiones
        SuppressionEntry.objects.get_or_create(
            organization=contact.organization,
            email=contact.email,
            defaults={'reason': 'unsub'}
        )
        
        if campaign:
            TrackingEvent.objects.create(
                campaign=campaign,
                contact=contact,
                event_type='unsub',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
        return render(request, 'opportunities/unsubscribe_success.html', {'contact': contact})
        
    return render(request, 'opportunities/unsubscribe_success.html', {'contact': None})
