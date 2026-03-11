from django.urls import path

from . import views


urlpatterns = [
    path("", views.admin_entry, name="adminpanel_home"),
    path("dashboard/", views.dashboard, name="adminpanel_dashboard"),
    path("users/", views.users, name="adminpanel_users"),
    path("users/<int:user_id>/action/", views.user_action, name="adminpanel_user_action"),
    path("users/<int:user_id>/edit/", views.user_edit, name="adminpanel_user_edit"),
    path("teachers/", views.teachers, name="adminpanel_teachers"),
    path("teachers/invite/", views.invite_teacher, name="adminpanel_invite_teacher"),
    path(
        "teachers/invitations/<int:invitation_id>/resend/",
        views.resend_teacher_invite,
        name="adminpanel_resend_teacher_invite",
    ),
    path(
        "teachers/<int:teacher_id>/action/",
        views.teacher_action,
        name="adminpanel_teacher_action",
    ),
    path("students/", views.students, name="adminpanel_students"),
    path(
        "students/<int:student_id>/action/",
        views.student_action,
        name="adminpanel_student_action",
    ),
    path("assignments/", views.assignments, name="adminpanel_assignments"),
    path(
        "assignments/<int:assignment_id>/action/",
        views.assignment_action,
        name="adminpanel_assignment_action",
    ),
    path("analytics/", views.analytics, name="adminpanel_analytics"),
]
