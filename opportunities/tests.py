from django.test import TestCase, Client
from organizations.models import Organization, ActivityLog
from core.models import User, Lead
from contacts.models import Contact
from opportunities.models import Opportunity

class OpportunityDeleteTestCase(TestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(
            name="Org 1",
            trade_name="Org 1 Trade",
            email="org1@test.com"
        )
        self.org2 = Organization.objects.create(
            name="Org 2",
            trade_name="Org 2 Trade",
            email="org2@test.com"
        )
        
        self.admin_org1 = User.objects.create_user(
            username="admin1",
            email="admin1@test.com",
            password="password123",
            role="org_admin",
            organization=self.org1
        )
        self.editor_org1 = User.objects.create_user(
            username="editor1",
            email="editor1@test.com",
            password="password123",
            role="campaign_editor",
            organization=self.org1
        )
        self.viewer_org1 = User.objects.create_user(
            username="viewer1",
            email="viewer1@test.com",
            password="password123",
            role="viewer",
            organization=self.org1
        )
        self.admin_org2 = User.objects.create_user(
            username="admin2",
            email="admin2@test.com",
            password="password123",
            role="org_admin",
            organization=self.org2
        )
        
        self.contact1 = Contact.objects.create(
            organization=self.org1,
            email="contact1@test.com",
            first_name="Juan",
            last_name="Perez"
        )
        self.contact2 = Contact.objects.create(
            organization=self.org2,
            email="contact2@test.com",
            first_name="Maria",
            last_name="Gomez"
        )
        
        self.opp1 = Opportunity.objects.create(
            organization=self.org1,
            contact=self.contact1,
            title="Lead de Prueba 1",
            status="new"
        )
        self.opp2 = Opportunity.objects.create(
            organization=self.org1,
            contact=self.contact1,
            title="Lead de Prueba 2",
            status="new"
        )
        self.opp_org2 = Opportunity.objects.create(
            organization=self.org2,
            contact=self.contact2,
            title="Lead Org 2",
            status="new"
        )
        
        self.client = Client()

    def test_org_admin_can_delete_single_opportunity(self):
        """Un administrador de organización puede eliminar una oportunidad de prueba."""
        self.client.force_login(self.admin_org1)
        response = self.client.post(f'/opportunities/{self.opp1.id}/delete/', follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Debe haber desaparecido de la BD
        self.assertFalse(Opportunity.objects.filter(id=self.opp1.id).exists())
        # Y debe registrar en ActivityLog
        self.assertTrue(ActivityLog.objects.filter(
            organization=self.org1,
            action="Eliminación de Oportunidad"
        ).exists())

    def test_campaign_editor_can_delete_single_opportunity(self):
        """Un editor de campañas también puede eliminar una oportunidad."""
        self.client.force_login(self.editor_org1)
        response = self.client.post(f'/opportunities/{self.opp2.id}/delete/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Opportunity.objects.filter(id=self.opp2.id).exists())

    def test_viewer_cannot_delete_opportunity(self):
        """Un visualizador/analista no puede eliminar oportunidades (403)."""
        self.client.force_login(self.viewer_org1)
        response = self.client.post(f'/opportunities/{self.opp1.id}/delete/', follow=True)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Opportunity.objects.filter(id=self.opp1.id).exists())

    def test_cross_tenant_isolation_on_delete(self):
        """Un usuario de Org 2 no puede eliminar una oportunidad de Org 1 (404)."""
        self.client.force_login(self.admin_org2)
        response = self.client.post(f'/opportunities/{self.opp1.id}/delete/')
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Opportunity.objects.filter(id=self.opp1.id).exists())

    def test_bulk_delete_opportunities(self):
        """Eliminación masiva de oportunidades seleccionadas dentro de la misma organización."""
        self.client.force_login(self.admin_org1)
        response = self.client.post('/opportunities/bulk-delete/', {
            'selected_ids': [self.opp1.id, self.opp2.id, self.opp_org2.id]
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # opp1 y opp2 deben haberse borrado
        self.assertFalse(Opportunity.objects.filter(id=self.opp1.id).exists())
        self.assertFalse(Opportunity.objects.filter(id=self.opp2.id).exists())
        # opp_org2 NO debe haberse borrado porque pertenece a otra organización
        self.assertTrue(Opportunity.objects.filter(id=self.opp_org2.id).exists())


class LandingLeadDeleteTestCase(TestCase):
    def setUp(self):
        self.humm_admin = User.objects.create_user(
            username="masteradmin",
            email="master@humm.cl",
            password="password123",
            role="humm_admin"
        )
        self.lead1 = Lead.objects.create(
            name="Lead Test 1",
            company_name="Empresa Test 1",
            email="lead1@test.com",
            phone="+56911111111",
            source="Landing Hummailing"
        )
        self.lead2 = Lead.objects.create(
            name="Lead Test 2",
            company_name="Empresa Test 2",
            email="lead2@test.com",
            phone="+56922222222",
            source="Landing Hummailing"
        )
        self.client = Client()

    def test_humm_admin_can_delete_single_landing_lead(self):
        """El administrador master puede eliminar un prospecto capturado."""
        self.client.force_login(self.humm_admin)
        response = self.client.post(f'/humm-admin/leads/{self.lead1.id}/delete/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Lead.objects.filter(id=self.lead1.id).exists())

    def test_humm_admin_can_bulk_delete_landing_leads(self):
        """El administrador master puede eliminar prospectos masivamente."""
        self.client.force_login(self.humm_admin)
        response = self.client.post('/humm-admin/leads/bulk-delete/', {
            'selected_ids': [self.lead1.id, self.lead2.id]
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Lead.objects.filter(id=self.lead1.id).exists())
        self.assertFalse(Lead.objects.filter(id=self.lead2.id).exists())
