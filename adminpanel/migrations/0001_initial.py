# Generated manually for adminpanel app.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AdminUserState",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "teacher_approval_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("suspension_reason", models.CharField(blank=True, max_length=255)),
                ("suspended_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="adminpanel_state",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Admin User State",
                "verbose_name_plural": "Admin User States",
            },
        ),
        migrations.AddIndex(
            model_name="adminuserstate",
            index=models.Index(
                fields=["teacher_approval_status"],
                name="adminpanel_a_teacher_dcb6c9_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="adminuserstate",
            index=models.Index(
                fields=["suspended_at"],
                name="adminpanel_a_suspend_d9ec1c_idx",
            ),
        ),
    ]

