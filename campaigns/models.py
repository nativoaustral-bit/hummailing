from django.db import models
from django.conf import settings
from contacts.models import Segment, Contact

class CampaignTemplate(models.Model):
    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE, related_name='templates', null=True, blank=True, verbose_name="Organización")
    name = models.CharField(max_length=150, verbose_name="Nombre de la plantilla")
    description = models.TextField(blank=True, verbose_name="Descripción")
    html_content = models.TextField(verbose_name="Contenido HTML base", blank=True)
    content_blocks = models.JSONField(default=list, blank=True, verbose_name="Bloques de la plantilla")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Plantilla de Campaña"
        verbose_name_plural = "Plantillas de Campaña"

    def __str__(self):
        return self.name

class Campaign(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Borrador'),
        ('review', 'En revisión'),
        ('scheduled', 'Programada'),
        ('sending', 'Enviando'),
        ('sent', 'Enviada'),
        ('paused', 'Pausada'),
        ('cancelled', 'Cancelada'),
    )
    
    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE, related_name='campaigns', null=True, blank=True, verbose_name="Organización")
    name = models.CharField(max_length=200, verbose_name="Nombre interno")
    subject = models.CharField(max_length=250, verbose_name="Asunto")
    preheader = models.CharField(max_length=250, blank=True, verbose_name="Texto de preencabezado")
    
    sender_name = models.CharField(max_length=150, default="Hummailing")
    sender_email = models.EmailField(default="hola@humm.cl")
    reply_to = models.EmailField(blank=True, default="hola@humm.cl")
    
    segment = models.ForeignKey(Segment, on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns')
    target_tag = models.ForeignKey('contacts.Tag', on_delete=models.SET_NULL, null=True, blank=True, help_text="Enviar a una etiqueta específica")
    template = models.ForeignKey(CampaignTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    
    # El contenido estructurado por bloques se guarda aquí
    content_blocks = models.JSONField(default=list, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True, help_text="Cuándo comenzó el envío")
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Campaña"
        verbose_name_plural = "Campañas"
        ordering = ['-created_at']

    def __str__(self):
        return self.name

class CampaignLink(models.Model):
    LINK_TYPES = (
        ('info', 'Informativo'),
        ('conversion', 'Conversión'),
        ('unsubscribe', 'Desuscripción'),
    )
    
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='links')
    original_url = models.URLField(max_length=2000)
    link_type = models.CharField(max_length=20, choices=LINK_TYPES, default='info')
    service_interest = models.CharField(max_length=200, blank=True, help_text="Si es conversión, qué servicio o tema es")
    token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    
    def __str__(self):
        return f"{self.original_url} ({self.get_link_type_display()})"

class TrackingEvent(models.Model):
    EVENT_TYPES = (
        ('sent', 'Envío'),
        ('delivered', 'Entrega'),
        ('bounce_temp', 'Rebote temporal'),
        ('bounce_perm', 'Rebote permanente'),
        ('open', 'Apertura'),
        ('click', 'Clic'),
        ('reply', 'Respuesta'),
        ('unsub', 'Cancelación de suscripción'),
        ('spam', 'Queja por spam'),
        ('error', 'Error'),
    )
    
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='events')
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    link = models.ForeignKey(CampaignLink, on_delete=models.SET_NULL, null=True, blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Evento de Seguimiento"
        verbose_name_plural = "Eventos de Seguimiento"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.contact.email} - {self.get_event_type_display()} - {self.campaign.name}"


class CampaignSchedule(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pendiente'),
        ('processing', 'En proceso'),
        ('completed', 'Completado'),
        ('cancelled', 'Cancelado'),
        ('failed', 'Fallido'),
    )
    
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='schedules', verbose_name="Campaña")
    scheduled_at = models.DateTimeField(verbose_name="Fecha y hora programada")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Fecha real de ejecución")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Programación de Campaña"
        verbose_name_plural = "Programaciones de Campaña"
        ordering = ['scheduled_at']

    def __str__(self):
        return f"{self.campaign.name} - {self.scheduled_at.strftime('%d/%m/%Y %H:%M')} ({self.get_status_display()})"

