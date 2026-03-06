from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.student_dashboard, name="student_dashboard"),
    path("assignments/", views.student_assignments, name="student_assignments"),
    path("assignments/view_assignment/", views.student_view_assignment, name="view_assignment"),
    path("assignments/submit_assignment/", views.student_submit_assignment, name="submit_assignment"),
    path("profile/", views.student_profile, name="student_profile"),
    path("profile/edit/", views.edit_student_profile, name="edit_student_profile"),
    path('chat/', views.llama_chat, name='ai_chat'),
    path('chat-page/', views.chat_page, name='chat_page'),  
    
]