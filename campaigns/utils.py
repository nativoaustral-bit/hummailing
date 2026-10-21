import os
import re
import uuid
import base64
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

def extract_and_save_base64_image(data_uri):
    """
    Si la URL es un data:image/...;base64,..., decodifica y guarda el archivo en MEDIA_ROOT/logos/
    retornando la URL limpia relativa '/media/logos/...'. Si no, retorna la URL original.
    """
    if not isinstance(data_uri, str) or not data_uri.startswith('data:image/'):
        return data_uri

    match = re.match(r'^data:image/([a-zA-Z0-9\+\-]+);base64,(.+)$', data_uri)
    if not match:
        return data_uri

    raw_ext = match.group(1).lower()
    b64_data = match.group(2)
    ext_map = {'jpeg': '.jpg', 'jpg': '.jpg', 'png': '.png', 'webp': '.webp', 'gif': '.gif'}
    ext = ext_map.get(raw_ext, '.png')

    try:
        file_bytes = base64.b64decode(b64_data)
        logos_dir = settings.MEDIA_ROOT / 'logos'
        os.makedirs(logos_dir, mode=0o755, exist_ok=True)
        try:
            os.chmod(settings.MEDIA_ROOT, 0o755)
            os.chmod(logos_dir, 0o755)
        except Exception:
            pass

        filename = f"img_{uuid.uuid4().hex[:12]}{ext}"
        file_path = logos_dir / filename
        with open(file_path, 'wb') as f:
            f.write(file_bytes)
        try:
            os.chmod(file_path, 0o644)
        except Exception:
            pass
        return f"{settings.MEDIA_URL}logos/{filename}"
    except Exception as e:
        logger.warning(f"No se pudo extraer imagen base64: {e}")
        return data_uri

def make_absolute_image_url(url, base_site_url=None):
    """
    Asegura que cualquier URL de imagen enviada por email sea una URL absoluta accesible (https://...).
    - Si es base64 data URI, la extrae a disco primero.
    - Si ya es URL absoluta, la preserva asegurando https:// si es del dominio propio.
    - Si es relativa (/media/... o media/...), le antepone base_site_url (ej: https://mailing.humm.cl).
    """
    if not url or not isinstance(url, str):
        return ""
    url = url.strip()
    if not url:
        return ""

    # 1. Si es base64, extraer y guardar en disco
    if url.startswith('data:image/'):
        url = extract_and_save_base64_image(url)

    # 2. Si ya es una URL completa
    if url.startswith(('http://', 'https://')):
        if url.startswith('http://mailing.humm.cl'):
            url = 'https://' + url[7:]
        return url

    # 3. Si es una ruta relativa
    base = (base_site_url or getattr(settings, 'SITE_URL', 'https://mailing.humm.cl')).rstrip('/')
    if not url.startswith('/'):
        url = '/' + url
    return f"{base}{url}"
