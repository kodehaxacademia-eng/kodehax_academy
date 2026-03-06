from django.urls import path
from . import views

app_name = 'teacher'

urlpatterns = [
    # /teacher/dashboard/
    path('dashboard/', views.teacher_dashboard, name="teacher_dashboard"),
]