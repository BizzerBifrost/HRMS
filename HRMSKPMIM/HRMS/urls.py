from django.urls import path
from . import views

urlpatterns = [
    # home
    path('', views.index, name='index'),
    path('login/', views.login, name='login'),
    path('login/process/', views.login_process, name='login_process'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    # staff

    # hr

    # manager
]