# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):

    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('admin', 'Admin'),
    )

    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    is_email_verified = models.BooleanField(default=False)
    last_otp_verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.username
