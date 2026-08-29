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
