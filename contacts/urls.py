from django.urls import path
from . import views

app_name = 'contacts'

urlpatterns = [
    path('', views.contact_list, name='list'),
    path('import/', views.import_contacts, name='import'),
    path('create/', views.contact_create, name='create'),
    path('<int:contact_id>/edit/', views.contact_update, name='edit'),
    path('<int:contact_id>/delete/', views.contact_delete, name='delete'),
]
