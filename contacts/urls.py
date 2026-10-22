from django.urls import path
from . import views

app_name = 'contacts'

urlpatterns = [
    path('', views.contact_list, name='list'),
    path('import/', views.import_contacts, name='import'),
    path('create/', views.contact_create, name='create'),
    path('<int:contact_id>/edit/', views.contact_update, name='edit'),
    path('<int:contact_id>/delete/', views.contact_delete, name='delete'),
    
    # Gestión de Etiquetas
    path('tags/', views.tag_list, name='tag_list'),
    path('tags/create/', views.tag_create, name='tag_create'),
    path('tags/<int:tag_id>/edit/', views.tag_update, name='tag_update'),
    path('tags/<int:tag_id>/delete/', views.tag_delete, name='tag_delete'),
]

