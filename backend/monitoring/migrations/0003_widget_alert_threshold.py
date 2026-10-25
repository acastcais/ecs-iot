from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("monitoring", "0002_seed_product_types"),
    ]

    operations = [
        migrations.AddField(
            model_name="widget",
            name="alert_threshold",
            field=models.FloatField(
                blank=True,
                null=True,
                help_text=(
                    "Opcional, para cualquier gadget: si se define, se muestra una luz piloto bajo el sensor "
                    "(verde en rango normal, roja cuando el valor es mayor o igual a este umbral)."
                ),
            ),
        ),
    ]
