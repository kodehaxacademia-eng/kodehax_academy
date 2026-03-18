from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.student_dashboard, name="student_dashboard"),
    path("performance/", views.student_performance_dashboard, name="student_performance_dashboard"),
    path("join-classroom/", views.join_classroom, name="join_classroom"),
    path("classes/<int:class_id>/", views.class_detail, name="student_class_detail"),
    path("assignments/", views.view_assignments, name="view_assignments"),
    path("assignments/<int:assignment_id>/submit/", views.submit_assignment, name="submit_assignment"),
    path("assignments/<int:assignment_id>/quiz/", views.take_quiz_assignment, name="take_quiz_assignment"),
    path("assignments/<int:assignment_id>/code/", views.submit_code_assignment, name="submit_code_assignment"),
    path("profile/", views.student_profile, name="student_profile"),
    path("profile/edit/", views.edit_student_profile, name="edit_student_profile"),
    path('chat/', views.llama_chat, name='ai_chat'),
    path("api/chat/start/", views.chat_start_api, name="chat_start_api"),
    path("api/chat/sessions/", views.chat_sessions_api, name="chat_sessions_api"),
    path("api/chat/<int:session_id>/", views.chat_session_detail_api, name="chat_session_detail_api"),
    path("api/chat/<int:session_id>/message/", views.chat_session_message_api, name="chat_session_message_api"),
    path("api/chat/<int:session_id>/rename/", views.chat_session_rename_api, name="chat_session_rename_api"),
    path("api/chat/<int:session_id>/clear/", views.chat_session_clear_api, name="chat_session_clear_api"),
    path("chat/image-query/", views.image_query_api, name="student_image_query_api"),
    path('chat-page/', views.chat_page, name='chat_page'),  
]
