import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from organizations.models import Organization, ActivityLog
from core.models import User
from contacts.models import Contact, Tag
from campaigns.models import Campaign, CampaignLink
from opportunities.models import Opportunity

def seed_demo_data():
    print("--- Sembrando Datos Demo para Hummailing ---")

    # 1. Crear Organización 1: Acme Emprendimiento
    org1, _ = Organization.objects.get_or_create(
        name="Acme Soluciones Digitales SpA",
        defaults={
            'trade_name': "Acme Digital",
            'rut': "76.890.123-K",
            'email': "contacto@acmedigital.cl",
            'phone': "+56 9 8765 4321",
            'default_sender_name': "Acme Digital",
            'default_sender_email': "hola@humm.cl",
            'default_reply_to': "contacto@acmedigital.cl",
            'status': 'active',
            'max_contacts': 2000,
            'monthly_email_limit': 10000
        }
    )

    # 2. Crear Organización 2: BioNativa Cosmética
    org2, _ = Organization.objects.get_or_create(
        name="BioNativa Cosmética Orgánica Ltda",
        defaults={
            'trade_name': "BioNativa",
            'rut': "77.123.456-8",
            'email': "hola@bionativa.cl",
            'phone': "+56 9 1122 3344",
            'default_sender_name': "BioNativa",
            'default_sender_email': "hola@humm.cl",
            'default_reply_to': "hola@bionativa.cl",
            'status': 'active',
            'max_contacts': 1500,
            'monthly_email_limit': 8000
        }
    )

    # 3. Crear Usuarios para cada organización
    # Usuario Acme
    u1, created = User.objects.get_or_create(
        username="acme.admin",
        defaults={
            'email': "admin@acmedigital.cl",
            'first_name': "Marcela",
            'last_name': "Rojas",
            'organization': org1,
            'role': "org_admin",
            'must_change_password': False
        }
    )
    if created:
        u1.set_password("acme1234")
        u1.save()

    # Usuario BioNativa
    u2, created = User.objects.get_or_create(
        username="bionativa.admin",
        defaults={
            'email': "admin@bionativa.cl",
            'first_name': "Sebastián",
            'last_name': "Valenzuela",
            'organization': org2,
            'role': "org_admin",
            'must_change_password': False
        }
    )
    if created:
        u2.set_password("bionativa1234")
        u2.save()

    # 4. Crear Etiquetas y Contactos para Acme
    tag_tech, _ = Tag.objects.get_or_create(organization=org1, name="Tecnología")
    tag_pyme, _ = Tag.objects.get_or_create(organization=org1, name="PYME")

    c1, _ = Contact.objects.get_or_create(
        organization=org1,
        email="contacto1@clienteacme.cl",
        defaults={'first_name': "Ignacio", 'last_name': "Paredes", 'company': "TechCorp", 'phone': "+56 9 9988 7766"}
    )
    c1.tags.add(tag_tech)

    c2, _ = Contact.objects.get_or_create(
        organization=org1,
        email="contacto2@clienteacme.cl",
        defaults={'first_name': "Valeria", 'last_name': "Soto", 'company': "Innovar SpA", 'phone': "+56 9 5544 3322"}
    )
    c2.tags.add(tag_pyme)

    # 5. Crear Contactos para BioNativa (¡con un correo común para demostrar aislamiento!)
    tag_retail, _ = Tag.objects.get_or_create(organization=org2, name="Retail")
    c3, _ = Contact.objects.get_or_create(
        organization=org2,
        email="contacto1@clienteacme.cl", # Mismo email, pero aislado en BioNativa
        defaults={'first_name': "Ignacio", 'last_name': "Paredes (Bio)", 'company': "EcoTienda", 'phone': "+56 9 7788 9900"}
    )
    c3.tags.add(tag_retail)

    # 6. Crear Oportunidad Comercial de ejemplo en Acme
    opp, _ = Opportunity.objects.get_or_create(
        organization=org1,
        contact=c1,
        title="Interés en Software ERP Cloud",
        defaults={
            'interest_topic': "Software ERP",
            'status': "new",
            'priority': "high",
            'notes': "Prospecto hizo clic en el botón de la campaña de lanzamiento."
        }
    )

    print("✅ Datos Demo creados con éxito:")
    print(" - Admin Master Humm: user='admin' / pass='admin'")
    print(" - Cliente 1 (Acme): user='acme.admin' / pass='acme1234'")
    print(" - Cliente 2 (BioNativa): user='bionativa.admin' / pass='bionativa1234'")

if __name__ == '__main__':
    seed_demo_data()
