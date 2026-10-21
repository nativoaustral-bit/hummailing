"""
Servicio de Integración Hummailing → Humm Control Center (HCC v0.1).
Implementa la Integración 04A:
- Identidad del titular y emisión determinista de TOOL_ACTIVATED.
- Aislamiento absoluto de PII de contactos y oportunidades comerciales.
- Outbox transaccional persistido antes de red, con intento inmediato y cron replay.
- Cero creación de Leads o Personas desde destinatarios de campañas.
"""

import json
import logging
import ssl
import urllib.request
import urllib.error
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models import HCCOutboxEvent, HCCOutboxStatus, User
from contacts.models import Contact

logger = logging.getLogger('hummailing.hcc_integration')


def build_tool_activated_payload(user: User, campaign=None, occurred_at=None) -> dict:
    """
    Construye el payload canónico inmutable para TOOL_ACTIVATED hacia HCC.
    Aplica estrictamente la regla de aislamiento de datos:
    - Incluye ÚNICAMENTE datos del titular (User).
    - Métricas agregadas numéricas mínimas como snapshot al momento de activación.
    - CERO PII de destinatarios (sin emails, nombres, teléfonos ni contenido de correos).
    - CERO datos de oportunidades o eventos de engagement individuales.
    - CERO atribución inventada (no sobrescribe first_source en HCC).
    """
    if occurred_at is None:
        occurred_at = timezone.now()
    if hasattr(occurred_at, 'isoformat'):
        occurred_at_iso = occurred_at.isoformat()
    else:
        occurred_at_iso = str(occurred_at)

    event_id = f"hummailing-activation-user-{user.id}"

    org = getattr(user, 'organization', None)
    if not org and campaign and getattr(campaign, 'organization', None):
        org = campaign.organization

    account_name = ""
    contacts_total = 0
    campaigns_sent_total = 1

    if org:
        account_name = (org.trade_name or org.name or '').strip()
        contacts_total = Contact.objects.filter(organization=org).count()
        from campaigns.models import Campaign
        sent_count = Campaign.objects.filter(organization=org, status='sent').count()
        campaigns_sent_total = max(1, sent_count)

    full_name = (user.get_full_name() or user.username).strip()

    payload = {
        "event_id": event_id,
        "source_system": "HUMMAILING",
        "event_type": "TOOL_ACTIVATED",
        "occurred_at": occurred_at_iso,

        # Identidad técnica inmutable del titular
        "user": {
            "external_id": str(user.id),
            "name": full_name,
            "email": (user.email or '').strip().lower(),
            "phone": (user.phone or '').strip(),
        },

        # Métricas mínimas transversales como snapshot inicial (Zero PII)
        # account_name reside en data para no provocar fusiones erróneas en Organization de HCC
        "data": {
            "tool": "hummailing",
            "account_name": account_name,
            "activation_type": "FIRST_CAMPAIGN_SENT",
            "activated_at": occurred_at_iso,
            "contacts_total": contacts_total,
            "campaigns_sent_total": campaigns_sent_total,
        }
    }

    return payload


def send_event_to_hcc(payload: dict) -> dict:
    """
    Despacha el payload canónico hacia HCC vía HTTP POST con TLS estricto y timeout corto.
    Retorna dict con:
    - success (bool)
    - status_code (int)
    - duplicate (bool)
    - error (str)
    - is_permanent (bool)
    - data (dict)
    """
    api_url = getattr(settings, 'HCC_API_URL', 'https://control.humm.cl/api/v1/events/')
    api_key = getattr(settings, 'HCC_API_KEY', '').strip()

    if not api_key:
        return {
            'success': False,
            'status_code': 0,
            'duplicate': False,
            'error': 'HCC_API_KEY no configurada en entorno privado.',
            'is_permanent': True,
            'data': None
        }

    json_body = json.dumps(payload, ensure_ascii=False).encode('utf-8')

    req = urllib.request.Request(
        api_url,
        data=json_body,
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-API-Key': api_key,
            'User-Agent': 'Hummailing-Integration/0.1',
        },
        method='POST'
    )

    ctx = ssl.create_default_context()
    if not ctx.get_ca_certs():
        import os
        for ca_path in ['/etc/ssl/cert.pem', '/etc/pki/tls/certs/ca-bundle.crt', '/etc/ssl/certs/ca-certificates.crt']:
            if os.path.exists(ca_path):
                try:
                    ctx.load_verify_locations(ca_path)
                    break
                except Exception:
                    pass

    timeout = getattr(settings, 'HCC_READ_TIMEOUT', 3.0)

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as response:
            status_code = response.status
            res_body = response.read().decode('utf-8')
            res_json = json.loads(res_body) if res_body else {}
            is_dup = bool(res_json.get('duplicate') or res_json.get('status') == 'already_processed')
            return {
                'success': True,
                'status_code': status_code,
                'duplicate': is_dup,
                'error': '',
                'is_permanent': False,
                'data': res_json
            }
    except urllib.error.HTTPError as he:
        status_code = he.code
        err_body = he.read().decode('utf-8', errors='replace') if he.fp else ''
        # Errores 4xx son estructurales/permanentes (400, 401, 403, 404, 405)
        is_permanent = status_code in (400, 401, 403, 404, 405)
        err_msg = f"HTTP {status_code}: {err_body[:300].strip()}"
        logger.warning(f"HCC rechazó evento {payload.get('event_id')}: {err_msg}")
        return {
            'success': False,
            'status_code': status_code,
            'duplicate': False,
            'error': err_msg,
            'is_permanent': is_permanent,
            'data': None
        }
    except Exception as exc:
        err_msg = f"Falla de conexión hacia HCC: {str(exc)[:300]}"
        logger.warning(f"Error de red hacia HCC para evento {payload.get('event_id')}: {err_msg}")
        return {
            'success': False,
            'status_code': 0,
            'duplicate': False,
            'error': err_msg,
            'is_permanent': False,
            'data': None
        }


