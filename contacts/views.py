from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.core.paginator import Paginator
from .models import Contact, Tag, Segment
from organizations.models import SuppressionEntry, ActivityLog
from core.permissions import role_required

@login_required
def contact_list(request):
    org = request.organization
    query = request.GET.get('q', '').strip()
    tag_filter = request.GET.get('tag', '').strip()
    status_filter = request.GET.get('status', '').strip()
    
    contacts = Contact.objects.filter(organization=org).prefetch_related('tags').order_by('-created_at') if org else Contact.objects.none()
    
    if query:
        contacts = contacts.filter(
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(company__icontains=query) |
            Q(city__icontains=query)
        )
    if tag_filter:
        contacts = contacts.filter(tags__name=tag_filter)
    if status_filter:
        contacts = contacts.filter(status=status_filter)
        
    tags = Tag.objects.filter(organization=org).order_by('name') if org else Tag.objects.none()
    
    # Tamaño de página configurable (default 50 contactos)
    page_size_str = request.GET.get('page_size', '50')
    try:
        page_size = int(page_size_str)
        if page_size not in [25, 50, 100, 200]:
            page_size = 50
    except (ValueError, TypeError):
        page_size = 50

    paginator = Paginator(contacts, page_size)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    context = {
        'page_obj': page_obj,
        'tags': tags,
        'query': query,
        'tag_filter': tag_filter,
        'status_filter': status_filter,
        'page_size': page_size,
        'total_count': contacts.count() if hasattr(contacts, 'count') else 0,
    }
    return render(request, 'contacts/list.html', context)

@login_required
@role_required(['org_admin'])
def contact_create(request):
    org = request.organization
    if not org:
        messages.error(request, "No tienes una organización activa seleccionada.")
        return redirect('contacts:list')
        
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        company = request.POST.get('company', '').strip()
        phone = request.POST.get('phone', '').strip()
        job_title = request.POST.get('job_title', '').strip()
        industry = request.POST.get('industry', '').strip()
        region = request.POST.get('region', '').strip()
        city = request.POST.get('city', '').strip()
        source = request.POST.get('source', '').strip()
        
        if not email:
            messages.error(request, "El correo electrónico es obligatorio.")
            available_tags = Tag.objects.filter(organization=org).order_by('name')
            return render(request, 'contacts/create.html', {'available_tags': available_tags})
            
        # Verificar límite de contactos
        if Contact.objects.filter(organization=org).count() >= org.max_contacts:
            messages.error(request, f"Has alcanzado el límite máximo de {org.max_contacts} contactos permitidos para tu organización.")
            return redirect('contacts:list')
            
        contact, created = Contact.objects.get_or_create(
            organization=org,
            email=email,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'company': company,
                'phone': phone,
                'job_title': job_title,
                'industry': industry,
                'region': region,
                'city': city,
                'source': source,
            }
        )
        
        # Procesar etiquetas pre-existentes seleccionadas
        selected_tag_ids = request.POST.getlist('tags')
        if selected_tag_ids:
            tags_to_add = Tag.objects.filter(id__in=selected_tag_ids, organization=org)
            contact.tags.add(*tags_to_add)
            
        # Procesar nuevas etiquetas escritas por el usuario
        new_tags_str = request.POST.get('new_tags', '').strip()
        if new_tags_str:
            for name in [t.strip() for t in new_tags_str.split(',') if t.strip()]:
                tag_obj, _ = Tag.objects.get_or_create(organization=org, name=name)
                contact.tags.add(tag_obj)
                
        if created:
            messages.success(request, f"Contacto {email} creado con éxito.")
        else:
            messages.warning(request, f"El contacto {email} ya existía y sus etiquetas fueron actualizadas.")
            
        return redirect('contacts:list')
        
    available_tags = Tag.objects.filter(organization=org).order_by('name')
    return render(request, 'contacts/create.html', {'available_tags': available_tags})

@login_required
@role_required(['org_admin'])
def contact_delete(request, contact_id):
    org = request.organization
    if request.method == 'POST':
        contact = get_object_or_404(Contact, id=contact_id, organization=org)
        email = contact.email
        contact.delete()
        messages.success(request, f"Contacto {email} eliminado.")
    return redirect('contacts:list')

