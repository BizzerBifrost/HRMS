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
    path('staff/home/', views.staffmenu, name='staffmenu'),
    path('staff/leave/application/', views.staff_leave_application, name='staff_leave_application'),
    path('staff/leave/status/', views.staff_leave_status, name='staff_leave_status'),
    path('staff/view-goals/', views.staff_view_goals, name='staff_view_goals'),
    path('staff/policies/', views.staff_policies, name='staff_policies'),

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
    path('hr/feedback/', views.hr_feedback, name='hr_feedback'),
    path('hr/update-feedback-status/', views.update_feedback_status, name='update_feedback_status'),
    path('hr/recruitment/', views.recruitment_list, name='hr_recruitment'),
    path('hr/recruitment/search/', views.recruitment_search, name='hr_recruitment_search'),
    path('hr/recruitment/details/<int:request_id>/', views.recruitment_details, name='hr_recruitment_details'),
    path('hr/recruitment/process/<int:request_id>/', views.recruitment_process, name='hr_recruitment_process'),
    path('hr/recruitment/notes/<int:request_id>/', views.recruitment_notes, name='hr_recruitment_notes'),
    path('hr/recruitment/attachments/<int:request_id>/', views.recruitment_attachments, name='hr_recruitment_attachments'),
    path('hr/recruitment/attachment/download/<int:attachment_id>/', views.download_attachment, name='download_attachment'),

    path('hr/recruitment/history/<int:request_id>/', views.recruitment_status_history, name='hr_recruitment_history'),
    path('hr/recruitment/analytics/', views.recruitment_analytics, name='recruitment_analytics'),
    path('hr/recruitment/export/', views.export_recruitment_report, name='export_recruitment_report'),
    path('hr/recruitment/schedule/', views.schedule_recruitment_report, name='schedule_recruitment_report'),
    path('hr/recruitment/schedule/cancel/<str:schedule_id>/', views.cancel_scheduled_report, name='cancel_scheduled_report'),

    # manager
    path('manager/home/', views.managermenu, name='managermenu'),
    path('manager/leave-approvals/', views.leave_approvals, name='leave_approvals'),
    path('manager/process-leave-request/', views.process_leave_request, name='process_leave_request'),
    path('manager/team-management/', views.team_management, name='team_management'),
    path('manager/team-goals/', views.team_goals, name='team_goals'),
    path('manager/recruitment-request/', views.recruitment_request, name='recruitment_request'),

    # admin
    path('administrator/home/', views.adminmenu, name = 'adminmenu'),
    path('administrator/profile/', views.admin_profile, name='admin_profile'),
    path('administrator/user-management/', views.user_management, name='user_management'),
    path('administrator/add-user/', views.add_user, name='add_user'),
    path('administrator/delete-user/', views.delete_user, name='delete_user'),
]