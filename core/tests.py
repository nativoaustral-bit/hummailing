import os
import shutil
import tempfile
import concurrent.futures
from io import BytesIO
from PIL import Image

from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.cache import cache

from core.security import create_unsubscribe_token, validate_unsubscribe_token
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

        self.editor_alpha = User.objects.create_user(
            username="editor_alpha",
            email="editor@alpha.cl",
            password="password123",
            organization=self.org_alpha,
            role="campaign_editor",
            must_change_password=False
        )

        self.viewer_alpha = User.objects.create_user(
            username="viewer_alpha",
            email="viewer@alpha.cl",
            password="password123",
            organization=self.org_alpha,
            role="viewer",
            must_change_password=False
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

    def test_unsubscribe_token_without_pii_and_confirmation_flow(self):
        """Verifica que el token de desuscripción no contenga PII, que GET no mute estado y POST sí."""
        contact = Contact.objects.create(
            organization=self.org_alpha,
            email="baja.segura@cliente.cl",
            first_name="Baja"
        )
        token = create_unsubscribe_token(contact.id, self.org_alpha.id)
        
        # 1. Verificar ausencia de PII en la URL/token
        self.assertNotIn("baja.segura@cliente.cl", token)
        self.assertNotIn("baja", token.lower())
        
        # 2. GET muestra pantalla de confirmación sin mutar la base de datos
        url = reverse('opportunities:unsubscribe', kwargs={'token': token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cancelar Suscripción")
        contact.refresh_from_db()
        self.assertEqual(contact.status, 'active')
        
        # 3. POST con CSRF ejecuta la desuscripción efectiva
        post_response = self.client.post(url, follow=True)
        self.assertEqual(post_response.status_code, 200)
        self.assertContains(post_response, "Te has dado de baja exitosamente")
        contact.refresh_from_db()
        self.assertEqual(contact.status, 'unsubscribed')
        self.assertTrue(SuppressionEntry.objects.filter(organization=self.org_alpha, email="baja.segura@cliente.cl").exists())

        # 4. Token alterado/corrupto es rechazado
        bad_response = self.client.get(reverse('opportunities:unsubscribe', kwargs={'token': token + 'invalid'}))
        self.assertEqual(bad_response.status_code, 400)

        # 5. Token con discrepancia cross-tenant es rechazado
        cross_token = create_unsubscribe_token(contact.id, self.org_beta.id)
        cross_response = self.client.get(reverse('opportunities:unsubscribe', kwargs={'token': cross_token}))
        self.assertEqual(cross_response.status_code, 400)

    from unittest.mock import patch

    @patch('core.views.send_mail')
    @patch('core.views.Lead.objects.create')
    def test_concurrent_rate_limiting_on_lead_capture(self, mock_lead_create, mock_send_mail):
        """Verifica que solicitudes concurrentes/paralelas no permitan sobrepasar el límite de 5 req/h."""
        cache.clear()
        url = reverse('capture_lead')
        test_ip = '198.51.100.77'
        
        def send_lead(i):
            client = Client()
            payload = {
                'name': f'Lead Concurrente {i}',
                'company_name': 'Test Corp',
                'email': f'lead_{i}@testcorp.cl',
                'phone': '+56911223344',
                'privacy_policy': 'on'
            }
            return client.post(
                url,
                payload,
                REMOTE_ADDR=test_ip,
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                HTTP_ACCEPT='application/json'
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(send_lead, i) for i in range(12)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        status_codes = [r.status_code for r in results]
        success_count = status_codes.count(200)
        rate_limited_count = status_codes.count(429)
        
        self.assertEqual(success_count, 5, f"Esperado exactamente 5 solicitudes exitosas, obtenido {success_count}")
        self.assertEqual(rate_limited_count, 7, f"Esperado 7 solicitudes bloqueadas por HTTP 429, obtenido {rate_limited_count}")

    def test_viewer_role_blocked_on_all_mutations(self):
        """Verifica que el rol 'viewer' (solo lectura) tenga bloqueada cualquier mutación de estado con 403."""
        contact = Contact.objects.create(organization=self.org_alpha, email="solo_lectura@alpha.cl", first_name="Solo")
        campaign = Campaign.objects.create(organization=self.org_alpha, name="Campaña Lectura", subject="Sub")
        opp = Opportunity.objects.create(organization=self.org_alpha, contact=contact, title="Oportunidad Lectura")

        self.client.login(username="viewer_alpha", password="password123")

        # Intentos de mutación en contactos
        r = self.client.post(reverse('contacts:create'), {'email': 'nuevo@alpha.cl', 'first_name': 'Nuevo'})
        self.assertEqual(r.status_code, 403)
        
        r = self.client.post(reverse('contacts:edit', kwargs={'contact_id': contact.id}), {'first_name': 'Modificado'})
        self.assertEqual(r.status_code, 403)
        
        r = self.client.post(reverse('contacts:delete', kwargs={'contact_id': contact.id}))
        self.assertEqual(r.status_code, 403)
        
        r = self.client.post(reverse('contacts:import'))
        self.assertEqual(r.status_code, 403)

        # Intentos de mutación en campañas
        r = self.client.post(reverse('campaigns:create'), {'name': 'Hack Camp', 'subject': 'Sub'})
        self.assertEqual(r.status_code, 403)

        r = self.client.post(reverse('campaigns:editor', kwargs={'campaign_id': campaign.id}), '{"blocks": []}', content_type="application/json")
        self.assertEqual(r.status_code, 403)

        r = self.client.post(reverse('campaigns:delete', kwargs={'campaign_id': campaign.id}))
        self.assertEqual(r.status_code, 403)

        r = self.client.post(reverse('campaigns:send', kwargs={'campaign_id': campaign.id}), '{}', content_type="application/json")
        self.assertEqual(r.status_code, 403)

        r = self.client.post(reverse('campaigns:upload_image'))
        self.assertEqual(r.status_code, 403)

        # Intento de mutación en oportunidades
        r = self.client.post(reverse('opportunities:detail', kwargs={'opp_id': opp.id}), {'status': 'won'})
        self.assertEqual(r.status_code, 403)

    def test_campaign_editor_role_boundaries(self):
        """Verifica que campaign_editor pueda editar campañas pero no mutar contactos ni eliminar campañas."""
        contact = Contact.objects.create(organization=self.org_alpha, email="editor_test@alpha.cl")
        campaign = Campaign.objects.create(organization=self.org_alpha, name="Campaña Editor", subject="Sub")

        self.client.login(username="editor_alpha", password="password123")

        # Restringido en contactos (403)
        r = self.client.post(reverse('contacts:create'), {'email': 'prohibido@alpha.cl'})
        self.assertEqual(r.status_code, 403)

        r = self.client.post(reverse('contacts:delete', kwargs={'contact_id': contact.id}))
        self.assertEqual(r.status_code, 403)

        # Restringido en eliminación de campañas (403)
        r = self.client.post(reverse('campaigns:delete', kwargs={'campaign_id': campaign.id}))
        self.assertEqual(r.status_code, 403)

        # Autorizado en creación y edición de campañas
        r = self.client.post(reverse('campaigns:create'), {'name': 'Campaña Autorizada', 'subject': 'Asunto'})
        self.assertEqual(r.status_code, 302)

        r = self.client.post(reverse('campaigns:editor', kwargs={'campaign_id': campaign.id}), '{"blocks": []}', content_type="application/json")
        self.assertEqual(r.status_code, 200)

    def test_cross_tenant_isolation_rejections(self):
        """Verifica que un usuario de la Organización Alpha no pueda alterar recursos de Beta ni asignar usuarios de Beta."""
        contact_beta = Contact.objects.create(organization=self.org_beta, email="beta_privado@beta.cl")
        campaign_beta = Campaign.objects.create(organization=self.org_beta, name="Camp Beta", subject="Sub")
        contact_alpha = Contact.objects.create(organization=self.org_alpha, email="alpha_lead@alpha.cl")
        opp_alpha = Opportunity.objects.create(organization=self.org_alpha, contact=contact_alpha, title="Opp Alpha")

        self.client.login(username="user_alpha", password="password123")

        # No puede editar ni borrar contactos de otra org (404)
        r = self.client.post(reverse('contacts:edit', kwargs={'contact_id': contact_beta.id}), {'first_name': 'Infiltrado'})
        self.assertEqual(r.status_code, 404)

        r = self.client.post(reverse('contacts:delete', kwargs={'contact_id': contact_beta.id}))
        self.assertEqual(r.status_code, 404)

        # No puede editar ni borrar campañas de otra org (404)
        r = self.client.post(reverse('campaigns:editor', kwargs={'campaign_id': campaign_beta.id}), '{"blocks": []}', content_type="application/json")
        self.assertEqual(r.status_code, 404)

        r = self.client.post(reverse('campaigns:delete', kwargs={'campaign_id': campaign_beta.id}))
        self.assertEqual(r.status_code, 404)

        # No puede asignar una oportunidad propia a un usuario de otra organización
        r = self.client.post(reverse('opportunities:detail', kwargs={'opp_id': opp_alpha.id}), {
            'status': 'in_progress',
            'assigned_to': self.user_beta.id
        }, follow=True)
        opp_alpha.refresh_from_db()
        self.assertNotEqual(opp_alpha.assigned_to_id, self.user_beta.id)
        self.assertContains(r, "El usuario asignado no pertenece a tu organización")

    def test_image_upload_security_svg_rejection_and_raster_validation(self):
        """Verifica que la subida de imágenes rechace SVG y archivos corruptos, y acepte imágenes raster válidas."""
        self.client.login(username="user_alpha", password="password123")
        url = reverse('campaigns:upload_image')

        # 1. Rechazar SVG terminantemente con 400
        svg_file = SimpleUploadedFile("malicious.svg", b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", content_type="image/svg+xml")
        r = self.client.post(url, {'image': svg_file})
        self.assertEqual(r.status_code, 400)
        self.assertIn("SVG no está permitido", r.json()['message'])

        # 2. Rechazar archivo falso disfrazado con extensión png con 400
        fake_img = SimpleUploadedFile("exploit.png", b"<?php echo 'pwned'; ?>", content_type="image/png")
        r = self.client.post(url, {'image': fake_img})
        self.assertEqual(r.status_code, 400)
        self.assertIn("no es una imagen válida", r.json()['message'])

        # 3. Aceptar imagen raster válida (PNG 1x1)
        img_buffer = BytesIO()
        test_img = Image.new('RGB', (10, 10), color='blue')
        test_img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        valid_png = SimpleUploadedFile("test_logo.png", img_buffer.getvalue(), content_type="image/png")
        r = self.client.post(url, {'image': valid_png})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['status'], 'success')

    def test_backup_and_restore_isolated_cycle(self):
        """Verifica el ciclo completo: backup consistente -> transferencia off-site -> validación SHA-256 -> restore aislado."""
        temp_dir = tempfile.mkdtemp()
        temp_offsite_dir = tempfile.mkdtemp()
        try:
            # 1. Ejecutar backup con copia off-site automática
            backup_zip_path = call_command('backup_data', dest=temp_dir, offsite_dest=temp_offsite_dir)
            self.assertTrue(os.path.exists(backup_zip_path))
            self.assertTrue(backup_zip_path.endswith('.zip'))

            # 2. Verificar que la copia off-site exista y coincida exactamente en checksum SHA-256
            zip_filename = os.path.basename(backup_zip_path)
            offsite_file = os.path.join(temp_offsite_dir, zip_filename)
            self.assertTrue(os.path.exists(offsite_file))
            
            from core.management.commands.backup_data import sha256_file
            self.assertEqual(sha256_file(backup_zip_path), sha256_file(offsite_file))

            # 3. Ejecutar comando de restauración aislada y dry-run utilizando el archivo transferido off-site
            result = call_command('restore_data', backup_file=offsite_file, isolated=True, dry_run=True)
            self.assertEqual(result, "OK")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            shutil.rmtree(temp_offsite_dir, ignore_errors=True)




from .test_hcc_integration import HummailingHCCIntegrationTests
