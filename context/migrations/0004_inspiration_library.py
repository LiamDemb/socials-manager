import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0001_initial"),
        ("context", "0003_intelligence_v2"),
    ]

    operations = [
        migrations.AddField(
            model_name="inspirationreference",
            name="canonical_key",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="inspirationreference",
            name="is_bookmark",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="inspirationreference",
            name="origin_type",
            field=models.CharField(
                choices=[("manual", "manual"), ("peer_media", "peer_media")],
                default="manual",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="inspirationreference",
            name="owner_note",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="peerprofile",
            name="collection_paused",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="peerprofile",
            name="peer_role",
            field=models.CharField(
                choices=[
                    ("comparable", "comparable"),
                    ("aspirational", "aspirational"),
                    ("reference_only", "reference_only"),
                    ("excluded", "excluded"),
                    ("unresolved", "unresolved"),
                ],
                default="unresolved",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="inspirationreference",
            name="peer_media",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="saved_references",
                to="context.peermedia",
            ),
        ),
        migrations.CreateModel(
            name="PeerMediaMetricSnapshot",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("captured_at", models.DateTimeField()),
                ("metrics", models.JSONField(default=dict)),
                ("source_version", models.CharField(blank=True, default="", max_length=40)),
                (
                    "media",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="metric_snapshots",
                        to="context.peermedia",
                    ),
                ),
            ],
            options={
                "ordering": ["-captured_at"],
            },
        ),
        migrations.CreateModel(
            name="ActivityReference",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("origin", models.CharField(default="owner_attach", max_length=40)),
                ("note", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField()),
                ("reference_version", models.PositiveIntegerField(default=1)),
                (
                    "activity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reference_links",
                        to="campaigns.activity",
                    ),
                ),
                (
                    "reference",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activity_links",
                        to="context.inspirationreference",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="activityreference",
            constraint=models.UniqueConstraint(fields=("activity", "reference"), name="unique_activity_reference"),
        ),
        migrations.AddConstraint(
            model_name="inspirationreference",
            constraint=models.UniqueConstraint(
                condition=models.Q(("peer_media__isnull", False), ("is_bookmark", True)),
                fields=("peer_media",),
                name="unique_bookmark_per_peer_media",
            ),
        ),
    ]
