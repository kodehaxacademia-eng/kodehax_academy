from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/",views.teacher_dashboard,name="teacher_dashboard"),
    path("class/create/",views.create_class,name="create_class"),
    path("classes/<int:id>/",views.class_detail,name="class_detail"),
    path("classes/<int:class_id>/assignments/new/", views.assignment_type_selector, name="assignment_type_selector"),
    path( "classes/<int:class_id>/assignments/create/",views.create_assignment,name="create_assignment"),
    path("classes/<int:class_id>/assignments/create/file/", views.create_file_assignment, name="create_file_assignment"),
    path("classes/<int:class_id>/assignments/create/quiz/", views.create_quiz_assignment, name="create_quiz_assignment"),
    path("classes/<int:class_id>/assignments/create/code/", views.create_code_assignment, name="create_code_assignment"),
    path("classes/<int:class_id>/assignments/",views.assignment_list,name="assignment_list"),
    path("assignments/<int:id>/",views.assignment_detail,name="assignment_detail"),
    path("submissions/file/<int:submission_id>/grade/", views.grade_file_submission, name="grade_file_submission"),
    path("submissions/code/<int:submission_id>/grade/", views.grade_code_submission, name="grade_code_submission"),
    path("assignments/<int:assignment_id>/quiz/auto-grade/", views.auto_grade_quiz, name="auto_grade_quiz"),
    path("classes/<int:class_id>/assignments/manage/",views.assignments_page,name="assignments_page"),
    path("classes/<int:class_id>/performance/",views.performance_list,name="performance_list"),
    path("classes/<int:class_id>/performance/<int:student_id>/",views.student_performance,name="student_performance"),
    path("profile/",views.teacher_profile, name="teacher_profile"),
    path("profile/edit/",views.teacher_edit_profile, name="teacher_edit_profile"),
    path("ai-tools/",views.ai_tools,name="ai_tools"),
]
