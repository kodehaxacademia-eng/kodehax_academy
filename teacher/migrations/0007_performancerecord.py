import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("teacher", "0006_assignment_attempt_policy"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PerformanceRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("original_assignment_id", models.PositiveBigIntegerField(db_index=True)),
                ("assignment_title", models.CharField(max_length=255)),
                ("assignment_type", models.CharField(choices=[("file", "File Upload"), ("quiz", "Quiz (MCQ)"), ("code", "Coding")], default="file", max_length=10)),
                ("score", models.FloatField(blank=True, null=True)),
                ("max_score", models.FloatField(default=100)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("due_date_snapshot", models.DateTimeField(blank=True, null=True)),
                ("was_on_time", models.BooleanField(default=True)),
                ("evaluation_type", models.CharField(choices=[("manual", "Manual"), ("ai", "AI"), ("auto", "Auto")], default="manual", max_length=10)),
                ("feedback", models.TextField(blank=True)),
                ("is_deleted_assignment", models.BooleanField(default=False)),
                ("recorded_at", models.DateTimeField(auto_now=True)),
                ("assignment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="performance_records", to="teacher.assignment")),
                ("classroom", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="performance_records", to="teacher.classroom")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="performance_records", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["classroom", "student"], name="teacher_perf_classroo_4753ba_idx"),
                    models.Index(fields=["student", "submitted_at"], name="teacher_perf_student_bcf32f_idx"),
                    models.Index(fields=["classroom", "assignment_type"], name="teacher_perf_classroo_45d4a5_idx"),
                ],
                "unique_together": {("student", "original_assignment_id")},
            },
        ),
    ]
