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
    published_at = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    total_score = models.PositiveIntegerField(default=0)
    solved_count = models.PositiveSmallIntegerField(default=0)
    easy_solved_count = models.PositiveSmallIntegerField(default=0)
    medium_solved_count = models.PositiveSmallIntegerField(default=0)
    hard_solved_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-date", "-created_at")
        unique_together = ("student", "date")

    @property
    def expires_at(self):
        base = self.published_at or self.created_at
        return base + timedelta(hours=24)

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f"{self.student.username} - {self.date}"


class DailyChallenge(models.Model):
    DIFFICULTY_EASY = "easy"
    DIFFICULTY_MEDIUM = "medium"
    DIFFICULTY_HARD = "hard"

    DIFFICULTY_CHOICES = (
        (DIFFICULTY_EASY, "Easy"),
        (DIFFICULTY_MEDIUM, "Medium"),
        (DIFFICULTY_HARD, "Hard"),
    )

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
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    starter_code = models.TextField(blank=True)
    function_name = models.CharField(max_length=100, default="solve")
    test_cases = models.JSONField(default=list, blank=True)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default=DIFFICULTY_EASY)
    level = models.PositiveSmallIntegerField(default=1)
    question_number = models.PositiveSmallIntegerField(default=1)
    points = models.PositiveSmallIntegerField(default=5)
    hint1 = models.TextField(blank=True)
    hint2 = models.TextField(blank=True)
    hints_used = models.PositiveSmallIntegerField(default=0)
    attempts = models.PositiveSmallIntegerField(default=0)
    failed_tests = models.PositiveSmallIntegerField(default=0)
    runtime_errors = models.PositiveSmallIntegerField(default=0)
    compilation_errors = models.PositiveSmallIntegerField(default=0)
    timeout_errors = models.PositiveSmallIntegerField(default=0)
    penalty_points = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    score = models.PositiveIntegerField(default=0)
    latest_code = models.TextField(blank=True)
    latest_result = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("level", "question_number", "id")

    def __str__(self):
        return f"{self.student.username} - {self.problem.title} ({self.date})"


class StudentChallengeAttempt(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_challenge_attempts",
    )
    challenge = models.ForeignKey(
        DailyChallenge,
        on_delete=models.CASCADE,
        related_name="attempt_history",
    )
    code = models.TextField(blank=True)
    passed_tests = models.PositiveSmallIntegerField(default=0)
    failed_tests = models.PositiveSmallIntegerField(default=0)
    runtime_errors = models.PositiveSmallIntegerField(default=0)
    compilation_errors = models.PositiveSmallIntegerField(default=0)
    timeout_errors = models.PositiveSmallIntegerField(default=0)
    hints_used = models.PositiveSmallIntegerField(default=0)
    penalty_points = models.PositiveSmallIntegerField(default=0)
    final_score = models.PositiveIntegerField(default=0)
    solved = models.BooleanField(default=False)
    result_payload = models.JSONField(default=dict, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-submitted_at",)


class StudentPoints(models.Model):
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_challenge_points",
    )
    total_points = models.PositiveIntegerField(default=0)
    points_spent = models.PositiveIntegerField(default=0)
    points_remaining = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-total_points", "student__username")