@login_required
@role_required(['org_admin'])
def contact_update(request, contact_id):
    org = request.organization
    contact = get_object_or_404(Contact, id=contact_id, organization=org)
    
    if request.method == 'POST':
        contact.email = request.POST.get('email', contact.email).strip().lower()
        contact.first_name = request.POST.get('first_name', '').strip()
        contact.last_name = request.POST.get('last_name', '').strip()
        contact.company = request.POST.get('company', '').strip()
        contact.phone = request.POST.get('phone', '').strip()
        contact.job_title = request.POST.get('job_title', '').strip()
        contact.industry = request.POST.get('industry', '').strip()
        contact.region = request.POST.get('region', '').strip()
        contact.city = request.POST.get('city', '').strip()
        contact.source = request.POST.get('source', '').strip()
        contact.status = request.POST.get('status', contact.status)
        contact.internal_notes = request.POST.get('internal_notes', '').strip()
        contact.save()
        
        # Procesar etiquetas: reiniciar y asignar seleccionadas + nuevas
        contact.tags.clear()
        
        # 1. Etiquetas pre-creadas seleccionadas
        selected_tag_ids = request.POST.getlist('tags')
        if selected_tag_ids:
            tags_to_add = Tag.objects.filter(id__in=selected_tag_ids, organization=org)
            contact.tags.add(*tags_to_add)
            
        # 2. Nuevas etiquetas escritas
        new_tags_str = request.POST.get('new_tags', '').strip()
        legacy_tags_str = request.POST.get('tags_string', '').strip()
        tags_input = new_tags_str or legacy_tags_str
        if tags_input:
            tag_names = [t.strip() for t in tags_input.split(',') if t.strip()]
            for name in tag_names:
                tag, _ = Tag.objects.get_or_create(organization=org, name=name)
                contact.tags.add(tag)
                
        messages.success(request, f"Contacto {contact.email} actualizado con éxito.")
        return redirect('contacts:list')
        
    available_tags = Tag.objects.filter(organization=org).order_by('name')
    contact_tag_ids = set(contact.tags.values_list('id', flat=True))
    tags_string = ", ".join([t.name for t in contact.tags.all()])
    return render(request, 'contacts/edit.html', {
        'contact': contact,
        'available_tags': available_tags,
        'contact_tag_ids': contact_tag_ids,
        'tags_string': tags_string
    })

import logging
from .utils import parse_imported_file

logger = logging.getLogger(__name__)

@login_required
@role_required(['org_admin', 'campaign_editor'])
def import_contacts(request):
    org = request.organization
    if not org:
        messages.error(request, "No tienes una organización activa seleccionada.")
        return redirect('contacts:list')
        
    if request.method == 'POST':
        if 'file' not in request.FILES:
            messages.error(request, "No se ha proporcionado ningún archivo para importar.")
            return redirect('contacts:import')
            
        uploaded_file = request.FILES['file']
        existing_tag_id = request.POST.get('existing_tag_id', '').strip()
        new_tag_name = request.POST.get('new_tag', '').strip()
        legacy_tag_name = request.POST.get('tag', '').strip()
        
        try:
            contacts_data, parse_error = parse_imported_file(uploaded_file)
            if parse_error:
                messages.error(request, parse_error)
                return redirect('contacts:import')
                
            created_count = 0
            updated_count = 0
            skipped_unsub_count = 0
            
            # Determinar etiqueta de asignación
            tag = None
            if existing_tag_id:
                tag = Tag.objects.filter(id=existing_tag_id, organization=org).first()
            elif new_tag_name:
                tag, _ = Tag.objects.get_or_create(organization=org, name=new_tag_name)
            elif legacy_tag_name:
                tag, _ = Tag.objects.get_or_create(organization=org, name=legacy_tag_name)
                
            # Obtener supresiones previas de la organización
            suppressed_emails = set(SuppressionEntry.objects.filter(
                Q(organization=org) | Q(organization__isnull=True)
            ).values_list('email', flat=True))
            
            # Obtener conteo actual
            current_count = Contact.objects.filter(organization=org).count()
            limit_reached = False
            
            for item in contacts_data:
                email = item['email']
                
                # Desuscripción previa respetada
                if email in suppressed_emails:
                    skipped_unsub_count += 1
                    continue
                    
                first_name = item.get('first_name', '').strip()
                last_name = item.get('last_name', '').strip()
                company = item.get('company', '').strip()
                phone = item.get('phone', '').strip()
                
                # Verificar límite de contactos
                if current_count >= org.max_contacts:
                    limit_reached = True
                    break
                    
                contact, created = Contact.objects.get_or_create(
                    organization=org,
                    email=email,
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'company': company,
                        'phone': phone,
                        'status': 'active',
                    }
                )
                
                if created:
                    created_count += 1
                    current_count += 1
                else:
                    # Actualizar campos no vacíos provistos en la importación
                    updated_fields = []
                    if first_name and contact.first_name != first_name:
                        contact.first_name = first_name
                        updated_fields.append('first_name')
                    if last_name and contact.last_name != last_name:
                        contact.last_name = last_name
                        updated_fields.append('last_name')
                    if company and contact.company != company:
                        contact.company = company
                        updated_fields.append('company')
                    if phone and contact.phone != phone:
                        contact.phone = phone
                        updated_fields.append('phone')
                    if updated_fields:
                        contact.save(update_fields=updated_fields)
                    updated_count += 1
                    
                if tag:
                    contact.tags.add(tag)
                    
            if limit_reached:
                messages.warning(
                    request, 
                    f"Se detuvo la importación porque tu organización alcanzó el límite de {org.max_contacts} contactos permitidos."
                )
                
            tag_info = f" con etiqueta '{tag.name}'" if tag else ""
            ActivityLog.objects.create(
                organization=org,
                user=request.user,
                action="Importación de Contactos",
                details=f"Importación ({uploaded_file.name}){tag_info}: {created_count} creados, {updated_count} actualizados, {skipped_unsub_count} omitidos por baja previa."
            )
            
            msg = f"¡Importación completada con éxito! Creados: {created_count}, Actualizados: {updated_count}."
            if tag:
                msg += f" Asignados a la etiqueta '{tag.name}'."
            if skipped_unsub_count > 0:
                msg += f" Omitidos por desuscripción previa: {skipped_unsub_count}."
            messages.success(request, msg)
            
        except Exception as e:
            logger.error(f"Error procesando importación de archivo {uploaded_file.name}: {e}", exc_info=True)
            messages.error(request, f"Error al procesar el archivo: {str(e)}")
            
        return redirect('contacts:import')
        
    tags = Tag.objects.filter(organization=org).annotate(contact_count=Count('contact')).order_by('name') if org else Tag.objects.none()
    return render(request, 'contacts/import.html', {'tags': tags})

