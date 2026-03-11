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
            name="AssessmentQuestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question_text", models.TextField()),
                ("topic", models.CharField(max_length=50)),
                ("options", models.JSONField(default=list)),
                ("correct_answer", models.CharField(max_length=255)),
                ("difficulty", models.CharField(choices=[("beginner", "Beginner"), ("basic", "Basic"), ("intermediate", "Intermediate")], default="beginner", max_length=20)),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("order", "id")},
        ),
        migrations.CreateModel(
            name="CodingProblem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("slug", models.SlugField(blank=True, max_length=255, unique=True)),
                ("description", models.TextField()),
                ("starter_code", models.TextField(blank=True)),
                ("function_name", models.CharField(default="solve", max_length=100)),
                ("test_cases", models.JSONField(default=list)),
                ("difficulty", models.CharField(choices=[("beginner", "Beginner"), ("basic", "Basic"), ("intermediate", "Intermediate")], default="beginner", max_length=20)),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("order", "id")},
        ),
        migrations.CreateModel(
            name="StudentAssessment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("score", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("completed", models.BooleanField(default=False)),
                ("date_completed", models.DateTimeField(blank=True, null=True)),
                ("current_step", models.PositiveSmallIntegerField(default=1)),
                ("self_assessment_answers", models.JSONField(blank=True, default=dict)),
                ("self_assessment_score", models.PositiveIntegerField(default=0)),
                ("mcq_answers", models.JSONField(blank=True, default=dict)),
                ("mcq_score", models.PositiveIntegerField(default=0)),
                ("mcq_breakdown", models.JSONField(blank=True, default=dict)),
                ("coding_answers", models.JSONField(blank=True, default=dict)),
                ("coding_score", models.PositiveIntegerField(default=0)),
                ("coding_breakdown", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("student", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="skill_assessment", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-updated_at",)},
        ),
        migrations.CreateModel(
            name="StudentSkill",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("skill_score", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("skill_level", models.CharField(choices=[("Beginner", "Beginner"), ("Basic", "Basic"), ("Intermediate", "Intermediate"), ("Advanced", "Advanced"), ("Expert", "Expert")], default="Beginner", max_length=20)),
                ("weak_topics", models.JSONField(blank=True, default=dict)),
                ("strong_topics", models.JSONField(blank=True, default=list)),
                ("assessment_snapshot", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("student", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="coding_skill_profile", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-updated_at",)},
        ),
    ]
