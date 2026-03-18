from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("daily_challenges", "0003_questiontemplate_dailychallengequestion_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="studentpoints",
            name="daily_points",
            field=models.IntegerField(default=0),
        ),
        migrations.CreateModel(
            name="DailyChallengeSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("questions_attempted", models.PositiveSmallIntegerField(default=0)),
                ("questions_solved", models.PositiveSmallIntegerField(default=0)),
                ("points_earned", models.PositiveIntegerField(default=0)),
                ("points_deducted", models.PositiveIntegerField(default=0)),
                ("session_score", models.IntegerField(default=0)),
                ("attempted_challenge_ids", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "student",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="daily_challenge_sessions", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "ordering": ("-date", "-updated_at"),
                "unique_together": {("student", "date")},
            },
        ),
    ]
