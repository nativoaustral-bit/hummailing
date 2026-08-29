import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_datetime
from .models import Campaign, TrackingEvent, Contact

logger = logging.getLogger(__name__)

@csrf_exempt
def resend_webhook(request):
    if request.method == 'POST':
        try:
            payload = json.loads(request.body)
            event_type = payload.get('type')
            data = payload.get('data', {})
            
            email = data.get('to', [''])[0] if isinstance(data.get('to'), list) else data.get('to')
            
            # Map Resend events to our EVENT_TYPES
            event_map = {
                'email.sent': 'sent',
                'email.delivered': 'delivered',
                'email.bounced': 'bounce_temp', # Or bounce_perm depending on bounce subtype
                'email.complained': 'spam',
                'email.opened': 'open',
                'email.clicked': 'click',
            }
            
            internal_event_type = event_map.get(event_type)
            if not internal_event_type:
                return JsonResponse({'status': 'ignored', 'reason': 'unhandled_event'})

            # A more robust implementation would use tags or custom headers in Resend
            # to pass the Campaign ID back in the webhook.
            # Assuming we can find the most recent campaign sent to this user for now as a fallback,
            # or if 'tags' were sent via Resend API (resend allows passing tags in params).
            
            # For this MVP, let's just log it if we can't find a direct link, 
            # or you can pass `tags=[{"name": "campaign_id", "value": str(campaign.id)}]` in `send_campaign_task`
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'method_not_allowed'}, status=405)
