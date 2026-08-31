from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('captar-lead/', views.capture_lead, name='capture_lead'),
    path('accounts/change-password/', views.change_password, name='change_password'),
    path('accounts/my-account/', views.my_account, name='my_account'),
]

