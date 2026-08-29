from django.db import models

class Tag(models.Model):
    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE, related_name='tags', null=True, blank=True, verbose_name="Organización")
    name = models.CharField(max_length=100, verbose_name="Nombre")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Etiqueta"
        verbose_name_plural = "Etiquetas"
        unique_together = ('organization', 'name')

    def __str__(self):
        return self.name

class Segment(models.Model):
    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE, related_name='segments', null=True, blank=True, verbose_name="Organización")
    name = models.CharField(max_length=150, verbose_name="Nombre")
    description = models.TextField(blank=True, verbose_name="Descripción")
    filter_rules = models.JSONField(default=dict, verbose_name="Reglas de filtro")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Segmento"
        verbose_name_plural = "Segmentos"
        unique_together = ('organization', 'name')

    def __str__(self):
        return self.name

class Contact(models.Model):
    STATUS_CHOICES = (
        ('active', 'Activo'),
        ('unconfirmed', 'Sin confirmar'),
        ('unsubscribed', 'Dado de baja'),
        ('bounced', 'Correo rebotado'),
        ('blocked', 'Bloqueado'),
        ('spam', 'Marcado como spam'),
    )
    
    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE, related_name='contacts', null=True, blank=True, verbose_name="Organización")
    email = models.EmailField(verbose_name="Correo Electrónico")
    first_name = models.CharField(max_length=150, blank=True, verbose_name="Nombre")
    last_name = models.CharField(max_length=150, blank=True, verbose_name="Apellidos")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Teléfono")
    company = models.CharField(max_length=200, blank=True, verbose_name="Empresa o emprendimiento")
    job_title = models.CharField(max_length=200, blank=True, verbose_name="Cargo")
    industry = models.CharField(max_length=150, blank=True, verbose_name="Rubro")
    region = models.CharField(max_length=150, blank=True, verbose_name="Región")
    city = models.CharField(max_length=150, blank=True, verbose_name="Comuna")
    source = models.CharField(max_length=150, blank=True, verbose_name="Fuente u origen")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="Estado")
    consent_status = models.BooleanField(default=True, verbose_name="Estado de consentimiento")
    consent_date = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de consentimiento")
    consent_source = models.CharField(max_length=200, blank=True, verbose_name="Origen de consentimiento")
    
    last_interaction = models.DateTimeField(null=True, blank=True, verbose_name="Última interacción")
    internal_notes = models.TextField(blank=True, verbose_name="Observaciones internas")
    
    tags = models.ManyToManyField(Tag, blank=True, verbose_name="Etiquetas")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Contacto"
        verbose_name_plural = "Contactos"
        unique_together = ('organization', 'email')
    
    def __str__(self):
        if self.first_name:
            return f"{self.first_name} {self.last_name} ({self.email})"
        return self.email
    
    def save(self, *args, **kwargs):
        self.email = self.email.lower().strip()
        super().save(*args, **kwargs)
