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
