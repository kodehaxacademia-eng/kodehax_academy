from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("daily_challenges", "0002_alter_dailychallenge_options_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="QuestionTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title_template", models.CharField(max_length=255)),
                ("description_template", models.TextField()),
                ("difficulty", models.CharField(choices=[("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard")], default="easy", max_length=10)),
                ("topic", models.CharField(default="general", max_length=50)),
                ("parameter_schema", models.JSONField(blank=True, default=dict)),
                ("starter_code_template", models.TextField(blank=True)),
                ("function_name", models.CharField(default="solve", max_length=100)),
                ("test_cases_template", models.JSONField(blank=True, default=list)),
                ("hint1_template", models.TextField(blank=True)),
                ("hint2_template", models.TextField(blank=True)),
                ("approval_status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending", max_length=10)),
                ("approval_note", models.TextField(blank=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_question_templates", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="question_templates", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("difficulty", "topic", "title_template"),
            },
        ),
        migrations.AddField(
            model_name="dailychallenge",
            name="generated_parameters",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="dailychallenge",
            name="template",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="daily_challenge_items", to="daily_challenges.questiontemplate"),
        ),
        migrations.AddField(
            model_name="dailychallenge",
            name="topic",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.CreateModel(
            name="DailyChallengeQuestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("generated_question", models.CharField(max_length=255)),
                ("parameters_used", models.JSONField(blank=True, default=dict)),
                ("parameter_signature", models.CharField(blank=True, db_index=True, max_length=255)),
                ("date_used", models.DateField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("challenge", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="generation_history_rows", to="daily_challenges.dailychallenge")),
                ("template", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="generation_history", to="daily_challenges.questiontemplate")),
            ],
            options={
                "ordering": ("-date_used", "-created_at"),
                "indexes": [
                    models.Index(fields=["template", "date_used"], name="daily_chall_template_9b66db_idx"),
                    models.Index(fields=["date_used", "parameter_signature"], name="daily_chall_date_us_355771_idx"),
                ],
            },
        ),
    ]
