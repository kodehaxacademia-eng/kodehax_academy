import secrets

from django.conf import settings
from django.db import models


class TeacherInvitation(models.Model):
    email = models.EmailField(unique=True)
    token = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teacher_invitations",
    )
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.email

    def refresh_token(self):
        self.token = secrets.token_urlsafe(32)

    def save(self, *args, **kwargs):
        if not self.token:
            self.refresh_token()
        self.email = self.email.lower().strip()
        super().save(*args, **kwargs)
