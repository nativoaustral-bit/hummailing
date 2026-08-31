from django.test import TestCase, Client
from django.urls import reverse
from organizations.models import Organization, SuppressionEntry
from core.models import User, Lead
from contacts.models import Contact, Tag
from campaigns.models import Campaign, CampaignLink, TrackingEvent
from opportunities.models import Opportunity

class HummailingMultiTenantTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # 1. Crear 2 Organizaciones
        self.org_alpha = Organization.objects.create(
            name="Empresa Alpha SpA",
            trade_name="Alpha",
            email="contacto@alpha.cl",
            default_sender_name="Alpha",
            default_sender_email="contacto@alpha.cl"
        )
        self.org_beta = Organization.objects.create(
            name="Consultora Beta Ltda",
            trade_name="Beta",
            email="contacto@beta.cl",
            default_sender_name="Beta",
            default_sender_email="contacto@beta.cl"
        )
        
        # 2. Crear Usuarios
        self.admin_humm = User.objects.create_user(
            username="admin_humm",
            email="admin@humm.cl",
            password="password123",
            role="humm_admin",
            must_change_password=False
        )
        
        self.user_alpha = User.objects.create_user(
            username="user_alpha",
            email="juan@alpha.cl",
            password="password123",
            organization=self.org_alpha,
            role="org_admin",
            must_change_password=False
        )
        
        self.user_beta = User.objects.create_user(
            username="user_beta",
            email="pedro@beta.cl",
            password="password123",
            organization=self.org_beta,
            role="org_admin",
            must_change_password=False
        )

        self.new_user_temp = User.objects.create_user(
            username="user_temp",
            email="temp@alpha.cl",
            password="temppassword123",
            organization=self.org_alpha,
            role="org_admin",
            must_change_password=True
        )

    def test_contact_email_isolation_between_organizations(self):
        """Verifica que dos organizaciones distintas puedan tener el mismo correo como contacto privado."""
        contact_alpha = Contact.objects.create(
            organization=self.org_alpha,
            email="prospecto@cliente.cl",
            first_name="Cliente",
            last_name="Alpha"
        )
        contact_beta = Contact.objects.create(
            organization=self.org_beta,
            email="prospecto@cliente.cl",
            first_name="Cliente",
            last_name="Beta"
        )
        self.assertNotEqual(contact_alpha.id, contact_beta.id)
        self.assertEqual(Contact.objects.filter(email="prospecto@cliente.cl").count(), 2)

    def test_contact_list_isolation(self):
        """Verifica que el usuario de Alpha solo vea sus contactos y no los de Beta."""
        Contact.objects.create(organization=self.org_alpha, email="alpha_lead@test.cl", first_name="Lead Alpha")
        Contact.objects.create(organization=self.org_beta, email="beta_lead@test.cl", first_name="Lead Beta")
        
        self.client.login(username="user_alpha", password="password123")
        response = self.client.get(reverse('contacts:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "alpha_lead@test.cl")
        self.assertNotContains(response, "beta_lead@test.cl")

    def test_campaign_list_isolation(self):
        """Verifica que el usuario de Alpha solo vea sus campañas y no las de Beta."""
        Campaign.objects.create(organization=self.org_alpha, name="Campaña Alpha 1", subject="Asunto Alpha")
        Campaign.objects.create(organization=self.org_beta, name="Campaña Beta 1", subject="Asunto Beta")
        
        self.client.login(username="user_alpha", password="password123")
        response = self.client.get(reverse('campaigns:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Campaña Alpha 1")
        self.assertNotContains(response, "Campaña Beta 1")

    def test_forced_password_change_middleware(self):
        """Verifica que un usuario con must_change_password=True sea forzado a cambiar su clave."""
        self.client.login(username="user_temp", password="temppassword123")
        response = self.client.get(reverse('dashboard'), follow=True)
        self.assertRedirects(response, reverse('change_password'))
        self.assertContains(response, "Actualizar Contraseña")

    def test_successful_password_change_resets_flag(self):
        """Verifica que al cambiar la contraseña, la marca must_change_password pase a False."""
        self.client.login(username="user_temp", password="temppassword123")
        response = self.client.post(reverse('change_password'), {
            'current_password': 'temppassword123',
            'new_password1': 'mi_nueva_clave_segura_2026',
            'new_password2': 'mi_nueva_clave_segura_2026',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.new_user_temp.refresh_from_db()
        self.assertFalse(self.new_user_temp.must_change_password)
        self.assertTrue(self.new_user_temp.check_password('mi_nueva_clave_segura_2026'))

    def test_conversion_link_tracking_creates_opportunity(self):
        """Verifica que al hacer clic en un enlace de conversión se registre el evento y cree una Oportunidad."""
        camp = Campaign.objects.create(
            organization=self.org_alpha,
            name="Campaña Promo",
            subject="Asunto Promo"
        )
        contact = Contact.objects.create(
            organization=self.org_alpha,
            email="comprador@empresa.cl",
            first_name="Carlos"
        )
        link = CampaignLink.objects.create(
            campaign=camp,
            original_url="https://www.humm.cl/servicios",
            link_type="conversion",
            service_interest="Auditoría Comercial",
            token="testtoken123"
        )
        
        # Simular clic en el enlace de redirección con el ID del contacto
        url = reverse('opportunities:track_click', kwargs={'token': 'testtoken123'}) + f"?c={contact.id}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://www.humm.cl/servicios")
        
        # Verificar que se creó la Oportunidad
        opp = Opportunity.objects.filter(organization=self.org_alpha, contact=contact).first()
        self.assertIsNotNone(opp)
        self.assertEqual(opp.interest_topic, "Auditoría Comercial")
        self.assertEqual(opp.status, "new")

    def test_humm_admin_can_access_master_panel(self):
        """Verifica que el Administrador Humm pueda acceder al panel maestro."""
        self.client.login(username="admin_humm", password="password123")
        response = self.client.get(reverse('organizations:admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Administración de Clientes Hummailing")

    def test_landing_page_renders_successfully(self):
        """Verifica que la landing page sea accesible públicamente y contenga los textos principales."""
        response = self.client.get(reverse('landing'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Convierte cada correo en una oportunidad.")
        self.assertContains(response, "Una herramienta de Humm")
        self.assertContains(response, "Quiero conocer Hummailing")
        self.assertContains(response, "logo.svg")

    def test_lead_capture_ajax_success(self):
        """Verifica que el endpoint de captación de leads procese solicitudes AJAX correctamente."""
        payload = {
            'name': 'Andrea González',
            'company_name': 'Taller Nativo SpA',
            'email': 'andrea@taller.cl',
            'phone': '+56912345678',
            'message': 'Me gustaría enviar catálogos mensuales.',
            'privacy_policy': 'on',
            'utm_source': 'google',
            'utm_campaign': 'campana_pymes',
        }
        response = self.client.post(
            reverse('capture_lead'),
            payload,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], "Gracias por tu interés. El equipo de Humm se pondrá en contacto contigo.")

        # Verificar persistencia en base de datos
        lead = Lead.objects.filter(email='andrea@taller.cl').first()
        self.assertIsNotNone(lead)
        self.assertEqual(lead.name, 'Andrea González')
        self.assertEqual(lead.company_name, 'Taller Nativo SpA')
        self.assertEqual(lead.source, 'landing_hummailing')
        self.assertEqual(lead.utm_source, 'google')
        self.assertEqual(lead.utm_campaign, 'campana_pymes')
        self.assertEqual(lead.status, 'pending')

    def test_lead_capture_honeypot_blocks_spam_silently(self):
        """Verifica que si un bot rellena el campo honeypot, no se guarde el lead."""
        initial_count = Lead.objects.count()
        payload = {
            'name': 'Bot Spammer',
            'company_name': 'Spam Co',
            'email': 'bot@spam.com',
            'phone': '123456',
            'privacy_policy': 'on',
            'website_hp': 'http://spam-link.com',  # Honeypot lleno
        }
        response = self.client.post(
            reverse('capture_lead'),
            payload,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Lead.objects.count(), initial_count)

    def test_lead_capture_validation_errors(self):
        """Verifica que el formulario rechace datos faltantes o inválidos."""
        payload = {
            'name': '',
            'company_name': '',
            'email': 'invalido',
            'phone': '',
        }
        response = self.client.post(
            reverse('capture_lead'),
            payload,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('name', data['errors'])
        self.assertIn('email', data['errors'])

    def test_humm_admin_can_view_lead_list_and_detail(self):
        """Verifica que el Administrador Humm pueda ver la lista y detalle de leads."""
        lead = Lead.objects.create(
            name="Test User",
            company_name="Empresa Test",
            email="test@empresa.cl",
            phone="+56911112222",
            source="landing_solucion_x"
        )
        self.client.login(username="admin_humm", password="password123")
        
        # Lista
        response = self.client.get(reverse('organizations:lead_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test User")
        self.assertContains(response, "landing_solucion_x")
        
        # Detalle
        response = self.client.get(reverse('organizations:lead_detail', kwargs={'lead_id': lead.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test@empresa.cl")

    def test_non_admin_cannot_access_lead_list(self):
        """Verifica que un usuario regular de organización no pueda ver los leads de Humm."""
        self.client.login(username="user_alpha", password="password123")
        response = self.client.get(reverse('organizations:lead_list'))
        self.assertNotEqual(response.status_code, 200)


