from django.urls import path

from . import views


urlpatterns = [
    path("register/", views.register, name="register"),
    path("student/register/", views.register, name="student_register"),
    path("teacher/register/", views.teacher_register_disabled, name="teacher_register"),
    path("student/login/", views.student_login, name="student_login"),
    path("teacher/login/", views.teacher_login, name="teacher_login"),
    path("verify-email/<uid>/<token>/", views.verify_email, name="verify_email"),
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("reset-password/<uid>/<token>/", views.reset_password, name="reset_password"),
    path("teacher-invite/<uid>/<token>/", views.teacher_invite_register, name="teacher_invite_register"),
]
