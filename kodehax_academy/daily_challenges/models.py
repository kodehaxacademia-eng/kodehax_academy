from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class DailyChallengeSet(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_challenge_sets",
    )
    date = models.DateField()
    completed = models.BooleanField(default=False)
    total_score = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-date", "-created_at")
        unique_together = ("student", "date")

    @property
    def expires_at(self):
        return self.created_at + timedelta(hours=24)

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f"{self.student.username} - {self.date}"


class DailyChallenge(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SOLVED = "solved"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_SOLVED, "Solved"),
        (STATUS_FAILED, "Failed"),
    )

    challenge_set = models.ForeignKey(
        DailyChallengeSet,
        on_delete=models.CASCADE,
        related_name="challenges",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_challenges",
    )
    problem = models.ForeignKey(
        "skill_assessment.CodingProblem",
        on_delete=models.CASCADE,
        related_name="daily_challenge_items",
    )
    date = models.DateField()
    attempts = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    score = models.PositiveIntegerField(default=0)
    latest_code = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("id",)
        unique_together = ("student", "problem", "date")

    def __str__(self):
        return f"{self.student.username} - {self.problem.title} ({self.date})"
