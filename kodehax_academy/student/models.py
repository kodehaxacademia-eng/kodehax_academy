from django.db import models
from django.conf import settings


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
