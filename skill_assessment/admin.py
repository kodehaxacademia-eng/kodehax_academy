from django.contrib import admin

from .models import AssessmentQuestion, CodingProblem, StudentAssessment, StudentSkill
from .services import reset_student_assessment


@admin.action(description="Reset selected student assessments")
def reset_assessments(modeladmin, request, queryset):
    for assessment in queryset.select_related("student"):
        reset_student_assessment(assessment.student)


@admin.action(description="Reset selected skill profiles")
def reset_skill_profiles(modeladmin, request, queryset):
    for profile in queryset.select_related("student"):
        reset_student_assessment(profile.student)


@admin.register(StudentSkill)
class StudentSkillAdmin(admin.ModelAdmin):
    list_display = ("student", "skill_level", "skill_score", "updated_at")
    list_filter = ("skill_level", "updated_at")
    search_fields = ("student__username", "student__email")
    readonly_fields = ("created_at", "updated_at")
    actions = (reset_skill_profiles,)


@admin.register(StudentAssessment)
class StudentAssessmentAdmin(admin.ModelAdmin):
    list_display = ("student", "score", "completed", "current_step", "date_completed")
    list_filter = ("completed", "current_step", "date_completed")
    search_fields = ("student__username", "student__email")
    readonly_fields = ("created_at", "updated_at", "date_completed")
    actions = (reset_assessments,)


@admin.register(AssessmentQuestion)
class AssessmentQuestionAdmin(admin.ModelAdmin):
    list_display = ("question_text", "topic", "difficulty", "order", "is_active")
    list_filter = ("topic", "difficulty", "is_active")
    search_fields = ("question_text", "topic")
    list_editable = ("order", "is_active")


@admin.register(CodingProblem)
class CodingProblemAdmin(admin.ModelAdmin):
    list_display = ("title", "topic", "function_name", "difficulty", "order", "is_active")
    list_filter = ("topic", "difficulty", "is_active")
    search_fields = ("title", "topic", "description", "function_name")
    list_editable = ("order", "is_active")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "topic",
                    "description",
                    "starter_code",
                    "function_name",
                    "test_cases",
                    "difficulty",
                    "order",
                    "is_active",
                )
            },
        ),
        ("Daily Challenge Hints", {"fields": ("hint1", "hint2")}),
    )
