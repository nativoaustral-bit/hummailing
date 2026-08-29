import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from contacts.models import Contact, Tag
from campaigns.models import Campaign
from django.contrib.auth import get_user_model

def setup_test_data():
    # Create or get tag
    tag, _ = Tag.objects.get_or_create(name='Prueba Etapa 3')
    
    # Create contact
    # You can change this email!
    test_email = 'rmerinog@gmail.com'
    contact, created = Contact.objects.get_or_create(
        email=test_email,
        defaults={'first_name': 'Roberto', 'status': 'active'}
    )
    contact.tags.add(tag)
    
    # Get user
    User = get_user_model()
    user = User.objects.first()
    
    # Create Campaign
    campaign, _ = Campaign.objects.get_or_create(
        name='Campaña de Prueba - Etapa 3',
        defaults={
            'subject': '¡Tu primer correo desde Celery y Resend!',
            'target_tag': tag,
            'created_by': user,
            'content_blocks': [
                {"type": "header"},
                {"type": "title", "content": {"text": "¡Funciona!"}},
                {"type": "text", "content": {"text": "Hola {{ first_name }},\n\nSi estás leyendo esto, es porque el worker de Celery procesó correctamente el correo en segundo plano y Resend lo despachó a tu bandeja."}},
                {"type": "cta", "content": {"text": "Volver a Humm", "url": "http://localhost:8000"}},
                {"type": "footer"}
            ]
        }
    )
    
    print(f"Campaña '{campaign.name}' creada exitosamente.")
    print("Por favor verifica que la campaña esté lista en el dashboard.")

if __name__ == '__main__':
    setup_test_data()
