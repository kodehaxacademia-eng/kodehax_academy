from django.contrib import admin

from .models import (
    DailyChallenge,
    DailyChallengeSession,
    DailyChallengeQuestion,
    DailyChallengeSet,
    QuestionTemplate,
    StudentChallengeAttempt,
    StudentPoints,
)


@admin.register(DailyChallengeSet)
class DailyChallengeSetAdmin(admin.ModelAdmin):
    list_display = ("student", "date", "completed", "total_score", "solved_count", "created_at")
    list_filter = ("date", "completed")
    search_fields = ("student__username", "student__email")
    readonly_fields = ("created_at", "updated_at", "published_at")


@admin.register(DailyChallenge)
class DailyChallengeAdmin(admin.ModelAdmin):
    list_display = ("student", "title", "difficulty", "level", "status", "attempts", "score", "template")
    list_filter = ("date", "status", "difficulty", "level")
    search_fields = ("student__username", "title", "student__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(QuestionTemplate)
class QuestionTemplateAdmin(admin.ModelAdmin):
    list_display = ("title_template", "difficulty", "topic", "approval_status", "is_active", "created_by", "approved_by")
    list_filter = ("difficulty", "topic", "approval_status", "is_active")
    search_fields = ("title_template", "topic", "created_by__username")
    readonly_fields = ("created_at", "updated_at", "approved_at")


@admin.register(DailyChallengeQuestion)
class DailyChallengeQuestionAdmin(admin.ModelAdmin):
    list_display = ("generated_question", "template", "date_used", "parameter_signature")
    list_filter = ("date_used", "template__difficulty", "template__topic")
    search_fields = ("generated_question", "template__title_template", "parameter_signature")
    readonly_fields = ("created_at",)


@admin.register(StudentChallengeAttempt)
class StudentChallengeAttemptAdmin(admin.ModelAdmin):
    list_display = ("student", "challenge", "submitted_at", "solved", "final_score", "penalty_points", "hints_used")
    list_filter = ("solved", "submitted_at")
    search_fields = ("student__username", "challenge__title")
    readonly_fields = ("submitted_at",)


@admin.register(StudentPoints)
class StudentPointsAdmin(admin.ModelAdmin):
    list_display = ("student", "total_points", "daily_points", "points_spent", "points_remaining", "updated_at")
    search_fields = ("student__username", "student__email")
    readonly_fields = ("updated_at",)


@admin.register(DailyChallengeSession)
class DailyChallengeSessionAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "date",
        "questions_attempted",
        "questions_solved",
        "points_earned",
        "points_deducted",
        "session_score",
        "updated_at",
    )
    list_filter = ("date",)
    search_fields = ("student__username", "student__email")
    readonly_fields = ("created_at", "updated_at")
