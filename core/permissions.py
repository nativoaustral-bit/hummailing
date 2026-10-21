from functools import wraps
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)

def role_required(allowed_roles):
    """
    Decorador para restringir el acceso a vistas según el rol del usuario autenticado.
    El Administrador Master Humm (humm_admin o superuser) siempre tiene acceso.
    Si el rol no está permitido, deniega con HTTP 403.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', '')
                if is_ajax:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Tu sesión ha expirado o no estás autenticado. Por favor inicia sesión en otra pestaña y vuelve a guardar.'
                    }, status=200)
                return redirect('login')
                
            # Humm Admin / Superuser tiene permiso global
            if getattr(request.user, 'is_humm_master_admin', False):
                return view_func(request, *args, **kwargs)
                
            user_role = getattr(request.user, 'role', 'viewer')
            if user_role not in allowed_roles:
                logger.warning(
                    f"Acceso denegado: Usuario {request.user.username} (rol={user_role}) "
                    f"intentó acceder a {view_func.__name__} que requiere {allowed_roles}."
                )
                
                is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', '')
                if is_ajax or request.path.endswith('/upload-image/'):
                    return JsonResponse({
                        'status': 'error',
                        'message': 'No tienes permisos suficientes para realizar esta acción.'
                    }, status=403)
                    
                messages.error(request, "No tienes permisos suficientes para realizar esta acción.")
                return HttpResponseForbidden("<h1>403 Prohibido</h1><p>No tienes permisos suficientes para realizar esta acción.</p>")
                
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def block_viewer_mutations(view_func):
    """
    Bloquea explícitamente cualquier método mutante (POST, PUT, PATCH, DELETE)
    si el usuario tiene el rol 'viewer' (Visualizador / Analista - Solo Lectura).
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and not getattr(request.user, 'is_humm_master_admin', False):
            if request.user.role == 'viewer' and request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                logger.warning(
                    f"Operación mutante bloqueada para rol 'viewer': {request.user.username} -> {request.path} [{request.method}]"
                )
                is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', '')
                if is_ajax:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Tu rol es de solo lectura (Visualizador). No puedes modificar información.'
                    }, status=403)
                    
                messages.error(request, "Tu cuenta tiene rol de solo lectura (Visualizador). No puedes modificar datos.")
                return HttpResponseForbidden("<h1>403 Prohibido</h1><p>Tu rol de solo lectura no te permite modificar información.</p>")
                
        return view_func(request, *args, **kwargs)
    return _wrapped_view
