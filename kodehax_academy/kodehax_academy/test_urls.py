from django.http import HttpResponse
from django.urls import include, path


def _stub_view(request):
    return HttpResponse("ok")


urlpatterns = [
    path("logout/", _stub_view, name="logout"),
    path("student/dashboard/", _stub_view, name="student_dashboard"),
    path("student/skill-profile/", _stub_view, name="skill_assessment_profile"),
    path("student/daily-challenges/", include("daily_challenges.urls")),
    path("student/assignments/", _stub_view, name="view_assignments"),
    path("student/performance/", _stub_view, name="student_performance_dashboard"),
    path("student/chat/", _stub_view, name="chat_page"),
    path("student/profile/", _stub_view, name="student_profile"),
]
