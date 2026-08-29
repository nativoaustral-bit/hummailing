from django.urls import path
from . import views
from . import webhooks

app_name = 'campaigns'

urlpatterns = [
    path('', views.campaign_list, name='list'),
    path('create/', views.campaign_create, name='create'),
    path('<int:campaign_id>/editor/', views.campaign_editor, name='editor'),
    path('<int:campaign_id>/preview/', views.campaign_preview, name='preview'),
    path('<int:campaign_id>/send/', views.campaign_send, name='send'),
    path('<int:campaign_id>/duplicate/', views.campaign_duplicate, name='duplicate'),
    path('<int:campaign_id>/delete/', views.campaign_delete, name='delete'),
    path('upload-image/', views.upload_image, name='upload_image'),
    path('webhooks/resend/', webhooks.resend_webhook, name='resend_webhook'),
]
