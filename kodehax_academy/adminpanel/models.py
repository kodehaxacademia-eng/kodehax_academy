from django.conf import settings
from django.db import models


class AdminUserState(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    TEACHER_APPROVAL_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="adminpanel_state",
    )
    teacher_approval_status = models.CharField(
        max_length=20,
        choices=TEACHER_APPROVAL_CHOICES,
        default=STATUS_PENDING,
    )
    suspension_reason = models.CharField(max_length=255, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Admin User State"
        verbose_name_plural = "Admin User States"
        indexes = [
            models.Index(fields=["teacher_approval_status"]),
            models.Index(fields=["suspended_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} ({self.teacher_approval_status})"

