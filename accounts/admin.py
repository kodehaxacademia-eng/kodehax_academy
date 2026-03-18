from django.contrib import admin

from .models import TeacherInvitation


@admin.register(TeacherInvitation)
class TeacherInvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "created_at", "is_used")
    search_fields = ("email",)
    list_filter = ("is_used", "created_at")
