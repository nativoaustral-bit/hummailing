"""
Suite de Pruebas de Integración 04A: Hummailing → Humm Control Center (HCC v0.1).
Valida:
1. Activación legítima únicamente con primer envío exitoso a contactos reales.
2. Exclusión de borradores, campañas vacías y envíos de prueba.
3. Atribución estricta por persona (sender_user > created_by > no inventar titular).
4. Prueba adversarial exhaustiva de Zero PII (Contact, Opportunity, Email Body).
5. Snapshot inmutable congelado al encolar en HCCOutboxEvent.
6. Resiliencia total ante caída de HCC (la campaña no se afecta y outbox queda PENDING).
7. Manejo de errores permanentes (401/403 -> ERROR).
8. Comandos de gestión: replay_hcc_outbox y sync_existing_hummailing_users.
"""

import json
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from django.core.management import call_command
import io

from core.models import User, HCCOutboxEvent, HCCOutboxStatus
from organizations.models import Organization
from contacts.models import Contact
from campaigns.models import Campaign, TrackingEvent
from opportunities.models import Opportunity
from core.services.hcc_service import (
    build_tool_activated_payload,
    enqueue_tool_activation,
    dispatch_outbox_event,
    check_and_trigger_activation
)


class HummailingHCCIntegrationTests(TestCase):

    def setUp(self):
        # 1. Crear Organización Titular
        self.org = Organization.objects.create(
            name="Pastelería El Secreto SpA",
            trade_name="Pastelería El Secreto",
            email="contacto@elsecreto.cl",
            phone="+56912345678",
            status="active"
        )

        # 2. Crear Titular (User)
        self.titular = User.objects.create_user(
            username="carolina.titular",
            email="carolina@elsecreto.cl",
            password="Segura#2026",
            first_name="Carolina",
            last_name="Soto",
            phone="+56987654321",
            role="org_admin",
            organization=self.org
        )

        # 3. Crear Contacto Privado
        self.contacto = Contact.objects.create(
            organization=self.org,
            email="cliente.privado@example.com",
            first_name="Juan",
            last_name="Pérez",
            phone="+56911112222",
            company="Empresa Cliente",
            status="active"
        )

        # 4. Crear Campaña
        self.campaign = Campaign.objects.create(
            organization=self.org,
            name="Lanzamiento Tortas Gourmet",
            subject="¡Prueba nuestras nuevas tortas!",
            status="draft",
            created_by=self.titular,
            content_blocks=[
                {"type": "title", "content": {"text": "Nueva Carta Gourmet"}},
                {"type": "text", "content": {"text": "Oferta exclusiva para clientes."}}
            ]
        )

    def test_activation_triggered_on_first_real_campaign_sent(self):
        """Prueba 1: TOOL_ACTIVATED se genera tras el primer envío real exitoso."""
        with patch('resend.Emails.send', return_value={'id': 'msg_test_123'}), \
             patch('resend.Broadcasts.create', return_value={'id': 'bcast_test_123'}), \
             patch('resend.Broadcasts.send', return_value={'id': 'bcast_test_123'}), \
             patch('resend.Segments.create', return_value={'id': 'seg_test_123'}), \
             patch('resend.Segments.get', return_value={'id': 'seg_test_123'}), \
             patch('resend.Contacts.get', return_value={'id': 'cnt_test_123', 'unsubscribed': False}), \
             patch('resend.ContactSegments.add', return_value={'id': 'cs_test_123'}), \
             patch('core.services.hcc_service.send_event_to_hcc', return_value={'success': True, 'status_code': 201, 'duplicate': False, 'error': '', 'is_permanent': False, 'data': {}}):
            
            from campaigns.tasks import send_campaign_task
            with self.captureOnCommitCallbacks(execute=True):
                send_campaign_task(self.campaign.id, sender_user_id=self.titular.id)

        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, 'sent')
        self.assertTrue(TrackingEvent.objects.filter(campaign=self.campaign, event_type='sent').exists())

        # Verificar Outbox Event
        event_id = f"hummailing-activation-user-{self.titular.id}"
        outbox = HCCOutboxEvent.objects.get(event_id=event_id)
        self.assertEqual(outbox.event_type, 'TOOL_ACTIVATED')
        self.assertEqual(outbox.user, self.titular)
        self.assertEqual(outbox.status, HCCOutboxStatus.SENT)
        self.assertEqual(outbox.payload['user']['external_id'], str(self.titular.id))
        self.assertEqual(outbox.payload['user']['name'], "Carolina Soto")
        self.assertEqual(outbox.payload['user']['email'], "carolina@elsecreto.cl")
        self.assertEqual(outbox.payload['data']['account_name'], "Pastelería El Secreto")
        self.assertEqual(outbox.payload['data']['contacts_total'], 1)
        self.assertEqual(outbox.payload['data']['campaigns_sent_total'], 1)

    def test_no_activation_on_test_email(self):
        """Prueba 2: Un envío de prueba (test_email) NO genera TOOL_ACTIVATED."""
        with patch('resend.Emails.send', return_value={'id': 'msg_test_single'}):
            from campaigns.tasks import send_campaign_task
            with self.captureOnCommitCallbacks(execute=True):
                send_campaign_task(self.campaign.id, test_email="prueba@elsecreto.cl", sender_user_id=self.titular.id)

        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, 'draft')
        self.assertEqual(HCCOutboxEvent.objects.count(), 0)

    def test_no_activation_on_zero_successful_sends(self):
        """Prueba 3: Campaña con cero envíos exitosos NO activa la herramienta."""
        with patch('resend.Broadcasts.create', side_effect=Exception("Broadcast failed")), \
             patch('resend.Emails.send', side_effect=Exception("SMTP Connection Refused")):
            from campaigns.tasks import send_campaign_task
            with self.captureOnCommitCallbacks(execute=True):
                send_campaign_task(self.campaign.id, sender_user_id=self.titular.id)

        self.campaign.refresh_from_db()
        self.assertFalse(TrackingEvent.objects.filter(campaign=self.campaign, event_type='sent').exists())
        self.assertEqual(HCCOutboxEvent.objects.count(), 0)

    def test_attribution_priority_sender_over_created_by_and_no_arbitrary_admin(self):
        """Prueba 4: Atribución estricta: sender_user > created_by. Si no hay, NO inventa org_admin."""
        editor = User.objects.create_user(
            username="editor.juan",
            email="juan@elsecreto.cl",
            first_name="Juan",
            last_name="Editor",
            role="campaign_editor",
            organization=self.org
        )

        # Caso A: sender_user explícito tiene prioridad sobre created_by
        self.campaign.status = 'sent'
        self.campaign.save()
        TrackingEvent.objects.create(campaign=self.campaign, contact=self.contacto, event_type='sent')

        with self.captureOnCommitCallbacks(execute=True):
            ev_editor = check_and_trigger_activation(self.campaign, sender_user=editor)
        self.assertIsNotNone(ev_editor)
        self.assertEqual(ev_editor.user, editor)
        self.assertEqual(ev_editor.event_id, f"hummailing-activation-user-{editor.id}")

        # Caso B: Sin created_by y sin sender_user -> NO debe asignar a org_admin
        other_campaign = Campaign.objects.create(
            organization=self.org,
            name="Campaña Huérfana",
            subject="Sin creador",
            status="sent",
            created_by=None
        )
        TrackingEvent.objects.create(campaign=other_campaign, contact=self.contacto, event_type='sent')

        with self.captureOnCommitCallbacks(execute=True):
            ev_orphan = check_and_trigger_activation(other_campaign, sender_user=None)
        self.assertIsNone(ev_orphan, "No debe inventar titular cuando no hay evidencia fidedigna")

    def test_complete_adversarial_zero_pii_contact_and_opportunity(self):
        """Prueba 5: Test adversarial: Zero PII de Contact, Opportunity y cuerpo de email."""
        titular_name = "TITULAR_HUMMAILING_TEST"
        titular_user = User.objects.create_user(
            username="titular.test",
            email="titular@test.cl",
            first_name=titular_name,
            last_name="Prueba",
            phone="+56988887777",
            organization=self.org
        )

        contacto_privado = Contact.objects.create(
            organization=self.org,
            email="cliente.adversarial@example.com",
            first_name="CONTACTO_PRIVADO_HUMMAILING",
            last_name="Destinatario",
            phone="+56911112222",
            company="COMPANIA_PRIVADA_RESTRINGIDA",
            status="active"
        )

        opportunity_privada = Opportunity.objects.create(
            organization=self.org,
            contact=contacto_privado,
            campaign=self.campaign,
            title="OPORTUNIDAD_PRIVADA_HUMMAILING",
            interest_topic="TORTAS_PREMIUM_INTERES",
            status="new",
            priority="high"
        )

        payload = build_tool_activated_payload(titular_user, campaign=self.campaign)
        payload_str = json.dumps(payload, ensure_ascii=False)

        # 1. Debe contener datos del titular
        self.assertIn(titular_name, payload_str)
        self.assertIn("titular@test.cl", payload_str)
        self.assertIn("+56988887777", payload_str)

        # 2. PROHIBIDO: Ningún dato del contacto privado
        self.assertNotIn("CONTACTO_PRIVADO_HUMMAILING", payload_str)
        self.assertNotIn("cliente.adversarial@example.com", payload_str)
        self.assertNotIn("+56911112222", payload_str)
        self.assertNotIn("COMPANIA_PRIVADA_RESTRINGIDA", payload_str)

        # 3. PROHIBIDO: Ningún dato de la oportunidad
        self.assertNotIn("OPORTUNIDAD_PRIVADA_HUMMAILING", payload_str)
        self.assertNotIn("TORTAS_PREMIUM_INTERES", payload_str)

        # 4. PROHIBIDO: Ningún dato del contenido/asunto de la campaña
        self.assertNotIn("Lanzamiento Tortas Gourmet", payload_str)
        self.assertNotIn("Prueba nuestras nuevas tortas", payload_str)
        self.assertNotIn("Nueva Carta Gourmet", payload_str)

        # 5. Estructura de contrato limpia
        self.assertNotIn('attribution', payload)
        self.assertNotIn('organization', payload)  # account_name está en data
        self.assertEqual(payload['data']['account_name'], "Pastelería El Secreto")

    def test_idempotency_frozen_payload(self):
        """Prueba 6: Payload congelado y unicidad de HCCOutboxEvent."""
        ev1, created1 = enqueue_tool_activation(self.titular, campaign=self.campaign)
        self.assertTrue(created1)

        contacts_before = ev1.payload['data']['contacts_total']

        # Modificar contactos en la organización
        Contact.objects.create(
            organization=self.org,
            email="otro.contacto@example.com",
            first_name="Segundo",
            status="active"
        )

        # Segundo intento de enqueue -> devuelve el existente con payload idéntico
        ev2, created2 = enqueue_tool_activation(self.titular, campaign=self.campaign)
        self.assertFalse(created2)
        self.assertEqual(ev1.pk, ev2.pk)
        self.assertEqual(ev2.payload['data']['contacts_total'], contacts_before)

    def test_resilience_hcc_down_campaign_unaffected(self):
        """Prueba 7: Falla en red hacia HCC deja outbox en PENDING sin afectar la campaña."""
        with patch('resend.Emails.send', return_value={'id': 'msg_ok'}), \
             patch('resend.Broadcasts.create', return_value={'id': 'bcast_resilience_123'}), \
             patch('resend.Broadcasts.send', return_value={'id': 'bcast_resilience_123'}), \
             patch('resend.Segments.create', return_value={'id': 'seg_resilience_123'}), \
             patch('resend.Segments.get', return_value={'id': 'seg_resilience_123'}), \
             patch('resend.Contacts.get', return_value={'id': 'cnt_resilience_123', 'unsubscribed': False}), \
             patch('resend.ContactSegments.add', return_value={'id': 'cs_resilience_123'}), \
             patch('core.services.hcc_service.send_event_to_hcc', return_value={
                 'success': False,
                 'status_code': 0,
                 'duplicate': False,
                 'error': 'Connection timed out',
                 'is_permanent': False,
                 'data': None
             }):
            from campaigns.tasks import send_campaign_task
            with self.captureOnCommitCallbacks(execute=True):
                send_campaign_task(self.campaign.id, sender_user_id=self.titular.id)

        # Campaña completó con éxito
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, 'sent')

        # Outbox queda PENDING con 1 intento y error registrado
        outbox = HCCOutboxEvent.objects.get(event_id=f"hummailing-activation-user-{self.titular.id}")
        self.assertEqual(outbox.status, HCCOutboxStatus.PENDING)
        self.assertEqual(outbox.attempts, 1)
        self.assertIn("Connection timed out", outbox.last_error)

    def test_permanent_error_marks_outbox_error(self):
        """Prueba 8: Error 401/403 permanente marca outbox como ERROR."""
        outbox, _ = enqueue_tool_activation(self.titular, campaign=self.campaign)

        with patch('core.services.hcc_service.send_event_to_hcc', return_value={
            'success': False,
            'status_code': 401,
            'duplicate': False,
            'error': 'HTTP 401: Unauthorized API Key',
            'is_permanent': True,
            'data': None
        }):
            dispatch_outbox_event(outbox)

        outbox.refresh_from_db()
        self.assertEqual(outbox.status, HCCOutboxStatus.ERROR)
        self.assertEqual(outbox.attempts, 1)
        self.assertIn("HTTP 401", outbox.last_error)

    def test_replay_outbox_command(self):
        """Prueba 9: Comando replay_hcc_outbox reintenta y actualiza a SENT."""
        outbox, _ = enqueue_tool_activation(self.titular, campaign=self.campaign)
        self.assertEqual(outbox.status, HCCOutboxStatus.PENDING)

        with patch('core.services.hcc_service.send_event_to_hcc', return_value={
            'success': True,
            'status_code': 201,
            'duplicate': False,
            'error': '',
            'is_permanent': False,
            'data': {'status': 'success'}
        }):
            out = io.StringIO()
            call_command('replay_hcc_outbox', limit=10, stdout=out)
            output = out.getvalue()
            self.assertIn("Entregado exitosamente", output)

        outbox.refresh_from_db()
        self.assertEqual(outbox.status, HCCOutboxStatus.SENT)
        self.assertIsNotNone(outbox.sent_at)

    def test_sync_existing_hummailing_users_dry_run_and_execution(self):
        """Prueba 10: Comando sync_existing_hummailing_users: dry-run y backfill real."""
        # Preparar campaña enviada legítima histórica
        hist_campaign = Campaign.objects.create(
            organization=self.org,
            name="Campaña Histórica 2026",
            status="sent",
            sent_at=timezone.now(),
            created_by=self.titular
        )
        TrackingEvent.objects.create(campaign=hist_campaign, contact=self.contacto, event_type='sent')

        # 1. Ejecutar Dry-Run
        out_dry = io.StringIO()
        call_command('sync_existing_hummailing_users', dry_run=True, stdout=out_dry)
        dry_output = out_dry.getvalue()

        self.assertIn("[DRY-RUN COMPLETADO]", dry_output)
        self.assertIn("carolina.titular", dry_output)
        self.assertEqual(HCCOutboxEvent.objects.count(), 0)

        # 2. Ejecutar Backfill Real
        with patch('core.services.hcc_service.send_event_to_hcc', return_value={
            'success': True,
            'status_code': 201,
            'duplicate': False,
            'error': '',
            'is_permanent': False,
            'data': {'status': 'success'}
        }):
            out_real = io.StringIO()
            call_command('sync_existing_hummailing_users', stdout=out_real)
            real_output = out_real.getvalue()
            self.assertIn("[BACKFILL COMPLETADO]", real_output)

        event_id = f"hummailing-activation-user-{self.titular.id}"
        outbox = HCCOutboxEvent.objects.get(event_id=event_id)
        self.assertEqual(outbox.status, HCCOutboxStatus.SENT)
