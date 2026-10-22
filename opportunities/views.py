import uuid
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import HttpResponseRedirect
from django.db.models import Q
from django.core.paginator import Paginator

from .models import Opportunity
from campaigns.models import CampaignLink, TrackingEvent, Campaign
from contacts.models import Contact
from organizations.models import SuppressionEntry, ActivityLog
from core.models import User

from core.permissions import role_required, block_viewer_mutations
from core.security import validate_unsubscribe_token

logger = logging.getLogger(__name__)

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
@block_viewer_mutations
def opportunity_detail(request, opp_id):
    org = request.organization
    opportunity = get_object_or_404(Opportunity, id=opp_id, organization=org)
    org_users = User.objects.filter(organization=org) if org else User.objects.none()
    
    if request.method == 'POST':
        opportunity.status = request.POST.get('status', opportunity.status)
        opportunity.priority = request.POST.get('priority', opportunity.priority)
        assigned_id = request.POST.get('assigned_to')
        
        # Validar estrictamente que el usuario pertenezca a la misma organización
        if assigned_id:
            assigned_user = User.objects.filter(id=assigned_id, organization=org).first()
            if not assigned_user:
                messages.error(request, "El usuario asignado no pertenece a tu organización.")
                return redirect('opportunities:detail', opp_id=opportunity.id)
            opportunity.assigned_to = assigned_user
        else:
            opportunity.assigned_to = None
            
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

@login_required
@role_required(['org_admin', 'campaign_editor'])
def opportunity_delete(request, opp_id):
    org = request.organization
    if request.method == 'POST':
        if getattr(request.user, 'is_humm_master_admin', False) and not org:
            opportunity = get_object_or_404(Opportunity, id=opp_id)
        else:
            opportunity = get_object_or_404(Opportunity, id=opp_id, organization=org)
            
        title = opportunity.title
        opp_org = opportunity.organization
        contact_name = f"{opportunity.contact.first_name} {opportunity.contact.last_name}".strip() or opportunity.contact.email
        opportunity.delete()
        
        if opp_org:
            ActivityLog.objects.create(
                user=request.user,
                organization=opp_org,
                action="Eliminación de Oportunidad",
                details=f"Se eliminó la oportunidad comercial '{title}' ({contact_name})."
            )
        messages.success(request, f"Oportunidad '{title}' eliminada exitosamente.")
    return redirect('opportunities:list')

@login_required
@role_required(['org_admin', 'campaign_editor'])
def opportunity_bulk_delete(request):
    org = request.organization
    if request.method == 'POST':
        selected_ids = request.POST.getlist('selected_ids')
        if getattr(request.user, 'is_humm_master_admin', False) and not org:
            qs = Opportunity.objects.filter(id__in=selected_ids)
        else:
            qs = Opportunity.objects.filter(id__in=selected_ids, organization=org)
            
        count = qs.count()
        if count > 0:
            qs.delete()
            if org:
                ActivityLog.objects.create(
                    user=request.user,
                    organization=org,
                    action="Eliminación Masiva de Oportunidades",
                    details=f"Se eliminaron {count} oportunidades comerciales (leads)."
                )
            messages.success(request, f"Se eliminaron {count} oportunidades seleccionadas exitosamente.")
        else:
            messages.warning(request, "No se seleccionó ninguna oportunidad para eliminar.")
    return redirect('opportunities:list')


def redirect_tracked_link(request, token):
    """
    Ruta pública para registrar clics en enlaces de campañas y crear Oportunidades ante enlaces de conversión.
    """
    link = get_object_or_404(CampaignLink, token=token)
    contact_id = request.GET.get('c')
    contact_email = request.GET.get('e')
    
    contact = None
    if contact_id:
        contact = Contact.objects.filter(id=contact_id, organization=link.campaign.organization).first()
    elif contact_email:
        contact = Contact.objects.filter(email__iexact=contact_email.strip(), organization=link.campaign.organization).first()
        
    # Registrar evento de clic (evitando duplicados)
    if contact:
        if not TrackingEvent.objects.filter(campaign=link.campaign, contact=contact, event_type='click', link=link).exists():
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
    Ruta pública para cancelar suscripción con token criptográfico firmado sin PII.
    - GET: Valida token y muestra pantalla de confirmación (no muta estado, anti-scanners).
    - POST: Valida token, exige CSRF, ejecuta la baja y agrega a SuppressionEntry.
    """
    contact, error_msg = validate_unsubscribe_token(token)
    if not contact:
        return render(request, 'opportunities/unsubscribe_invalid.html', {'error': error_msg}, status=400)
        
    if request.method == 'POST':
        # Proceder con la desuscripción efectiva
        contact.status = 'unsubscribed'
        contact.save(update_fields=['status'])
        
        # Registrar en SuppressionEntry exclusivamente para la organización del contacto
        SuppressionEntry.objects.get_or_create(
            organization=contact.organization,
            email=contact.email,
            defaults={'reason': 'unsub'}
        )

        # Sincronizar baja con Resend si está disponible
        if getattr(settings, 'RESEND_API_KEY', None):
            try:
                import resend
                resend.api_key = settings.RESEND_API_KEY
                resend.Contacts.update({
                    'email': contact.email,
                    'unsubscribed': True
                })
            except Exception as res_unsub_err:
                logger.warning(f"Aviso: no se pudo sincronizar baja en Resend: {res_unsub_err}")
        
        # Registrar evento de seguimiento si se especifica la campaña
        campaign_id = request.POST.get('camp') or request.GET.get('camp')
        if campaign_id:
            campaign = Campaign.objects.filter(id=campaign_id, organization=contact.organization).first()
            if campaign:
                TrackingEvent.objects.create(
                    campaign=campaign,
                    contact=contact,
                    event_type='unsub',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
        return render(request, 'opportunities/unsubscribe_success.html', {'contact': contact})
        
    # GET: Pantalla de confirmación (anti-scanners no modifican estado)
    return render(request, 'opportunities/unsubscribe_confirm.html', {
        'contact': contact,
        'token': token,
        'camp': request.GET.get('camp', '')
    })

