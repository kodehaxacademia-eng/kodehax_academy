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


class PlatformSettings(models.Model):
    # Platform Settings
    platform_name = models.CharField(max_length=255, default="Kodehax Academy")
    support_email = models.EmailField(default="support@kodehax.com")
    maintenance_mode = models.BooleanField(default=False)

    # Authentication Settings
    require_email_verification = models.BooleanField(default=True)
    enable_otp_login = models.BooleanField(default=True)
    max_login_attempts = models.IntegerField(default=5)

    # Challenge Configuration
    challenge_time_limit_minutes = models.IntegerField(default=30)
    auto_generate_challenges = models.BooleanField(default=True)

    # Scoring System
    daily_challenge_base_points = models.IntegerField(default=10)
    hint_cost_penalty = models.IntegerField(default=2)

    class Meta:
        verbose_name = "Platform Settings"
        verbose_name_plural = "Platform Settings"

    def __str__(self):
        return "Platform Settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
