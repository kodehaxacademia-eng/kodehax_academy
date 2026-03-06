from django.urls import path
from . import views


urlpatterns = [

    path("", views.home, name="home"),
    # Student routes
    path("student/register/", views.student_register, name="student_register"),
    path("student/login/", views.student_login, name="student_login"),

    # Teacher routes
    path("teacher/register/", views.teacher_register, name="teacher_register"),
    path("teacher/login/", views.teacher_login, name="teacher_login"),

]