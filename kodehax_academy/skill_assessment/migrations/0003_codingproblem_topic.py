from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("skill_assessment", "0002_seed_default_content"),
    ]

    operations = [
        migrations.AddField(
            model_name="codingproblem",
            name="topic",
            field=models.CharField(default="general", max_length=50),
        ),
    ]
