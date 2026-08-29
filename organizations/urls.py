from django.urls import path
from . import views

app_name = 'organizations'

urlpatterns = [
    path('humm-admin/', views.admin_dashboard, name='admin_dashboard'),
    
    # Organizaciones / Clientes
    path('humm-admin/organizations/', views.organization_list, name='organization_list'),
    path('humm-admin/organizations/create/', views.organization_create, name='organization_create'),
    path('humm-admin/organizations/<int:org_id>/edit/', views.organization_edit, name='organization_edit'),
    path('humm-admin/organizations/<int:org_id>/toggle-status/', views.organization_toggle_status, name='organization_toggle_status'),
    path('humm-admin/organizations/<int:org_id>/delete/', views.organization_delete, name='organization_delete'),
    path('humm-admin/organizations/<int:org_id>/impersonate/', views.impersonate_organization, name='impersonate_organization'),
    path('humm-admin/organizations/exit-support/', views.exit_support_mode, name='exit_support_mode'),
    
    # Usuarios
    path('humm-admin/users/', views.user_list, name='user_list'),
    path('humm-admin/users/create/', views.user_create, name='user_create'),
    path('humm-admin/users/<int:user_id>/reset-password/', views.user_reset_password, name='user_reset_password'),
    path('humm-admin/users/<int:user_id>/toggle-active/', views.user_toggle_active, name='user_toggle_active'),
    path('humm-admin/users/<int:user_id>/delete/', views.user_delete, name='user_delete'),
    
    # Comunicados Masivos a Clientes
    path('humm-admin/broadcast/', views.broadcast_list, name='broadcast_list'),
    path('humm-admin/broadcast/new/', views.broadcast_announcement, name='broadcast_announcement'),
    
    # Auditoría
    path('humm-admin/activity/', views.activity_log_list, name='activity_logs'),
]
