from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from .models import Organization

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.organization = None
        request.is_impersonating = False

        if request.user.is_authenticated:
            # 1. Determinar organización activa
            if getattr(request.user, 'is_humm_master_admin', False):
                impersonate_id = request.session.get('impersonate_org_id')
                if impersonate_id:
                    try:
                        request.organization = Organization.objects.get(id=impersonate_id)
                        request.is_impersonating = True
                    except Organization.DoesNotExist:
                        request.session.pop('impersonate_org_id', None)
                        request.organization = request.user.organization
                else:
                    request.organization = request.user.organization
            else:
                request.organization = request.user.organization

            # 2. Interceptar cambio obligatorio de contraseña
            if getattr(request.user, 'must_change_password', False):
                allowed_paths = [
                    reverse('change_password') if 'change_password' in [p.name for p in []] else '/accounts/change-password/',
                    '/accounts/logout/',
                    '/logout/',
                    '/static/',
                ]
                if not any(request.path.startswith(p) for p in ['/accounts/change-password/', '/accounts/logout/', '/logout/', '/static/']):
                    messages.warning(request, "Por seguridad, debes cambiar tu contraseña temporal antes de continuar.")
                    return redirect('change_password')

        response = self.get_response(request)
        return response
