from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("skill_assessment", "0003_codingproblem_topic"),
    ]

    operations = [
        migrations.CreateModel(
            name="DailyChallengeSet",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("completed", models.BooleanField(default=False)),
                ("total_score", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="daily_challenge_sets", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-date", "-created_at"), "unique_together": {("student", "date")}},
        ),
        migrations.CreateModel(
            name="DailyChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("solved", "Solved"), ("failed", "Failed")], default="pending", max_length=10)),
                ("score", models.PositiveIntegerField(default=0)),
                ("latest_code", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("challenge_set", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="challenges", to="daily_challenges.dailychallengeset")),
                ("problem", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="daily_challenge_items", to="skill_assessment.codingproblem")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="daily_challenges", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("id",), "unique_together": {("student", "problem", "date")}},
        ),
    ]
