from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from organizations.models import Organization, SuppressionEntry
from contacts.models import Contact, Tag
from campaigns.models import Campaign, CampaignLink, TrackingEvent
from opportunities.models import Opportunity
from campaigns.tasks import send_campaign_task, render_blocks_to_html
from django.test import Client

class ResendBroadcastsValidationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.org_a = Organization.objects.create(
            name="Organización Alpha",
            trade_name="Alpha Labs",
            default_sender_name="Alpha",
            default_sender_email="contacto@alphalabs.cl",
            default_reply_to="soporte@alphalabs.cl"
        )
        self.org_b = Organization.objects.create(
            name="Organización Beta",
            trade_name="Beta Corp",
            default_sender_name="Beta",
            default_sender_email="contacto@betacorp.cl"
        )

        self.campaign_a = Campaign.objects.create(
            organization=self.org_a,
            name="Campaña Alpha Lanzamiento",
            subject="Gran Novedad Alpha",
            sender_name="Alpha Labs",
            sender_email="contacto@alphalabs.cl",
            reply_to="soporte@alphalabs.cl",
            content_blocks=[
                {"type": "title", "content": {"text": "Hola {{ first_name }}"}},
                {"type": "text", "content": {"text": "Te presentamos la solución para {{ company }}."}},
                {"type": "cta", "content": {"text": "CONOCER MÁS", "url": "https://alphalabs.cl/demo", "link_type": "conversion", "service_interest": "Demo Pro"}},
                {"type": "footer"}
            ],
            status='draft'
        )
        self.link_cta = CampaignLink.objects.create(
            campaign=self.campaign_a,
            original_url="https://alphalabs.cl/demo",
            link_type="conversion",
            service_interest="Demo Pro",
            token="token_cta_alpha"
        )

    def test_01_two_internal_addresses_send_click_and_unsub(self):
        """
        Validación 1:
        Envío a dos direcciones internas de prueba: personalización, clic y baja.
        """
        contact1 = Contact.objects.create(
            organization=self.org_a,
            email="interno1@alphalabs.cl",
            first_name="Constanza",
            last_name="Valenzuela",
            company="Alpha Interno",
            status="active"
        )
        contact2 = Contact.objects.create(
            organization=self.org_a,
            email="interno2@alphalabs.cl",
            first_name="Rodrigo",
            last_name="Merino",
            company="Alpha Staff",
            status="active"
        )

        mock_bc_create = MagicMock(return_value={'id': 'bcast_int_123'})
        mock_bc_send = MagicMock(return_value={'id': 'bcast_int_123'})
        mock_seg_create = MagicMock(return_value={'id': 'seg_int_123'})
        mock_contact_segments_add = MagicMock(return_value={'id': 'cs_ok'})
        mock_emails_send = MagicMock()

        # Mocking Resend API
        with patch('resend.Broadcasts.create', mock_bc_create), \
             patch('resend.Broadcasts.send', mock_bc_send), \
             patch('resend.Broadcasts.get', return_value={'id': 'bcast_int_123', 'status': 'draft'}), \
             patch('resend.Segments.create', mock_seg_create), \
             patch('resend.Segments.get', return_value={'id': 'seg_int_123'}), \
             patch('resend.ContactSegments.add', mock_contact_segments_add), \
             patch('resend.Contacts.get', return_value={'id': 'cnt_mock', 'unsubscribed': False}), \
             patch('resend.Contacts.update', return_value={'id': 'cnt_mock'}), \
             patch('resend.Emails.send', mock_emails_send):

            send_campaign_task(self.campaign_a.id)

        # 1. Comprobaciones de envío
        mock_emails_send.assert_not_called() # No llamadas a /emails para la campaña masiva
        self.assertEqual(mock_bc_create.call_count, 1)
        self.assertEqual(mock_bc_send.call_count, 1)

        self.campaign_a.refresh_from_db()
        self.assertEqual(self.campaign_a.status, 'sent')
        self.assertEqual(self.campaign_a.broadcast_id, 'bcast_int_123')
        self.assertEqual(self.campaign_a.resend_segment_id, 'seg_int_123')

        # Comprobar que ambos contactos fueron asociados al segmento
        added_emails = [c[0][0]['email'] for c in mock_contact_segments_add.call_args_list]
        self.assertIn("interno1@alphalabs.cl", added_emails)
        self.assertIn("interno2@alphalabs.cl", added_emails)

        # Comprobar personalización del HTML del Broadcast
        sent_html = mock_bc_create.call_args[0][0]['html']
        self.assertIn("{{{FIRST_NAME|Hola}}}", sent_html)
        self.assertIn("{{{company|}}}", sent_html)
        self.assertIn("{{{RESEND_UNSUBSCRIBE_URL}}}", sent_html)
        self.assertIn(f"/t/{self.link_cta.token}/?e=" + "{{{EMAIL}}}", sent_html)

        # 2. Comprobar Clic y Conversión a Oportunidad para interno1
        click_url = f"/t/{self.link_cta.token}/?e=interno1@alphalabs.cl"
        resp = self.client.get(click_url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "https://alphalabs.cl/demo")

        # Verificar TrackingEvent de clic
        click_event = TrackingEvent.objects.filter(
            campaign=self.campaign_a,
            contact=contact1,
            event_type='click',
            link=self.link_cta
        )
        self.assertEqual(click_event.count(), 1)

        # Verificar creación de Oportunidad Comercial
        opp = Opportunity.objects.filter(
            organization=self.org_a,
            contact=contact1,
            campaign=self.campaign_a,
            link=self.link_cta
        ).first()
        self.assertIsNotNone(opp)
        self.assertIn("Constanza", opp.title)
        self.assertEqual(opp.interest_topic, "Demo Pro")

        # Clic repetido no debe duplicar el evento
        self.client.get(click_url)
        self.assertEqual(TrackingEvent.objects.filter(campaign=self.campaign_a, contact=contact1, event_type='click').count(), 1)

        # 3. Comprobar Webhook de Baja para interno2
        webhook_unsub_payload = {
            "type": "contact.updated",
            "data": {
                "email": "interno2@alphalabs.cl",
                "unsubscribed": True,
                "broadcast_id": "bcast_int_123"
            }
        }
        wh_resp = self.client.post(
            '/campaigns/webhooks/resend/',
            data=webhook_unsub_payload,
            content_type='application/json'
        )
        self.assertEqual(wh_resp.status_code, 200)

        # Verificar reflejo de baja en Hummailing
        contact2.refresh_from_db()
        self.assertEqual(contact2.status, 'unsubscribed')
        self.assertTrue(SuppressionEntry.objects.filter(organization=self.org_a, email="interno2@alphalabs.cl").exists())
        self.assertTrue(TrackingEvent.objects.filter(campaign=self.campaign_a, contact=contact2, event_type='unsub').exists())

    def test_02_simulation_300_recipients_and_retry_idempotency(self):
        """
        Validación 2:
        Simulación de 300 destinatarios y de un reintento, sin envíos duplicados ni llamadas individuales a /emails.
        """
        # Crear 300 contactos activos en Org A
        contacts_to_create = [
            Contact(
                organization=self.org_a,
                email=f"recipient_{i:03d}@empresa{i}.cl",
                first_name=f"Nombre{i}",
                last_name=f"Apellido{i}",
                company=f"Empresa {i}",
                status="active"
            ) for i in range(1, 301)
        ]
        Contact.objects.bulk_create(contacts_to_create)

        mock_bc_create = MagicMock(return_value={'id': 'bcast_300_recipients'})
        mock_bc_send = MagicMock(return_value={'id': 'bcast_300_recipients'})
        mock_emails_send = MagicMock()
        mock_contact_segments_add = MagicMock(return_value={'id': 'cs_ok'})

        with patch('resend.Broadcasts.create', mock_bc_create), \
             patch('resend.Broadcasts.send', mock_bc_send), \
             patch('resend.Broadcasts.get', return_value={'id': 'bcast_300_recipients', 'status': 'draft'}), \
             patch('resend.Segments.create', return_value={'id': 'seg_300_test'}), \
             patch('resend.Segments.get', return_value={'id': 'seg_300_test'}), \
             patch('resend.ContactSegments.add', mock_contact_segments_add), \
             patch('resend.Contacts.get', return_value={'id': 'cnt_300', 'unsubscribed': False}), \
             patch('resend.Contacts.update', return_value={'id': 'cnt_300'}), \
             patch('resend.Emails.send', mock_emails_send):

            # Ejecución inicial
            send_campaign_task(self.campaign_a.id)

        # Verificación: NO llamadas a /emails
        mock_emails_send.assert_not_called()
        # Verificación: 1 sola creación y 1 solo envío de Broadcast
        self.assertEqual(mock_bc_create.call_count, 1)
        self.assertEqual(mock_bc_send.call_count, 1)
        # Verificación: 300 contactos añadidos al segmento
        self.assertEqual(mock_contact_segments_add.call_count, 300)

        self.campaign_a.refresh_from_db()
        self.assertEqual(self.campaign_a.status, 'sent')
        self.assertEqual(self.campaign_a.broadcast_id, 'bcast_300_recipients')
        self.assertEqual(TrackingEvent.objects.filter(campaign=self.campaign_a, event_type='sent').count(), 300)

        # SIMULACIÓN DE REINTENTO (Doble clic o reejecución accidental)
        mock_bc_create.reset_mock()
        mock_bc_send.reset_mock()
        mock_contact_segments_add.reset_mock()

        # En el reintento, Resend reporta status 'sent' o 'queued'
        with patch('resend.Broadcasts.create', mock_bc_create), \
             patch('resend.Broadcasts.send', mock_bc_send), \
             patch('resend.Broadcasts.get', return_value={'id': 'bcast_300_recipients', 'status': 'sent'}), \
             patch('resend.ContactSegments.add', mock_contact_segments_add), \
             patch('resend.Emails.send', mock_emails_send):

            send_campaign_task(self.campaign_a.id)

        # CERO llamadas remotas en el reintento
        mock_bc_create.assert_not_called()
        mock_bc_send.assert_not_called()
        mock_contact_segments_add.assert_not_called()
        mock_emails_send.assert_not_called()

        # Los TrackingEvents se mantienen intactos en 300
        self.assertEqual(TrackingEvent.objects.filter(campaign=self.campaign_a, event_type='sent').count(), 300)

    def test_03_exclusion_of_unsubscribed_and_other_organizations(self):
        """
        Validación 3:
        Exclusión de contactos dados de baja y de otras organizaciones.
        """
        # Contacto habilitado Org A
        active_a = Contact.objects.create(
            organization=self.org_a,
            email="habilitado_a@alphalabs.cl",
            status="active"
        )
        # Contacto dado de baja localmente Org A
        unsub_a = Contact.objects.create(
            organization=self.org_a,
            email="baja_local@alphalabs.cl",
            status="unsubscribed"
        )
        # Contacto en SuppressionEntry Org A
        suppressed_a = Contact.objects.create(
            organization=self.org_a,
            email="suprimido@alphalabs.cl",
            status="active"
        )
        SuppressionEntry.objects.create(
            organization=self.org_a,
            email="suprimido@alphalabs.cl",
            reason="unsub"
        )
        # Contacto activo en Hummailing pero dado de baja previamente en Resend
        unsub_in_resend_a = Contact.objects.create(
            organization=self.org_a,
            email="baja_resend@alphalabs.cl",
            status="active"
        )

        # Contactos de Organización B (deben aislarse completamente)
        contact_b = Contact.objects.create(
            organization=self.org_b,
            email="contacto_b@betacorp.cl",
            status="active"
        )

        def mock_resend_get(email=None, id=None):
            if email == "baja_resend@alphalabs.cl":
                return {'id': 'cnt_resend_unsub', 'unsubscribed': True, 'email': email}
            elif email == "habilitado_a@alphalabs.cl":
                return {'id': 'cnt_resend_active', 'unsubscribed': False, 'email': email}
            raise Exception("Contact not found")

        mock_contact_segments_add = MagicMock(return_value={'id': 'cs_ok'})

        with patch('resend.Broadcasts.create', return_value={'id': 'bcast_excl_test'}), \
             patch('resend.Broadcasts.send', return_value={'id': 'bcast_excl_test'}), \
             patch('resend.Broadcasts.get', return_value={'id': 'bcast_excl_test', 'status': 'draft'}), \
             patch('resend.Segments.create', return_value={'id': 'seg_excl_test'}), \
             patch('resend.Segments.get', return_value={'id': 'seg_excl_test'}), \
             patch('resend.ContactSegments.add', mock_contact_segments_add), \
             patch('resend.Contacts.get', side_effect=mock_resend_get), \
             patch('resend.Contacts.update', return_value={'id': 'ok'}), \
             patch('resend.Emails.send') as mock_emails_send:

            send_campaign_task(self.campaign_a.id)

        # Verificar que ÚNICAMENTE se agregó el contacto habilitado de Org A
        synced_emails = [c[0][0]['email'] for c in mock_contact_segments_add.call_args_list]
        self.assertEqual(len(synced_emails), 1)
        self.assertIn("habilitado_a@alphalabs.cl", synced_emails)

        # Verificar exclusiones
        self.assertNotIn("contacto_b@betacorp.cl", synced_emails)
        self.assertNotIn("baja_local@alphalabs.cl", synced_emails)
        self.assertNotIn("suprimido@alphalabs.cl", synced_emails)
        self.assertNotIn("baja_resend@alphalabs.cl", synced_emails)

        # Verificar que el contacto que estaba dado de baja en Resend se reflejó como baja en Hummailing
        unsub_in_resend_a.refresh_from_db()
        self.assertEqual(unsub_in_resend_a.status, 'unsubscribed')
        self.assertTrue(SuppressionEntry.objects.filter(organization=self.org_a, email="baja_resend@alphalabs.cl").exists())
