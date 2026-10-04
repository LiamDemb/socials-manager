import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("context", "0005_media_intelligence"),
    ]

    operations = [
        migrations.AddField(
            model_name="recommendationexposure",
            name="peer_media",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="exposures",
                to="context.peermedia",
            ),
        ),
        migrations.AlterField(
            model_name="recommendationexposure",
            name="reference",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="context.inspirationreference",
            ),
        ),
    ]
