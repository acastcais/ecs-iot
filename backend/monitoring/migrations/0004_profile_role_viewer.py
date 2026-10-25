from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("monitoring", "0003_widget_alert_threshold"),
    ]

    operations = [
        migrations.AlterField(
            model_name="profile",
            name="role",
            field=models.CharField(
                choices=[
                    ("global", "Global"),
                    ("admin", "Administrador"),
                    ("owner", "Operador"),
                    ("viewer", "Visualizador"),
                ],
                default="owner",
                max_length=10,
            ),
        ),
    ]
