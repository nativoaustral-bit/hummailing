import logging
import resend
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

class ResendEmailBackend(BaseEmailBackend):
    """
    Backend personalizado para Django que envía correos vía Resend API (HTTP REST)
    en lugar de SMTP tradicional. Esto garantiza compatibilidad total en desarrollo local
    y en servidores como Hostgator donde los puertos SMTP salientes suelen estar bloqueados.
    """
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = getattr(settings, 'RESEND_API_KEY', None)

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
            
        if not self.api_key or self.api_key == 're_your_resend_api_key_here':
            logger.warning("Resend API Key no configurada o inválida. No se pudo enviar el correo.")
            return 0
            
        resend.api_key = self.api_key
        sent_count = 0
        
        for message in email_messages:
            try:
                html_body = None
                text_body = message.body
                
                # Extraer cuerpo HTML si existe
                if hasattr(message, 'alternatives'):
                    for content, mimetype in message.alternatives:
                        if mimetype == 'text/html':
                            html_body = content
                            break
                
                # Si el cuerpo principal es HTML o contiene etiquetas básicas
                if not html_body and ('<html>' in text_body.lower() or '<div' in text_body.lower() or '<p' in text_body.lower()):
                    html_body = text_body
                
                from_email = message.from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'Hummailing <hola@humm.cl>')
                
                # Asegurar formato remitente válido
                if not from_email or '@' not in from_email:
                    from_email = 'Hummailing <hola@humm.cl>'
                
                clean_subject = " ".join((message.subject or "").splitlines()).strip()
                if not clean_subject:
                    clean_subject = "Notificación de Hummailing"

                params = {
                    "from": from_email,
                    "to": list(message.to),
                    "subject": clean_subject,
                }
                
                if html_body:
                    params["html"] = html_body
                if text_body:
                    params["text"] = text_body
                    
                if message.reply_to:
                    params["reply_to"] = message.reply_to[0] if isinstance(message.reply_to, (list, tuple)) else str(message.reply_to)
                if message.cc:
                    params["cc"] = list(message.cc)
                if message.bcc:
                    params["bcc"] = list(message.bcc)
                    
                response = resend.Emails.send(params)
                logger.info(f"Correo enviado exitosamente vía Resend API: {response}")
                sent_count += 1
            except Exception as e:
                logger.error(f"Error al enviar correo vía Resend API a {message.to}: {e}")
                if not self.fail_silently:
                    raise e
                    
        return sent_count
