import logging
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from contacts.models import Contact

logger = logging.getLogger(__name__)

UNSUB_SALT = 'hummailing-unsub-token-v1'

def generate_unsubscribe_token(contact=None, contact_id=None, organization_id=None):
    """
    Genera un token criptográfico firmado server-side sin PII (sin incluir email en la URL).
    Payload mínimo: contact_id, organization_id, propósito.
    """
    if contact is not None:
        if hasattr(contact, 'id'):
            c_id = contact.id
            o_id = contact.organization_id
        else:
            c_id = contact
            o_id = contact_id  # segundo argumento posicional si contact es entero
    else:
        c_id = contact_id
        o_id = organization_id
        
    signer = TimestampSigner(salt=UNSUB_SALT)
    payload = f"{c_id}:{o_id}:unsub"
    return signer.sign(payload)

create_unsubscribe_token = generate_unsubscribe_token

def validate_unsubscribe_token(token):
    """
    Valida la firma criptográfica del token y recupera el contacto verificado server-side.
    Comprueba que el contacto pertenezca a la organización firmada.
    No impone una expiración corta para mantener vigencia de correos enviados con anterioridad.
    Retorna (contact, None) o (None, error_message).
    """
    if not token or not isinstance(token, str):
        return None, "Token de desuscripción no proporcionado."
        
    signer = TimestampSigner(salt=UNSUB_SALT)
    try:
        raw_payload = signer.unsign(token)
        parts = raw_payload.split(':')
        if len(parts) != 3 or parts[2] != 'unsub':
            return None, "Formato de token no válido."
            
        contact_id = int(parts[0])
        organization_id = int(parts[1])
        
        contact = Contact.objects.filter(
            id=contact_id, 
            organization_id=organization_id
        ).select_related('organization').first()
        
        if not contact:
            return None, "Contacto u organización no encontrados."
            
        return contact, None
    except (BadSignature, SignatureExpired, ValueError) as e:
        logger.warning(f"Intento de desuscripción con token inválido o manipulado: {e}")
        return None, "El enlace de desuscripción es inválido o ha sido alterado."

import os
import fcntl
from pathlib import Path
from django.conf import settings
from django.core.cache import cache

def check_and_increment_rate_limit(key, limit=5, timeout=3600):
    """
    Control de tasa concurrente y atómico seguro para entornos multi-proceso / multi-hilo
    utilizando FileBasedCache y fcntl.flock para evitar condiciones de carrera sin requerir Redis.
    Retorna (is_allowed: bool, current_count: int).
    """
    cache_dir = Path(settings.CACHES['default']['LOCATION'])
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe_key = "".join(c if c.isalnum() else "_" for c in key)
    lock_file_path = cache_dir / f"{safe_key}.lock"
    
    with open(lock_file_path, 'w') as lock_f:
        fcntl.flock(lock_f, fcntl.LOCK_EX)
        try:
            current = cache.get(key, 0)
            current += 1
            cache.set(key, current, timeout=timeout)
            return (current <= limit), current
        finally:
            try:
                fcntl.flock(lock_f, fcntl.LOCK_UN)
            except Exception:
                pass
