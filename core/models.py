from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = (
        ('humm_admin', 'Administrador Humm'),
        ('org_admin', 'Administrador de Organización'),
        ('campaign_editor', 'Editor de Campañas'),
        ('viewer', 'Visualizador / Analista'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer', verbose_name="Rol en la plataforma")
    organization = models.ForeignKey(
        'organizations.Organization', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='users',
        verbose_name="Organización"
    )
    must_change_password = models.BooleanField(
        default=False, 
        verbose_name="Debe cambiar contraseña al iniciar sesión"
    )
    phone = models.CharField(max_length=50, blank=True, verbose_name="Teléfono")
    last_login_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP Último Acceso")
    
    @property
    def is_humm_master_admin(self):
        return self.is_superuser or self.role == 'humm_admin'

    def __str__(self):
        org_name = f" - {self.organization.name}" if self.organization else ""
        return f"{self.username} ({self.get_role_display()}{org_name})"


class Lead(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pendiente de Contacto'),
        ('contacted', 'Contactado'),
        ('converted', 'Convertido a Cliente'),
        ('discarded', 'Descartado'),
    )

    name = models.CharField(max_length=150, verbose_name="Nombre Completo")
    company_name = models.CharField(max_length=150, verbose_name="Emprendimiento o Empresa")
    email = models.EmailField(verbose_name="Correo Electrónico")
    phone = models.CharField(max_length=50, verbose_name="Teléfono o WhatsApp")
    message = models.TextField(blank=True, verbose_name="Mensaje o Consulta Opcional")
    privacy_accepted = models.BooleanField(default=True, verbose_name="Aceptó Política de Privacidad")
    
    # Origen y Tracking
    source = models.CharField(max_length=100, default='landing_hummailing', verbose_name="Origen del Lead")
    utm_source = models.CharField(max_length=100, blank=True, verbose_name="UTM Source")
    utm_medium = models.CharField(max_length=100, blank=True, verbose_name="UTM Medium")
    utm_campaign = models.CharField(max_length=100, blank=True, verbose_name="UTM Campaign")
    utm_term = models.CharField(max_length=100, blank=True, verbose_name="UTM Term")
    utm_content = models.CharField(max_length=100, blank=True, verbose_name="UTM Content")
    
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Dirección IP")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending', verbose_name="Estado")
    notes = models.TextField(blank=True, verbose_name="Notas Internas Humm")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Captación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    class Meta:
        verbose_name = "Prospecto / Lead"
        verbose_name_plural = "Prospectos / Leads (Landing)"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.company_name} ({self.email})"

