from django.db import models
from django.conf import settings
from django.utils import timezone


class StudentProfile(models.Model):

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    profile_picture = models.ImageField(upload_to="student_profiles/", blank=True, null=True)

    phone_number = models.CharField(max_length=15, blank=True)

    address = models.TextField(blank=True)

    course = models.CharField(max_length=100, blank=True)
    batch = models.CharField(max_length=100, blank=True)
    student_id = models.CharField(max_length=50, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True)

    parent_name = models.CharField(max_length=100, blank=True)

    parent_phone = models.CharField(max_length=15, blank=True)
    parent_email = models.EmailField(blank=True)
    guardian_relation = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.user.username


class ImageQuery(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="image_queries",
    )
    image = models.ImageField(upload_to="student_ai_queries/%Y/%m/%d/")
    extracted_text = models.TextField(blank=True)
    ai_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user.username} image query @ {self.created_at:%Y-%m-%d %H:%M}"


class ChatSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
    )
    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ("-updated_at",)
        indexes = [
            models.Index(fields=["user", "is_active", "updated_at"]),
            models.Index(fields=["user", "expires_at"]),
        ]

    def __str__(self):
        return self.title or f"Chat {self.pk}"

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())


class ChatMessage(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_CHOICES = (
        (ROLE_USER, "User"),
        (ROLE_ASSISTANT, "Assistant"),
    )

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        indexes = [
            models.Index(fields=["session", "created_at"]),
        ]

    def __str__(self):
        return f"{self.session_id} {self.role} @ {self.created_at:%Y-%m-%d %H:%M}"
