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
    path('update-staff/<str:staff_id>/', views.update_staff, name='update_staff'),
    path('hr/payroll/', views.payroll, name='payroll'),
    path('hr/payroll/set/<str:staff_id>/', views.set_payroll, name='set_payroll'),
    path('hr/payroll/view/<str:staff_id>/', views.view_payroll, name='view_payroll'),
    path('hr/payroll/edit/<str:staff_id>/', views.edit_payroll, name='edit_payroll'),
    path('hr/policies/', views.hr_policies, name='hr_policies'),
    path('hr/recruitment/', views.recruitment_list, name='hr_recruitment'),
    path('hr/recruitment/details/<int:request_id>/', views.recruitment_details, name='hr_recruitment_details'),
    path('hr/recruitment/process/<int:request_id>/', views.recruitment_process, name='hr_recruitment_process'),
    path('hr/recruitment/search/', views.recruitment_search, name='hr_recruitment_search'),

    # manager

    # admin
    path('administrator/home/', views.adminmenu, name = 'adminmenu'),
    path('administrator/profile/', views.admin_profile, name='admin_profile'),
    path('administrator/user-management/', views.user_management, name='user_management'),
    path('administrator/add-user/', views.add_user, name='add_user'),
    path('administrator/delete-user/', views.delete_user, name='delete_user'),
]