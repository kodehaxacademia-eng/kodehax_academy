from django.contrib import admin

from .models import DailyChallenge, DailyChallengeSet


@admin.register(DailyChallengeSet)
class DailyChallengeSetAdmin(admin.ModelAdmin):
    list_display = ("student", "date", "completed", "total_score", "created_at")
    list_filter = ("date", "completed")
    search_fields = ("student__username", "student__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(DailyChallenge)
class DailyChallengeAdmin(admin.ModelAdmin):
    list_display = ("student", "problem", "date", "status", "attempts", "score")
    list_filter = ("date", "status", "problem__difficulty")
    search_fields = ("student__username", "problem__title", "student__email")
    readonly_fields = ("created_at", "updated_at")
