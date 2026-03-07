from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/",views.teacher_dashboard,name="teacher_dashboard"),
    path("class/create/",views.create_class,name="create_class"),
    path("classes/<int:id>/",views.class_detail,name="class_detail"),
    path( "classes/<int:class_id>/assignments/create/",views.create_assignment,name="create_assignment"),
    path("classes/<int:class_id>/assignments/",views.assignment_list,name="assignment_list"),
    path("assignments/<int:id>/",views.assignment_detail,name="assignment_detail"),
    path("classes/<int:class_id>/assignments/",views.assignments_page,name="assignments_page"),
    path("classes/<int:class_id>/performance/",views.performance_list,name="performance_list"),
    path("classes/<int:class_id>/performance/<int:student_id>/",views.student_performance,name="student_performance"),
    path("profile/",views.teacher_profile, name="teacher_profile"),
    path("ai-tools/",views.ai_tools,name="ai_tools"),
]