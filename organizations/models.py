from django.db import models
from django.conf import settings

class Organization(models.Model):
    STATUS_CHOICES = (
        ('active', 'Activa'),
        ('suspended', 'Suspendida'),
        ('closed', 'Cerrada'),
    )

    name = models.CharField(max_length=200, verbose_name="Razón Social / Nombre")
    trade_name = models.CharField(max_length=200, blank=True, verbose_name="Nombre Comercial")
    rut = models.CharField(max_length=50, blank=True, verbose_name="RUT")
    email = models.EmailField(verbose_name="Correo Principal")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Teléfono")
    website = models.URLField(max_length=255, blank=True, verbose_name="Sitio Web")
    logo = models.CharField(max_length=500, blank=True, verbose_name="URL del Logo del Cliente")
    
    # Identidad de correos
    default_sender_name = models.CharField(max_length=150, default="Hummailing", verbose_name="Nombre del Remitente")
    default_sender_email = models.EmailField(default="hola@humm.cl", verbose_name="Correo de Envío Autorizado")
    default_reply_to = models.EmailField(default="hola@humm.cl", blank=True, verbose_name="Correo de Respuesta (Reply-To)")
    
    # Dirección
    address = models.CharField(max_length=255, blank=True, verbose_name="Dirección Comercial")
    region = models.CharField(max_length=100, blank=True, verbose_name="Región")
    city = models.CharField(max_length=100, blank=True, verbose_name="Comuna")
    
    # Estado y límites
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="Estado")
    max_contacts = models.PositiveIntegerField(default=1000, verbose_name="Límite Máximo de Contactos")
    monthly_email_limit = models.PositiveIntegerField(default=5000, verbose_name="Límite Mensual de Envíos")
    
    # Administración Humm
    account_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='managed_organizations',
        verbose_name="Responsable en Humm"
    )
    notes = models.TextField(blank=True, verbose_name="Observaciones Internas")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última Modificación")

    class Meta:
        verbose_name = "Organización"
        verbose_name_plural = "Organizaciones"
        ordering = ['name']

    def __str__(self):
        return self.trade_name or self.name


class ActivityLog(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='activity_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='activity_logs')
    action = models.CharField(max_length=150, verbose_name="Acción Realizada")
    details = models.TextField(blank=True, verbose_name="Detalles")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Dirección IP")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora")

    class Meta:
        verbose_name = "Registro de Actividad"
        verbose_name_plural = "Registros de Actividad"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} - {self.action} ({self.user})"


class SuppressionEntry(models.Model):
    REASON_CHOICES = (
        ('unsub', 'Cancelación de Suscripción'),
        ('bounce_perm', 'Rebote Permanente (Hard Bounce)'),
        ('spam', 'Queja por Spam'),
    )
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='suppressions')
    email = models.EmailField(verbose_name="Correo Excluido")
    reason = models.CharField(max_length=30, choices=REASON_CHOICES, default='unsub', verbose_name="Motivo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")

    class Meta:
        verbose_name = "Entrada de Exclusión"
        verbose_name_plural = "Lista de Exclusiones"
        unique_together = ('organization', 'email')
        ordering = ['-created_at']

    def __str__(self):
        org_name = self.organization.name if self.organization else "Global"
        return f"{self.email} ({self.get_reason_display()} - {org_name})"


class BroadcastAnnouncement(models.Model):
    TARGET_CHOICES = (
        ('all_active_orgs', 'Todos los Administradores de Empresas Activas'),
        ('all_users', 'Todos los Usuarios Registrados'),
    )
    title = models.CharField(max_length=200, verbose_name="Título Interno del Comunicado")
    subject = models.CharField(max_length=250, verbose_name="Asunto del Correo")
    message = models.TextField(verbose_name="Contenido del Mensaje")
    target_audience = models.CharField(max_length=50, choices=TARGET_CHOICES, default='all_active_orgs', verbose_name="Destinatarios")
    recipients_count = models.PositiveIntegerField(default=0, verbose_name="Cantidad de Destinatarios")
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name="Enviado Por")
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora de Envío")

    class Meta:
        verbose_name = "Comunicado Masivo a Clientes"
        verbose_name_plural = "Comunicados Masivos a Clientes"
        ordering = ['-sent_at']

    def __str__(self):
        return f"{self.subject} ({self.sent_at:%d/%m/%Y})"
