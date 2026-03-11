from django.conf import settings
from django.db import models
from django.utils.text import slugify


class StudentSkill(models.Model):
    LEVEL_BEGINNER = "Beginner"
    LEVEL_BASIC = "Basic"
    LEVEL_INTERMEDIATE = "Intermediate"
    LEVEL_ADVANCED = "Advanced"
    LEVEL_EXPERT = "Expert"

    LEVEL_CHOICES = (
        (LEVEL_BEGINNER, "Beginner"),
        (LEVEL_BASIC, "Basic"),
        (LEVEL_INTERMEDIATE, "Intermediate"),
        (LEVEL_ADVANCED, "Advanced"),
        (LEVEL_EXPERT, "Expert"),
    )

    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="coding_skill_profile",
    )
    skill_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    skill_level = models.CharField(
        max_length=20,
        choices=LEVEL_CHOICES,
        default=LEVEL_BEGINNER,
    )
    weak_topics = models.JSONField(default=dict, blank=True)
    strong_topics = models.JSONField(default=list, blank=True)
    assessment_snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return f"{self.student.username} - {self.skill_level} ({self.skill_score})"


class AssessmentQuestion(models.Model):
    DIFFICULTY_BEGINNER = "beginner"
    DIFFICULTY_BASIC = "basic"
    DIFFICULTY_INTERMEDIATE = "intermediate"

    DIFFICULTY_CHOICES = (
        (DIFFICULTY_BEGINNER, "Beginner"),
        (DIFFICULTY_BASIC, "Basic"),
        (DIFFICULTY_INTERMEDIATE, "Intermediate"),
    )

    question_text = models.TextField()
    topic = models.CharField(max_length=50)
    options = models.JSONField(default=list)
    correct_answer = models.CharField(max_length=255)
    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default=DIFFICULTY_BEGINNER,
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order", "id")

    def __str__(self):
        return f"{self.topic}: {self.question_text[:60]}"


class CodingProblem(models.Model):
    DIFFICULTY_BEGINNER = "beginner"
    DIFFICULTY_BASIC = "basic"
    DIFFICULTY_INTERMEDIATE = "intermediate"
    DIFFICULTY_ADVANCED = "advanced"

    DIFFICULTY_CHOICES = (
        (DIFFICULTY_BEGINNER, "Beginner"),
        (DIFFICULTY_BASIC, "Basic"),
        (DIFFICULTY_INTERMEDIATE, "Intermediate"),
        (DIFFICULTY_ADVANCED, "Advanced"),
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    topic = models.CharField(max_length=50, default="general")
    description = models.TextField()
    starter_code = models.TextField(blank=True)
    function_name = models.CharField(max_length=100, default="solve")
    test_cases = models.JSONField(default=list)
    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default=DIFFICULTY_BEGINNER,
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order", "id")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class StudentAssessment(models.Model):
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="skill_assessment",
    )
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    completed = models.BooleanField(default=False)
    date_completed = models.DateTimeField(null=True, blank=True)
    current_step = models.PositiveSmallIntegerField(default=1)
    self_assessment_answers = models.JSONField(default=dict, blank=True)
    self_assessment_score = models.PositiveIntegerField(default=0)
    mcq_answers = models.JSONField(default=dict, blank=True)
    mcq_score = models.PositiveIntegerField(default=0)
    mcq_breakdown = models.JSONField(default=dict, blank=True)
    coding_answers = models.JSONField(default=dict, blank=True)
    coding_score = models.PositiveIntegerField(default=0)
    coding_breakdown = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        status = "Completed" if self.completed else "In Progress"
        return f"{self.student.username} - {status}"
