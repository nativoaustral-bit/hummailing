from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator
import pandas as pd
from .models import Contact, Tag, Segment
from organizations.models import SuppressionEntry, ActivityLog

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
    
    paginator = Paginator(contacts, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    context = {
        'page_obj': page_obj,
        'tags': tags,
        'query': query,
        'tag_filter': tag_filter,
        'status_filter': status_filter,
        'total_count': contacts.count() if hasattr(contacts, 'count') else 0,
    }
    return render(request, 'contacts/list.html', context)

@login_required
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
            return render(request, 'contacts/create.html')
            
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
        if created:
            messages.success(request, f"Contacto {email} creado con éxito.")
        else:
            messages.warning(request, f"El contacto {email} ya existe en tu organización.")
            
        return redirect('contacts:list')
        
    return render(request, 'contacts/create.html')

@login_required
def contact_delete(request, contact_id):
    org = request.organization
    if request.method == 'POST':
        contact = get_object_or_404(Contact, id=contact_id, organization=org)
        email = contact.email
        contact.delete()
        messages.success(request, f"Contacto {email} eliminado.")
    return redirect('contacts:list')

@login_required
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
        
        # Procesar etiquetas
        tags_str = request.POST.get('tags_string', '')
        contact.tags.clear()
        if tags_str:
            tag_names = [t.strip() for t in tags_str.split(',') if t.strip()]
            for name in tag_names:
                tag, _ = Tag.objects.get_or_create(organization=org, name=name)
                contact.tags.add(tag)
                
        messages.success(request, f"Contacto {contact.email} actualizado.")
        return redirect('contacts:list')
        
    tags_string = ", ".join([t.name for t in contact.tags.all()])
    return render(request, 'contacts/edit.html', {'contact': contact, 'tags_string': tags_string})

@login_required
def import_contacts(request):
    org = request.organization
    if not org:
        messages.error(request, "No tienes una organización activa seleccionada.")
        return redirect('contacts:list')
        
    if request.method == 'POST':
        if 'file' not in request.FILES:
            messages.error(request, "No se ha proporcionado ningún archivo.")
            return redirect('contacts:import')
            
        file = request.FILES['file']
        tag_name = request.POST.get('tag', '').strip()
        
        try:
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            elif file.name.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(file)
            else:
                messages.error(request, "Formato no soportado. Sube un archivo CSV o Excel.")
                return redirect('contacts:import')
                
            df.columns = df.columns.str.lower()
            
            if 'email' not in df.columns:
                messages.error(request, "El archivo debe contener una columna llamada 'email'.")
                return redirect('contacts:import')
                
            df = df.fillna('')
            
            created_count = 0
            updated_count = 0
            skipped_unsub_count = 0
            invalid_count = 0
            
            tag = None
            if tag_name:
                tag, _ = Tag.objects.get_or_create(organization=org, name=tag_name)
                
            # Obtener supresiones previas de la organización
            suppressed_emails = set(SuppressionEntry.objects.filter(
                Q(organization=org) | Q(organization__isnull=True)
            ).values_list('email', flat=True))
            
            for _, row in df.iterrows():
                email = str(row['email']).strip().lower()
                if not email or '@' not in email or '.' not in email:
                    invalid_count += 1
                    continue
                    
                # Si está desuscrito previamente, no lo reactivamos automáticamente
                if email in suppressed_emails:
                    skipped_unsub_count += 1
                    continue
                    
                first_name = str(row.get('nombre', '')).strip()
                last_name = str(row.get('apellido', '')).strip()
                company = str(row.get('empresa', '')).strip()
                phone = str(row.get('telefono', '')).strip()
                
                # Verificar límite de contactos
                current_count = Contact.objects.filter(organization=org).count()
                if current_count >= org.max_contacts:
                    messages.warning(request, f"Se detuvo la importación porque alcanzaste el límite de {org.max_contacts} contactos.")
                    break
                    
                contact, created = Contact.objects.update_or_create(
                    organization=org,
                    email=email,
                    defaults={
                        'first_name': first_name if first_name else None,
                        'last_name': last_name if last_name else None,
                        'company': company if company else None,
                        'phone': phone if phone else None,
                    }
                )
                
                if tag:
                    contact.tags.add(tag)
                    
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                    
            ActivityLog.objects.create(
                organization=org,
                user=request.user,
                action="Importación de Contactos",
                details=f"Importación completada: {created_count} creados, {updated_count} actualizados, {skipped_unsub_count} omitidos por baja."
            )
            
            msg = f"Importación exitosa. Creados: {created_count}, Actualizados: {updated_count}."
            if skipped_unsub_count > 0:
                msg += f" Omitidos por desuscripción previa: {skipped_unsub_count}."
            if invalid_count > 0:
                msg += f" Correos inválidos descartados: {invalid_count}."
            messages.success(request, msg)
            
        except Exception as e:
            messages.error(request, f"Error al procesar el archivo: {str(e)}")
            
        return redirect('contacts:import')
        
    return render(request, 'contacts/import.html')
