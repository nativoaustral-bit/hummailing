import secrets
import string
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import resend

from .models import Organization, ActivityLog, BroadcastAnnouncement
from core.models import User, Lead
from contacts.models import Contact
from campaigns.models import Campaign, TrackingEvent

logger = logging.getLogger(__name__)

def is_humm_admin_check(user):
    return user.is_authenticated and user.is_humm_master_admin

@login_required
@user_passes_test(is_humm_admin_check)
def admin_dashboard(request):
    total_orgs = Organization.objects.count()
    active_orgs = Organization.objects.filter(status='active').count()
    total_users = User.objects.count()
    total_contacts = Contact.objects.count()
    total_campaigns = Campaign.objects.count()
    total_emails_sent = TrackingEvent.objects.filter(event_type='sent').count()
    
    # Métricas y prospectos de las Landings
    total_leads = Lead.objects.count()
    pending_leads = Lead.objects.filter(status='pending').count()
    recent_leads = Lead.objects.order_by('-created_at')[:5]
    
    recent_activity = ActivityLog.objects.select_related('organization', 'user').order_by('-timestamp')[:10]
    recent_orgs = Organization.objects.order_by('-created_at')[:5]
    recent_broadcasts = BroadcastAnnouncement.objects.order_by('-sent_at')[:3]
    
    context = {
        'total_orgs': total_orgs,
        'active_orgs': active_orgs,
        'total_users': total_users,
        'total_contacts': total_contacts,
        'total_campaigns': total_campaigns,
        'total_emails_sent': total_emails_sent,
        'total_leads': total_leads,
        'pending_leads': pending_leads,
        'recent_leads': recent_leads,
        'recent_activity': recent_activity,
        'recent_orgs': recent_orgs,
        'recent_broadcasts': recent_broadcasts,
    }
    return render(request, 'organizations/admin_dashboard.html', context)


@login_required
@user_passes_test(is_humm_admin_check)
def organization_list(request):
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    
    orgs = Organization.objects.annotate(
        user_count=Count('users', distinct=True),
        contact_count=Count('contacts', distinct=True),
        campaign_count=Count('campaigns', distinct=True)
    ).order_by('-created_at')
    
    if query:
        orgs = orgs.filter(Q(name__icontains=query) | Q(trade_name__icontains=query) | Q(rut__icontains=query) | Q(email__icontains=query))
    if status:
        orgs = orgs.filter(status=status)
        
    paginator = Paginator(orgs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'query': query,
        'status': status,
    }
    return render(request, 'organizations/organization_list.html', context)

