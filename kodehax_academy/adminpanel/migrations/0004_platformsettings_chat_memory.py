from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("adminpanel", "0003_platformsettings"),
    ]

    operations = [
        migrations.AddField(
            model_name="platformsettings",
            name="chat_memory_duration",
            field=models.IntegerField(default=30),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="enable_chat_memory",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="max_messages_per_session",
            field=models.IntegerField(default=12),
        ),
    ]
