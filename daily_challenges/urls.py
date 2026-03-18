from django.urls import path

from . import views


urlpatterns = [
    path("", views.today_challenges, name="daily_challenges_today"),
    path("<int:challenge_id>/", views.submit_solution, name="daily_challenge_workspace"),
]