@login_required
@user_passes_test(is_humm_admin_check)
def organization_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        trade_name = request.POST.get('trade_name', '').strip()
        rut = request.POST.get('rut', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        website = request.POST.get('website', '').strip()
        if website and not (website.startswith('http://') or website.startswith('https://')):
            website = f'https://{website}'
        
        default_sender_name = request.POST.get('default_sender_name', '').strip() or 'Hummailing'
        default_sender_email = request.POST.get('default_sender_email', '').strip() or 'hola@humm.cl'
        default_reply_to = request.POST.get('default_reply_to', '').strip() or 'hola@humm.cl'
        
        max_contacts = int(request.POST.get('max_contacts', 1000) or 1000)
        monthly_email_limit = int(request.POST.get('monthly_email_limit', 5000) or 5000)
        notes = request.POST.get('notes', '').strip()
        
        if not name or not email:
            messages.error(request, "El nombre de la organización y el correo son obligatorios.")
            return render(request, 'organizations/organization_form.html', {'is_edit': False})
            
        org = Organization.objects.create(
            name=name,
            trade_name=trade_name,
            rut=rut,
            email=email,
            phone=phone,
            website=website,
            default_sender_name=default_sender_name,
            default_sender_email=default_sender_email,
            default_reply_to=default_reply_to,
            max_contacts=max_contacts,
            monthly_email_limit=monthly_email_limit,
            notes=notes,
            account_manager=request.user
        )
        
        ActivityLog.objects.create(
            organization=org,
            user=request.user,
            action="Creación de Organización",
            details=f"Se creó la organización '{org.name}' ({org.email}) con límite de {max_contacts} contactos."
        )
        
        messages.success(request, f"Organización '{org.name}' creada exitosamente.")
        return redirect('organizations:organization_list')
        
    return render(request, 'organizations/organization_form.html', {'is_edit': False})

@login_required
@user_passes_test(is_humm_admin_check)
def organization_edit(request, org_id):
    org = get_object_or_404(Organization, id=org_id)
    
    if request.method == 'POST':
        org.name = request.POST.get('name', org.name).strip()
        org.trade_name = request.POST.get('trade_name', '').strip()
        org.rut = request.POST.get('rut', '').strip()
        org.email = request.POST.get('email', org.email).strip()
        org.phone = request.POST.get('phone', '').strip()
        website = request.POST.get('website', '').strip()
        if website and not (website.startswith('http://') or website.startswith('https://')):
            website = f'https://{website}'
        org.website = website
        
        org.default_sender_name = request.POST.get('default_sender_name', org.default_sender_name).strip()
        org.default_sender_email = request.POST.get('default_sender_email', org.default_sender_email).strip()
        org.default_reply_to = request.POST.get('default_reply_to', org.default_reply_to).strip()
        
        org.status = request.POST.get('status', org.status)
        org.max_contacts = int(request.POST.get('max_contacts', org.max_contacts) or 1000)
        org.monthly_email_limit = int(request.POST.get('monthly_email_limit', org.monthly_email_limit) or 5000)
        org.notes = request.POST.get('notes', '').strip()
        org.save()
        
        ActivityLog.objects.create(
            organization=org,
            user=request.user,
            action="Edición de Organización",
            details=f"Se actualizaron los parámetros y límites de '{org.name}' ({org.max_contacts} contactos / {org.monthly_email_limit} envíos)."
        )
        
        messages.success(request, f"Organización '{org.name}' actualizada con éxito.")
        return redirect('organizations:organization_list')
        
    return render(request, 'organizations/organization_form.html', {'org': org, 'is_edit': True})

@login_required
@user_passes_test(is_humm_admin_check)
def organization_toggle_status(request, org_id):
    org = get_object_or_404(Organization, id=org_id)
    if request.method == 'POST':
        if org.status == 'active':
            org.status = 'suspended'
            messages.warning(request, f"La organización '{org.name}' ha sido SUSPENDIDA.")
        else:
            org.status = 'active'
            messages.success(request, f"La organización '{org.name}' ha sido ACTIVADA.")
        org.save(update_fields=['status'])
        
        ActivityLog.objects.create(
            organization=org,
            user=request.user,
            action="Cambio de Estado",
            details=f"Se cambió el estado de '{org.name}' a '{org.get_status_display()}'."
        )
    return redirect('organizations:organization_list')

@login_required
@user_passes_test(is_humm_admin_check)
def organization_delete(request, org_id):
    org = get_object_or_404(Organization, id=org_id)
    if org.name == "Humm Ecosistema":
        messages.error(request, "No es posible eliminar la organización matriz 'Humm Ecosistema'.")
        return redirect('organizations:organization_list')
        
    if request.method == 'POST':
        org_name = org.name
        org.delete()
        
        ActivityLog.objects.create(
            user=request.user,
            action="Eliminación de Organización",
            details=f"Se eliminó permanentemente la organización '{org_name}' y sus datos asociados."
        )
        
        messages.success(request, f"La organización '{org_name}' ha sido eliminada permanentemente.")
    return redirect('organizations:organization_list')

@login_required
@user_passes_test(is_humm_admin_check)
def impersonate_organization(request, org_id):
    org = get_object_or_404(Organization, id=org_id)
    request.session['impersonate_org_id'] = org.id
    
    ActivityLog.objects.create(
        organization=org,
        user=request.user,
        action="Ingreso a Soporte",
        details=f"El administrador Humm {request.user.username} ingresó al contexto de soporte de '{org.name}'."
    )
    
    messages.info(request, f"Ahora estás en modo soporte visualizando la organización: {org.name}")
    return redirect('dashboard')

@login_required
def exit_support_mode(request):
    if 'impersonate_org_id' in request.session:
        del request.session['impersonate_org_id']
        messages.success(request, "Has salido del modo soporte y regresado al panel Humm.")
    return redirect('organizations:admin_dashboard')

@login_required
@user_passes_test(is_humm_admin_check)
def user_list(request):
    query = request.GET.get('q', '').strip()
    org_id = request.GET.get('org_id', '').strip()
    
    users = User.objects.select_related('organization').order_by('-date_joined')
    
    if query:
        users = users.filter(Q(username__icontains=query) | Q(email__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query))
    if org_id:
        users = users.filter(organization_id=org_id)
        
    organizations = Organization.objects.order_by('name')
    paginator = Paginator(users, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    context = {
        'page_obj': page_obj,
        'organizations': organizations,
        'query': query,
        'org_id': org_id,
    }
    return render(request, 'organizations/user_list.html', context)

@login_required
@user_passes_test(is_humm_admin_check)
def user_create(request):
    organizations = Organization.objects.filter(status='active').order_by('name')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip().lower()
        email = request.POST.get('email', '').strip().lower()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        role = request.POST.get('role', 'org_admin')
        org_id = request.POST.get('organization')
        
        # Generar o tomar contraseña (alfabeto sin caracteres ambiguos como 0/O o 1/l/I)
        password_type = request.POST.get('password_type', 'auto')
        if password_type == 'auto':
            # Caracteres 100% legibles sin ambigüedad
            chars = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!#$"
            temp_password = ''.join(secrets.choice(chars) for _ in range(10))
        else:
            temp_password = request.POST.get('custom_password', '').strip()
            
        if not username or not email or not temp_password:
            messages.error(request, "Usuario, correo y contraseña son requeridos.")
            return render(request, 'organizations/user_form.html', {'organizations': organizations})
            
        if User.objects.filter(username=username).exists():
            messages.error(request, f"El nombre de usuario '{username}' ya está en uso.")
            return render(request, 'organizations/user_form.html', {'organizations': organizations})
            
        org = Organization.objects.filter(id=org_id).first() if org_id else None
        if role != 'humm_admin' and not org:
            messages.error(request, "Los usuarios de clientes deben estar asociados a una organización.")
            return render(request, 'organizations/user_form.html', {'organizations': organizations})
            
        user = User.objects.create_user(
            username=username,
            email=email,
            password=temp_password,
            first_name=first_name,
            last_name=last_name,
            role=role,
            organization=org,
            phone=phone,
            must_change_password=True
        )
        
        # Despachar correo automático de bienvenida con credenciales
        if user.email:
            try:
                email_html = render_to_string('emails/welcome_user.html', {
                    'user': user,
                    'temp_password': temp_password,
                    'request': request,
                })
                email_text = f"""¡Te damos la bienvenida a Hummailing!

Tu cuenta de acceso para {user.organization.name if user.organization else 'tu organización'} ha sido creada exitosamente.

Tus credenciales de inicio:
- Usuario: {user.username}
- Clave Temporal: {temp_password}
- Portal Web: https://mailing.humm.cl/accounts/login/

Al ingresar por primera vez con tu clave temporal, el sistema te solicitará definir tu contraseña personal y definitiva."""

                send_mail(
                    subject="¡Bienvenido a Hummailing! — Tus credenciales de acceso",
                    message=email_text,
                    from_email="Hummailing <hola@humm.cl>",
                    recipient_list=[user.email],
                    html_message=email_html,
                    fail_silently=False
                )
                logger.info(f"Correo de bienvenida enviado exitosamente a {user.email}")
            except Exception as e:
                logger.error(f"Error al enviar correo de bienvenida a {user.email}: {e}")

        ActivityLog.objects.create(
            organization=org,
            user=request.user,
            action="Creación de Usuario",
            details=f"Se creó el usuario '{user.username}' ({user.email}) con rol '{user.get_role_display()}'."
        )
        
        return render(request, 'organizations/user_created_success.html', {
            'created_user': user,
            'temp_password': temp_password,
        })
        
    return render(request, 'organizations/user_form.html', {'organizations': organizations})

@login_required
@user_passes_test(is_humm_admin_check)
def user_reset_password(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        chars = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!#$"
        temp_password = ''.join(secrets.choice(chars) for _ in range(10))
        
        target_user.set_password(temp_password)
        target_user.must_change_password = True
        target_user.save()
        
        # Enviar correo al usuario con su nueva clave temporal
        if target_user.email:
            try:
                email_html = render_to_string('emails/reset_user_password.html', {
                    'user': target_user,
                    'temp_password': temp_password,
                    'request': request,
                })
                email_text = f"""Hola {target_user.first_name or target_user.username},

Se ha generado una nueva contraseña temporal para tu cuenta en Hummailing:

- Usuario: {target_user.username}
- Nueva Clave Temporal: {temp_password}
- Portal Web: https://mailing.humm.cl/accounts/login/

La plataforma te solicitará cambiar esta clave al iniciar sesión."""

                send_mail(
                    subject="Nueva clave temporal de acceso — Hummailing",
                    message=email_text,
                    from_email="Hummailing <hola@humm.cl>",
                    recipient_list=[target_user.email],
                    html_message=email_html,
                    fail_silently=False
                )
                logger.info(f"Correo de clave temporal enviado a {target_user.email}")
            except Exception as e:
                logger.error(f"Error al enviar clave temporal a {target_user.email}: {e}")

        ActivityLog.objects.create(
            organization=target_user.organization,
            user=request.user,
            action="Restablecimiento de Contraseña",
            details=f"Se restableció la contraseña temporal para el usuario '{target_user.username}'."
        )
        
        return render(request, 'organizations/user_reset_success.html', {
            'target_user': target_user,
            'temp_password': temp_password,
        })
        
    return render(request, 'organizations/user_reset_confirm.html', {'target_user': target_user})

@login_required
@user_passes_test(is_humm_admin_check)
def user_toggle_active(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    if target_user == request.user:
        messages.error(request, "No puedes desactivar tu propia cuenta.")
        return redirect('organizations:user_list')
        
    if request.method == 'POST':
        target_user.is_active = not target_user.is_active
        target_user.save(update_fields=['is_active'])
        status_str = "ACTIVADO" if target_user.is_active else "DESACTIVADO"
        messages.info(request, f"El usuario '{target_user.username}' ha sido {status_str}.")
    return redirect('organizations:user_list')

@login_required
@user_passes_test(is_humm_admin_check)
def user_delete(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    if target_user == request.user:
        messages.error(request, "No puedes eliminar tu propia cuenta de administrador.")
        return redirect('organizations:user_list')
        
    if request.method == 'POST':
        username = target_user.username
        target_user.delete()
        ActivityLog.objects.create(
            user=request.user,
            action="Eliminación de Usuario",
            details=f"Se eliminó permanentemente el usuario '{username}'."
        )
        messages.success(request, f"El usuario '{username}' ha sido eliminado.")
    return redirect('organizations:user_list')

@login_required
@user_passes_test(is_humm_admin_check)
def activity_log_list(request):
    logs = ActivityLog.objects.select_related('organization', 'user').order_by('-timestamp')
    paginator = Paginator(logs, 30)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'organizations/activity_logs.html', {'page_obj': page_obj})

@login_required
@user_passes_test(is_humm_admin_check)
def broadcast_announcement(request):
    """
    Permite al Administrador Humm redactar y enviar comunicados masivos a los administradores de organizaciones.
    """
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        target_audience = request.POST.get('target_audience', 'all_active_orgs')
        
        if not subject or not message:
            messages.error(request, "El asunto y el contenido del comunicado son requeridos.")
            return render(request, 'organizations/broadcast_form.html')
            
        # Determinar destinatarios
        if target_audience == 'all_active_orgs':
            recipients = list(User.objects.filter(
                organization__status='active', 
                role='org_admin',
                is_active=True
            ).values_list('email', flat=True))
            # Agregar correos principales de las organizaciones por seguridad
            org_emails = list(Organization.objects.filter(status='active').values_list('email', flat=True))
            recipients = list(set(recipients + org_emails))
        else:
            recipients = list(User.objects.filter(is_active=True).values_list('email', flat=True))
            
        recipients = [e for e in recipients if e and '@' in e]
        
        # Despachar vía Resend
        resend.api_key = settings.RESEND_API_KEY
        success_count = 0
        
        email_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">
            <div style="background-color: #173960; color: #ffffff; padding: 24px; text-align: center;">
                <h1 style="font-size: 20px; font-weight: bold; margin: 0; text-transform: uppercase;">HUMMAILING — COMUNICADO OFICIAL</h1>
                <p style="font-size: 11px; color: #99c5d7; margin-top: 4px;">Información de servicio de Humm</p>
            </div>
            <div style="padding: 32px; color: #334155; font-size: 15px; line-height: 1.6;">
                {message.replace(chr(10), '<br>')}
            </div>
            <div style="background-color: #f8fafc; padding: 20px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0;">
                <p style="margin: 0;">Recibes este mensaje como administrador de tu cuenta en Hummailing.</p>
            </div>
        </div>
        """
        
        for email in recipients:
            try:
                resend.Emails.send({
                    "from": "Hummailing <hola@humm.cl>",
                    "to": email,
                    "subject": f"[COMUNICADO] {subject}",
                    "html": email_html,
                    "reply_to": "hola@humm.cl"
                })
                success_count += 1
            except Exception as e:
                logger.error(f"Error sending broadcast to {email}: {e}")
                
        announcement = BroadcastAnnouncement.objects.create(
            title=title or subject,
            subject=subject,
            message=message,
            target_audience=target_audience,
            recipients_count=len(recipients),
            sent_by=request.user
        )
        
        ActivityLog.objects.create(
            user=request.user,
            action="Comunicado Masivo",
            details=f"Se envió el comunicado '{subject}' a {len(recipients)} destinatarios de organizaciones."
        )
        
        messages.success(request, f"Comunicado despachado con éxito a {len(recipients)} destinatarios.")
        return redirect('organizations:broadcast_list')
        
    return render(request, 'organizations/broadcast_form.html')

@login_required
@user_passes_test(is_humm_admin_check)
def broadcast_list(request):
    broadcasts = BroadcastAnnouncement.objects.order_by('-sent_at')
    return render(request, 'organizations/broadcast_list.html', {'broadcasts': broadcasts})


# ==============================================================================
# GESTIÓN DE LEADS Y PROSPECTOS DE LANDINGS EN PANEL MASTER HUMM
# ==============================================================================

@login_required
@user_passes_test(is_humm_admin_check)
def lead_list(request):
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    source = request.GET.get('source', '').strip()
    
    leads = Lead.objects.all().order_by('-created_at')
    
    if status:
        leads = leads.filter(status=status)
    if source:
        leads = leads.filter(source=source)
    if query:
        leads = leads.filter(
            Q(name__icontains=query) |
            Q(company_name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(message__icontains=query) |
            Q(notes__icontains=query)
        )
        
    total_leads = Lead.objects.count()
    pending_leads = Lead.objects.filter(status='pending').count()
    contacted_leads = Lead.objects.filter(status='contacted').count()
    converted_leads = Lead.objects.filter(status='converted').count()
    
    # Fuentes distintas registradas para el filtro
    sources = Lead.objects.values_list('source', flat=True).distinct()
    
    paginator = Paginator(leads, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    context = {
        'page_obj': page_obj,
        'total_leads': total_leads,
        'pending_leads': pending_leads,
        'contacted_leads': contacted_leads,
        'converted_leads': converted_leads,
        'sources': sources,
        'current_status': status,
        'current_source': source,
        'query': query,
    }
    return render(request, 'organizations/lead_list.html', context)


@login_required
@user_passes_test(is_humm_admin_check)
def lead_detail(request, lead_id):
    lead = get_object_or_404(Lead, id=lead_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status', lead.status)
        new_notes = request.POST.get('notes', lead.notes)
        
        lead.status = new_status
        lead.notes = new_notes
        lead.save()
        
        ActivityLog.objects.create(
            user=request.user,
            action="Actualización de Prospecto",
            details=f"Se actualizó el estado del lead {lead.name} ({lead.company_name}) a '{lead.get_status_display()}'."
        )
        
        messages.success(request, f"Prospecto {lead.name} actualizado con éxito.")
        return redirect('organizations:lead_detail', lead_id=lead.id)
        
    context = {
        'lead': lead,
    }
    return render(request, 'organizations/lead_detail.html', context)


@login_required
@user_passes_test(is_humm_admin_check)
def lead_delete(request, lead_id):
    lead = get_object_or_404(Lead, id=lead_id)
    if request.method == 'POST':
        name = lead.name
        company = lead.company_name
        lead.delete()
        
        ActivityLog.objects.create(
            user=request.user,
            action="Eliminación de Prospecto",
            details=f"Se eliminó el lead {name} ({company})."
        )
        messages.success(request, f"Prospecto {name} eliminado correctamente.")
        return redirect('organizations:lead_list')
        
    return redirect('organizations:lead_detail', lead_id=lead_id)

