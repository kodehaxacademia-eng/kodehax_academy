from django.urls import path

from . import views


urlpatterns = [
    path("", views.assessment_entry, name="skill_assessment_entry"),
    path("step/<int:step>/", views.assessment_step, name="skill_assessment_step"),
    path("complete/", views.assessment_complete, name="skill_assessment_complete"),
    path("profile/", views.assessment_profile, name="skill_assessment_profile"),
]