# ==============================================================================
# GESTIÓN DE ETIQUETAS (CRUD)
# ==============================================================================

@login_required
@role_required(['org_admin', 'campaign_editor'])
def tag_list(request):
    org = request.organization
    if not org:
        messages.error(request, "No tienes una organización activa seleccionada.")
        return redirect('contacts:list')
        
    tags = Tag.objects.filter(organization=org).annotate(
        contact_count=Count('contact')
    ).order_by('name')
    
    return render(request, 'contacts/tag_list.html', {
        'tags': tags,
        'total_tags': tags.count(),
    })

@login_required
@role_required(['org_admin', 'campaign_editor'])
def tag_create(request):
    org = request.organization
    if not org:
        messages.error(request, "No tienes una organización activa seleccionada.")
        return redirect('contacts:list')
        
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, "El nombre de la etiqueta no puede estar vacío.")
            return redirect('contacts:tag_list')
            
        tag, created = Tag.objects.get_or_create(organization=org, name=name)
        if created:
            ActivityLog.objects.create(
                organization=org,
                user=request.user,
                action="Creación de Etiqueta",
                details=f"Etiqueta '{name}' creada con éxito."
            )
            messages.success(request, f"Etiqueta '{name}' creada con éxito.")
        else:
            messages.warning(request, f"La etiqueta '{name}' ya existe en tu organización.")
            
    return redirect('contacts:tag_list')

@login_required
@role_required(['org_admin', 'campaign_editor'])
def tag_update(request, tag_id):
    org = request.organization
    tag = get_object_or_404(Tag, id=tag_id, organization=org)
    
    if request.method == 'POST':
        new_name = request.POST.get('name', '').strip()
        if not new_name:
            messages.error(request, "El nombre de la etiqueta no puede estar vacío.")
            return redirect('contacts:tag_list')
            
        if new_name != tag.name:
            if Tag.objects.filter(organization=org, name=new_name).exclude(id=tag.id).exists():
                messages.error(request, f"Ya existe otra etiqueta llamada '{new_name}' en tu organización.")
                return redirect('contacts:tag_list')
                
            old_name = tag.name
            tag.name = new_name
            tag.save(update_fields=['name'])
            
            ActivityLog.objects.create(
                organization=org,
                user=request.user,
                action="Edición de Etiqueta",
                details=f"Etiqueta renombrada de '{old_name}' a '{new_name}'."
            )
            messages.success(request, f"Etiqueta actualizada a '{new_name}' exitosamente.")
            
    return redirect('contacts:tag_list')

@login_required
@role_required(['org_admin', 'campaign_editor'])
def tag_delete(request, tag_id):
    org = request.organization
    tag = get_object_or_404(Tag, id=tag_id, organization=org)
    
    if request.method == 'POST':
        tag_name = tag.name
        count = tag.contact_set.count()
        tag.delete()
        
        ActivityLog.objects.create(
            organization=org,
            user=request.user,
            action="Eliminación de Etiqueta",
            details=f"Etiqueta '{tag_name}' eliminada (se desvinculó de {count} contactos)."
        )
        messages.success(request, f"Etiqueta '{tag_name}' eliminada (se desvinculó de {count} contactos).")
        
    return redirect('contacts:tag_list')


