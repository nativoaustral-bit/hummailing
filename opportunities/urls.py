from django.urls import path
from . import views

app_name = 'opportunities'

urlpatterns = [
    path('opportunities/', views.opportunity_list, name='list'),
    path('opportunities/bulk-delete/', views.opportunity_bulk_delete, name='bulk_delete'),
    path('opportunities/<int:opp_id>/', views.opportunity_detail, name='detail'),
    path('opportunities/<int:opp_id>/delete/', views.opportunity_delete, name='delete'),
    
    # Enlaces de seguimiento y desuscripción
    path('t/<str:token>/', views.redirect_tracked_link, name='track_click'),
    path('unsubscribe/<str:token>/', views.unsubscribe_contact, name='unsubscribe'),
]
