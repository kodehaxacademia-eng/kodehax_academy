from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("teacher", "0005_quizresult"),
    ]

    operations = [
        migrations.AddField(
            model_name="assignment",
            name="attempt_policy",
            field=models.CharField(
                choices=[("once", "Once only"), ("multiple", "Multiple attempts")],
                default="once",
                max_length=10,
            ),
        ),
    ]
