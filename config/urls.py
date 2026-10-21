"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render
from django.http import JsonResponse

def custom_500_view(request):
    import sys, traceback
    exc_type, exc_value, exc_tb = sys.exc_info()
    error_msg = str(exc_value) if exc_value else "Error interno no especificado"
    
    is_ajax = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest' or 
        'application/json' in request.headers.get('accept', '') or
        request.path.startswith('/campaigns/')
    )
    if is_ajax:
        return JsonResponse({
            'status': 'error',
            'message': f"Error interno en servidor: {error_msg}"
        }, status=200)
    return render(request, '500.html', status=500)

def server_status_view(request):
    key = request.GET.get('key')
    if key != 'humm_debug_2026' or not (request.user.is_authenticated and (request.user.is_superuser or getattr(request.user, 'is_humm_master_admin', False))):
        return JsonResponse({'status': 'denied'}, status=403)
    
    import sys, os
    
    logs = {}
    candidates = [
        ('hummailing_data_hummailing', '/home1/paulocis/private/hummailing_data/logs/hummailing.log'),
        ('hummailing_data_crash', '/home1/paulocis/private/hummailing_data/logs/crash.log'),
        ('mailing_hummailing', str(settings.BASE_DIR / 'logs' / 'hummailing.log')),
        ('mailing_crash', str(settings.BASE_DIR / 'logs' / 'crash.log')),
    ]
    for label, path in candidates:
        if os.path.exists(path):
            try:
                with open(path, 'r', errors='ignore') as f:
                    lines = f.readlines()
                    logs[label] = [l.strip() for l in lines[-60:]] if lines else ['(empty file)']
            except Exception as e:
                logs[label] = [f"Error reading: {e}"]
        else:
            logs[label] = ['(file not found)']
            
    db_path = str(settings.DATABASES['default']['NAME'])
    db_stat = {
        'path': db_path,
        'exists': os.path.exists(db_path),
        'writable': os.access(db_path, os.W_OK) if os.path.exists(db_path) else False,
        'parent_writable': os.access(os.path.dirname(db_path), os.W_OK) if os.path.dirname(db_path) else False,
    }
    
    return JsonResponse({
        'status': 'ok',
        'python_version': sys.version,
        'db_stat': db_stat,
        'logs': logs
    })

handler500 = 'config.urls.custom_500_view'

urlpatterns = [
    path('api/server-status/', server_status_view, name='server_status'),
    path('admin/', admin.site.urls),
    path('', include('organizations.urls')),
    path('', include('opportunities.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('contacts/', include('contacts.urls')),
    path('campaigns/', include('campaigns.urls')),
    path('', include('core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
