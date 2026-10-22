import os
import base64
from django.test import TestCase, Client
from django.conf import settings
from campaigns.models import Campaign
from organizations.models import Organization
from campaigns.utils import extract_and_save_base64_image, make_absolute_image_url
from campaigns.tasks import render_blocks_to_html

class CampaignImageDeliveryTestCase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name="Organización Test",
            trade_name="Humm Co-Creation",
            email="test@humm.cl"
        )
        self.campaign = Campaign.objects.create(
            organization=self.org,
            name="Campaña Imagen Test",
            subject="Asunto de Prueba",
            sender_name="Humm",
            sender_email="hola@humm.cl"
        )

    def test_make_absolute_image_url_with_relative_path(self):
        relative_url = "/media/logos/mi_logo.png"
        abs_url = make_absolute_image_url(relative_url, "https://mailing.humm.cl")
        self.assertEqual(abs_url, "https://mailing.humm.cl/media/logos/mi_logo.png")

    def test_make_absolute_image_url_with_external_url(self):
        external_url = "https://images.unsplash.com/photo-test.jpg"
        abs_url = make_absolute_image_url(external_url)
        self.assertEqual(abs_url, external_url)

    def test_make_absolute_image_url_with_base64_data_uri(self):
        # 1x1 transparent PNG in base64
        tiny_png = (
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        abs_url = make_absolute_image_url(tiny_png, "https://mailing.humm.cl")
        self.assertTrue(abs_url.startswith("https://mailing.humm.cl/media/logos/img_"))
        self.assertTrue(abs_url.endswith(".png"))

    def test_render_blocks_to_html_converts_all_images_to_absolute(self):
        blocks_data = {
            'theme': {'header_bg': '#173960'},
            'blocks': [
                {
                    'type': 'header',
                    'content': {
                        'logo_url': '/media/logos/test_header_logo.png',
                        'company_name': 'Humm Co-Creation'
                    }
                },
                {
                    'type': 'image',
                    'content': {
                        'url': '/media/logos/test_body_image.png'
                    }
                }
            ]
        }
        html = render_blocks_to_html(blocks_data, self.campaign, base_site_url="https://mailing.humm.cl")
        
        # Debe contener la URL absoluta y pública requerida por clientes de email (Gmail, Apple Mail, etc.)
        self.assertIn('src="https://mailing.humm.cl/media/logos/test_header_logo.png"', html)
        self.assertIn('src="https://mailing.humm.cl/media/logos/test_body_image.png"', html)
        self.assertNotIn('src="/media/', html)

    def test_media_serving_fallback_endpoint(self):
        # Crear un archivo de prueba en MEDIA_ROOT/logos
        logos_dir = settings.MEDIA_ROOT / 'logos'
        logos_dir.mkdir(parents=True, exist_ok=True)
        test_file = logos_dir / 'test_endpoint_logo.png'
        with open(test_file, 'wb') as f:
            f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
        
        client = Client()
        response = client.get('/media/logos/test_endpoint_logo.png')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        
        # Limpieza
        if test_file.exists():
            test_file.unlink()

from django.contrib.auth import get_user_model
from contacts.models import Tag, Contact

User = get_user_model()

class CampaignAudienceManagementTestCase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name="Org Audiencias Test",
            trade_name="Humm Audiencias",
            email="audiencias@humm.cl"
        )
        self.user = User.objects.create_user(
            email="admin_aud@humm.cl",
            username="admin_aud",
            password="testpassword123",
            organization=self.org,
            role="org_admin"
        )
        self.tag_pruebas = Tag.objects.create(
            organization=self.org,
            name="Contactos de Prueba"
        )
        self.tag_clientes = Tag.objects.create(
            organization=self.org,
            name="Clientes Reales"
        )
        
        self.c1 = Contact.objects.create(
            organization=self.org,
            email="prueba1@alphalabs.cl",
            first_name="Prueba",
            status="active"
        )
        self.c1.tags.add(self.tag_pruebas)

        self.c2 = Contact.objects.create(
            organization=self.org,
            email="cliente1@alphalabs.cl",
            first_name="Cliente",
            status="active"
        )
        self.c2.tags.add(self.tag_clientes)

        self.campaign = Campaign.objects.create(
            organization=self.org,
            name="Campaña Test Audiencia",
            subject="Prueba Inicial",
            sender_name="Humm",
            sender_email="hola@humm.cl",
            target_tag=self.tag_pruebas,
            created_by=self.user
        )

        self.client = Client()
        self.client.login(username="admin_aud", password="testpassword123")
        # Establecer la organización activa en la sesión
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def test_update_audience_to_different_tag(self):
        response = self.client.post(
            f"/campaigns/{self.campaign.id}/audience/",
            data={'target_tag': self.tag_clientes.id},
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['target_tag_name'], self.tag_clientes.name)
        
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.target_tag, self.tag_clientes)

    def test_update_audience_to_all_contacts(self):
        response = self.client.post(
            f"/campaigns/{self.campaign.id}/audience/",
            data={'target_tag': ''},
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['target_tag_name'], 'Todos los contactos activos')
        
        self.campaign.refresh_from_db()
        self.assertIsNone(self.campaign.target_tag)

    from unittest.mock import patch

    @patch('campaigns.views.dispatch_campaign_task')
    def test_campaign_send_updates_audience_inline(self, mock_dispatch):
        # Despachar envío pasando target_tag en el cuerpo
        response = self.client.post(
            f"/campaigns/{self.campaign.id}/send/",
            data={'target_tag': self.tag_clientes.id},
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.target_tag, self.tag_clientes)
        self.assertTrue(mock_dispatch.called)

    def test_campaign_duplicate_with_custom_audience(self):
        response = self.client.post(
            f"/campaigns/{self.campaign.id}/duplicate/",
            data={'name': 'Copia Clientes Reales', 'target_tag': self.tag_clientes.id}
        )
        self.assertEqual(response.status_code, 302)
        
        duplicate = Campaign.objects.filter(name='Copia Clientes Reales').first()
        self.assertIsNotNone(duplicate)
        self.assertEqual(duplicate.target_tag, self.tag_clientes)
        self.assertEqual(duplicate.subject, self.campaign.subject)

