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



class HCCOutboxStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pendiente'
    SENT = 'SENT', 'Enviado'
    ERROR = 'ERROR', 'Error Permanente'


class HCCOutboxEvent(models.Model):
    """
    Outbox transaccional para eventos garantizados hacia Humm Control Center (HCC).
    Garantiza resiliencia server-to-server desacoplando el despacho de campañas
    de la disponibilidad de red de HCC.
    """
    event_id = models.CharField(
        max_length=150, unique=True, db_index=True,
        help_text="ID canónico e inmutable del evento: hummailing-activation-user-{user_id}"
    )
    event_type = models.CharField(
        max_length=60, default='TOOL_ACTIVATED',
        help_text="Tipo de evento según contrato canónico HCC v0.1"
    )
    user = models.ForeignKey(
        'core.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hcc_outbox_events', verbose_name="Usuario titular de Hummailing"
    )
    payload = models.JSONField(
        default=dict,
        help_text="Payload canónico JSON serializado para HCC (congelado al crear)"
    )
    status = models.CharField(
        max_length=20, choices=HCCOutboxStatus.choices, default=HCCOutboxStatus.PENDING,
        db_index=True, verbose_name="Estado de sincronización"
    )
    attempts = models.PositiveIntegerField(
        default=0, verbose_name="Número de intentos de envío"
    )
    last_error = models.TextField(
        blank=True, default='', verbose_name="Último error registrado (resumido y sanitizado)"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, verbose_name="Fecha de creación en outbox"
    )
    last_attempt_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Fecha y hora del último intento"
    )
    sent_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Fecha y hora de confirmación de entrega"
    )

    class Meta:
        verbose_name = "Evento Outbox HCC"
        verbose_name_plural = "Eventos Outbox HCC"
        ordering = ['created_at']

    def __str__(self):
        return f"{self.event_id} [{self.status}] ({self.attempts} intentos)"

    def mark_sent(self):
        from django.utils import timezone
        self.status = HCCOutboxStatus.SENT
        self.sent_at = timezone.now()
        self.last_attempt_at = timezone.now()
        self.save(update_fields=['status', 'sent_at', 'last_attempt_at'])

    def mark_failed(self, error_message: str, is_permanent: bool = False):
        from django.utils import timezone
        self.attempts += 1
        self.last_attempt_at = timezone.now()
        self.last_error = str(error_message)[:500]
        if is_permanent:
            self.status = HCCOutboxStatus.ERROR
        else:
            self.status = HCCOutboxStatus.PENDING
        self.save(update_fields=['attempts', 'last_attempt_at', 'last_error', 'status'])
