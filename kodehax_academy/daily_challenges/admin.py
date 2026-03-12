from django.contrib import admin

from .models import DailyChallenge, DailyChallengeSet, StudentChallengeAttempt, StudentPoints


@admin.register(DailyChallengeSet)
class DailyChallengeSetAdmin(admin.ModelAdmin):
    list_display = ("student", "date", "completed", "total_score", "solved_count", "created_at")
    list_filter = ("date", "completed")
    search_fields = ("student__username", "student__email")
    readonly_fields = ("created_at", "updated_at", "published_at")


@admin.register(DailyChallenge)
class DailyChallengeAdmin(admin.ModelAdmin):
    list_display = ("student", "title", "difficulty", "level", "status", "attempts", "score")
    list_filter = ("date", "status", "difficulty", "level")
    search_fields = ("student__username", "title", "student__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(StudentChallengeAttempt)
class StudentChallengeAttemptAdmin(admin.ModelAdmin):
    list_display = ("student", "challenge", "submitted_at", "solved", "final_score", "penalty_points", "hints_used")
    list_filter = ("solved", "submitted_at")
    search_fields = ("student__username", "challenge__title")
    readonly_fields = ("submitted_at",)


@admin.register(StudentPoints)
class StudentPointsAdmin(admin.ModelAdmin):
    list_display = ("student", "total_points", "points_spent", "points_remaining", "updated_at")
    search_fields = ("student__username", "student__email")
    readonly_fields = ("updated_at",)
