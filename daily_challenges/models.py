from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class QuestionTemplate(models.Model):
    DIFFICULTY_EASY = "easy"
    DIFFICULTY_MEDIUM = "medium"
    DIFFICULTY_HARD = "hard"
    DIFFICULTY_CHOICES = (
        (DIFFICULTY_EASY, "Easy"),
        (DIFFICULTY_MEDIUM, "Medium"),
        (DIFFICULTY_HARD, "Hard"),
    )

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    )

    title_template = models.CharField(max_length=255)
    description_template = models.TextField()
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default=DIFFICULTY_EASY)
    topic = models.CharField(max_length=50, default="general")
    parameter_schema = models.JSONField(default=dict, blank=True)
    starter_code_template = models.TextField(blank=True)
    function_name = models.CharField(max_length=100, default="solve")
    test_cases_template = models.JSONField(default=list, blank=True)
    hint1_template = models.TextField(blank=True)
    hint2_template = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="question_templates",
    )
    approval_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    approval_note = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_question_templates",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("difficulty", "topic", "title_template")

    def __str__(self):
        return f"{self.title_template} ({self.difficulty})"

    @property
    def is_approved(self):
        return self.approval_status == self.STATUS_APPROVED


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
    template = models.ForeignKey(
        QuestionTemplate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="daily_challenge_items",
    )
    date = models.DateField()
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    topic = models.CharField(max_length=50, blank=True)
    generated_parameters = models.JSONField(default=dict, blank=True)
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


class DailyChallengeQuestion(models.Model):
    template = models.ForeignKey(
        QuestionTemplate,
        on_delete=models.CASCADE,
        related_name="generation_history",
    )
    challenge = models.ForeignKey(
        DailyChallenge,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generation_history_rows",
    )
    generated_question = models.CharField(max_length=255)
    parameters_used = models.JSONField(default=dict, blank=True)
    parameter_signature = models.CharField(max_length=255, db_index=True, blank=True)
    date_used = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-date_used", "-created_at")
        indexes = [
            models.Index(fields=["template", "date_used"]),
            models.Index(fields=["date_used", "parameter_signature"]),
        ]

    def __str__(self):
        return f"{self.generated_question} ({self.date_used})"


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
    daily_points = models.IntegerField(default=0)
    points_spent = models.PositiveIntegerField(default=0)
    points_remaining = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-total_points", "student__username")


class DailyChallengeSession(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_challenge_sessions",
    )
    date = models.DateField()
    questions_attempted = models.PositiveSmallIntegerField(default=0)
    questions_solved = models.PositiveSmallIntegerField(default=0)
    points_earned = models.PositiveIntegerField(default=0)
    points_deducted = models.PositiveIntegerField(default=0)
    session_score = models.IntegerField(default=0)
    attempted_challenge_ids = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-date", "-updated_at")
        unique_together = ("student", "date")