def enqueue_tool_activation(user: User, campaign=None, occurred_at=None) -> tuple:
    """
    Encola el evento TOOL_ACTIVATED en el outbox transaccional de Hummailing.
    Retorna (outbox_event, created).
    El payload queda congelado como snapshot inmutable al momento de creación.
    """
    event_id = f"hummailing-activation-user-{user.id}"

    existing = HCCOutboxEvent.objects.filter(event_id=event_id).first()
    if existing:
        return existing, False

    payload = build_tool_activated_payload(user, campaign=campaign, occurred_at=occurred_at)

    outbox_event, created = HCCOutboxEvent.objects.get_or_create(
        event_id=event_id,
        defaults={
            'event_type': 'TOOL_ACTIVATED',
            'user': user,
            'payload': payload,
            'status': HCCOutboxStatus.PENDING,
            'attempts': 0
        }
    )
    return outbox_event, created


def dispatch_outbox_event(outbox_event: HCCOutboxEvent) -> dict:
    """
    Ejecuta el despacho de un HCCOutboxEvent hacia HCC utilizando estrictamente
    su payload congelado. Actualiza el estado a SENT o registra el error.
    """
    if outbox_event.status == HCCOutboxStatus.SENT:
        return {'success': True, 'duplicate': True, 'status': 'ALREADY_SENT'}

    result = send_event_to_hcc(outbox_event.payload)

    if result['success']:
        outbox_event.mark_sent()
        logger.info(f"Evento outbox {outbox_event.event_id} entregado con éxito a HCC (HTTP {result['status_code']}).")
    else:
        outbox_event.mark_failed(result['error'], is_permanent=result['is_permanent'])
        logger.warning(f"Fallo al despachar outbox {outbox_event.event_id}: {result['error']}")

    return result


def process_pending_outbox(limit: int = 20) -> int:
    """
    Procesa un lote de eventos PENDING para el comando replay_hcc_outbox / cron.
    Retorna la cantidad de eventos despachados exitosamente.
    """
    pendientes = HCCOutboxEvent.objects.filter(
        status=HCCOutboxStatus.PENDING
    ).order_by('created_at')[:limit]

    success_count = 0
    for event in pendientes:
        res = dispatch_outbox_event(event)
        if res.get('success'):
            success_count += 1

    return success_count


def check_and_trigger_activation(campaign, sender_user=None):
    """
    Verifica si una campaña enviada cumple con la evidencia real de activación
    y determina de forma estricta al usuario titular atribuible.

    Reglas de Activación (Ajustes 1, 2, 3, 4):
    1. Evidencia combinada:
       - Campaign.status == 'sent'
       - TrackingEvent(event_type='sent') existente para la campaña (>= 1 envío exitoso).
    2. Determinación de titular atribuible:
       - Prioridad 1: sender_user (actor real que inició el despacho).
       - Prioridad 2: campaign.created_by (creador/operador directo de la campaña).
       - Si no existe evidencia suficiente: NO INVENTAR titular (no asignar a org_admin).
    3. Persistencia antes de red:
       - El outbox se guarda localmente (PENDING).
       - El intento de red se ejecuta desacoplado mediante transaction.on_commit().
    """
    # 1. Validar evidencia de campaña enviada real
    if not campaign or campaign.status != 'sent':
        return None

    from campaigns.models import TrackingEvent
    has_successful_sends = TrackingEvent.objects.filter(
        campaign=campaign,
        event_type='sent'
    ).exists()

    if not has_successful_sends:
        logger.info(f"Campaña {campaign.id} no califica para activación: sin eventos 'sent' registrados.")
        return None

    # 2. Determinar usuario atribuible con evidencia fidedigna
    user = None
    if sender_user and isinstance(sender_user, User) and sender_user.is_active:
        user = sender_user
    elif campaign.created_by and campaign.created_by.is_active:
        user = campaign.created_by

    if not user:
        logger.info(f"Campaña {campaign.id} enviada pero sin usuario atribuible demostrable (SKIPPED_NO_RELIABLE_USER).")
        return None

    # 3. Verificar si el usuario ya fue activado previamente
    event_id = f"hummailing-activation-user-{user.id}"
    if HCCOutboxEvent.objects.filter(event_id=event_id).exists():
        return None

    # 4. Encolar en outbox local con snapshot congelado
    occurred_at = campaign.sent_at or timezone.now()
    outbox_event, created = enqueue_tool_activation(user, campaign=campaign, occurred_at=occurred_at)

    # 5. Programar intento inmediato desacoplado tras COMMIT local
    if created:
        def _dispatch():
            try:
                ev = HCCOutboxEvent.objects.filter(pk=outbox_event.pk).first()
                if ev and ev.status == HCCOutboxStatus.PENDING:
                    dispatch_outbox_event(ev)
            except Exception as exc:
                logger.warning(f"Error en intento inmediato de activación HCC para usuario {user.id}: {exc}")

        try:
            transaction.on_commit(_dispatch)
        except Exception:
            # Si no hay bloque de transacción atómica activo (ej. ejecución directa), ejecutar
            _dispatch()

    return outbox_event
