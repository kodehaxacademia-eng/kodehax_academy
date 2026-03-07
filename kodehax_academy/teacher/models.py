from django.db import models
from django.conf import settings
import random
import string

User = settings.AUTH_USER_MODEL


# -----------------------------
# CLASSROOM CODE GENERATOR
# -----------------------------
def generate_class_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


# -----------------------------
# CLASSROOM
# -----------------------------
class ClassRoom(models.Model):

    name = models.CharField(max_length=255)

    description = models.TextField(blank=True)

    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="teacher_classes"
    )

    students = models.ManyToManyField(
        User,
        related_name="enrolled_classes",
        blank=True
    )

    class_code = models.CharField(
        max_length=6,
        unique=True,
        default=generate_class_code
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.class_code})"


# -----------------------------
# ASSIGNMENT
# -----------------------------
class Assignment(models.Model):

    classroom = models.ForeignKey(
        ClassRoom,
        on_delete=models.CASCADE,
        related_name="assignments"
    )

    title = models.CharField(max_length=255)

    description = models.TextField()

    due_date = models.DateTimeField()

    max_score = models.FloatField(default=100)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.classroom.name}"


# -----------------------------
# SUBMISSION
# -----------------------------
class Submission(models.Model):

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="submissions"
    )

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    file = models.FileField(upload_to="assignments/")

    submitted_at = models.DateTimeField(auto_now_add=True)

    # AI evaluation results
    score = models.FloatField(null=True, blank=True)

    ai_feedback = models.TextField(blank=True)

    class Meta:
        unique_together = ('assignment', 'student')

    def __str__(self):
        return f"{self.student} - {self.assignment.title}"


# -----------------------------
# CHAT MESSAGE
# -----------------------------
class ChatMessage(models.Model):

    classroom = models.ForeignKey(
        ClassRoom,
        on_delete=models.CASCADE,
        related_name="messages"
    )

    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    message = models.TextField()

    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender}: {self.message[:30]}"
