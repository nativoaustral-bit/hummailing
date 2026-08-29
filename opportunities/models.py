from django.db import models
from django.conf import settings
from organizations.models import Organization
from contacts.models import Contact

class Opportunity(models.Model):
    STATUS_CHOICES = (
        ('new', 'Nueva'),
        ('to_contact', 'Por contactar'),
        ('contacted', 'Contactado'),
        ('in_conversation', 'En conversación'),
        ('proposal_sent', 'Propuesta enviada'),
        ('won', 'Ganada / Venta cerrada'),
        ('not_interested', 'No interesado'),
        ('lost', 'Perdida'),
    )
    
    PRIORITY_CHOICES = (
        ('low', 'Baja'),
        ('medium', 'Media'),
        ('high', 'Alta / Urgente'),
    )
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='opportunities', verbose_name="Organización")
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='opportunities', verbose_name="Contacto Prospecto")
    campaign = models.ForeignKey('campaigns.Campaign', on_delete=models.SET_NULL, null=True, blank=True, related_name='opportunities', verbose_name="Campaña de Origen")
    link = models.ForeignKey('campaigns.CampaignLink', on_delete=models.SET_NULL, null=True, blank=True, related_name='opportunities', verbose_name="Enlace de Conversión")
    
    title = models.CharField(max_length=200, verbose_name="Título / Oportunidad")
    interest_topic = models.CharField(max_length=200, blank=True, verbose_name="Tema o Servicio de Interés")
    
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='new', verbose_name="Estado Comercial")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', verbose_name="Prioridad")
    
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_opportunities', verbose_name="Ejecutivo Responsable")
    notes = models.TextField(blank=True, verbose_name="Notas de Seguimiento")
    next_action = models.CharField(max_length=255, blank=True, verbose_name="Próxima Acción")
    follow_up_date = models.DateField(null=True, blank=True, verbose_name="Fecha de Seguimiento")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    class Meta:
        verbose_name = "Oportunidad Comercial"
        verbose_name_plural = "Oportunidades Comerciales"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.contact.email} ({self.get_status_display()})"
