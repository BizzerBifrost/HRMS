from django.urls import path
from . import views

urlpatterns = [
    # home
    path('', views.index, name='index'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('login/process/', views.login_process, name='login_process'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/<str:token>/', views.reset_password, name='reset_password'),
    # staff

    # hr
    path('hr/home/', views.hrmenu, name='hrmenu'),
    path('hr/profile/', views.hr_profile, name='hr_profile'),
    path('hr/employee-management/', views.employee_management, name='employee_management'),
    path('hr/add-employee/', views.add_employee, name='add_employee'),
    path('hr/delete-employee/', views.delete_employee, name='delete_employee'),

    # manager

    # admin
    path('administrator/home/', views.adminmenu, name = 'adminmenu'),
    path('administrator/profile/', views.admin_profile, name='admin_profile'),
    path('administrator/user-management/', views.user_management, name='user_management'),
    path('administrator/add-user/', views.add_user, name='add_user'),
    path('administrator/delete-user/', views.delete_user, name='delete_user'),
]