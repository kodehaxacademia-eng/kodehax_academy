from django.contrib import admin
from .models import ChatMessage, ChatSession, ImageQuery, StudentProfile


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "batch", "student_id")
    search_fields = ("user__username", "user__email", "student_id", "course", "batch")


@admin.register(ImageQuery)
class ImageQueryAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "image")
    search_fields = ("user__username", "user__email", "extracted_text")
    readonly_fields = ("created_at",)


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "updated_at", "is_active", "expires_at")
    list_filter = ("is_active",)
    search_fields = ("user__username", "user__email", "title")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("session", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("session__title", "content", "session__user__username")
