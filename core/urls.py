from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('accounts/change-password/', views.change_password, name='change_password'),
    path('accounts/my-account/', views.my_account, name='my_account'),
]
