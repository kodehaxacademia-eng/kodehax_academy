from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "role", "is_active", "is_email_verified")
    list_filter = ("role", "is_active", "is_email_verified")
    search_fields = ("username", "email")
