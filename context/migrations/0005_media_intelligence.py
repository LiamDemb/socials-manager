import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0001_initial"),
        ("context", "0004_inspiration_library"),
    ]

    operations = [
        migrations.AddField(
            model_name="peermedia",
            name="acquisition_revision",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="peermedia",
            name="media_availability",
            field=models.CharField(
                choices=[
                    ("link_only", "link_only"),
                    ("queued", "queued"),
                    ("analysing", "analysing"),
                    ("partial", "partial"),
                    ("ready", "ready"),
                    ("restricted", "restricted"),
                    ("failed", "failed"),
                    ("evicted", "evicted"),
                ],
                default="link_only",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="peermedia",
            name="provider_namespace",
            field=models.CharField(default="instagram", max_length=40),
        ),
        migrations.CreateModel(
            name="MediaAsset",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("role", models.CharField(max_length=40)),
                ("content_hash", models.CharField(blank=True, default="", max_length=64)),
                ("relative_path", models.CharField(blank=True, default="", max_length=300)),
                ("mime_type", models.CharField(blank=True, default="", max_length=80)),
                ("byte_size", models.PositiveIntegerField(default=0)),
                ("width", models.PositiveIntegerField(null=True)),
                ("height", models.PositiveIntegerField(null=True)),
                ("duration_seconds", models.FloatField(null=True)),
                ("captured_at", models.DateTimeField()),
                ("retention_class", models.CharField(default="analysis_derivative", max_length=40)),
                (
                    "post",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assets",
                        to="context.peermedia",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="MediaPack",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("profile_version", models.CharField(default="media-compact-v1", max_length=40)),
                ("input_hash", models.CharField(max_length=64)),
                ("manifest_hash", models.CharField(blank=True, default="", max_length=64)),
                ("state", models.CharField(default="pending", max_length=20)),
                ("reason", models.CharField(blank=True, default="", max_length=120)),
                ("sampling_manifest", models.JSONField(default=dict)),
                ("stored_bytes", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField()),
                ("completed_at", models.DateTimeField(null=True)),
                (
                    "post",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="packs",
                        to="context.peermedia",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("post", "profile_version", "input_hash"),
                        name="unique_media_pack_input",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="ContentAnalysisRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("adapter", models.CharField(max_length=80)),
                ("model_revision", models.CharField(max_length=120)),
                ("schema_version", models.CharField(default="content-labels-v1", max_length=40)),
                ("status", models.CharField(default="pending", max_length=20)),
                ("reason", models.CharField(blank=True, default="", max_length=200)),
                ("output", models.JSONField(default=dict)),
                ("input_hash", models.CharField(max_length=64)),
                ("elapsed_ms", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField()),
                (
                    "pack",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="analysis_runs",
                        to="context.mediapack",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ContentFeatureValue",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("feature_key", models.CharField(max_length=80)),
                ("feature_version", models.CharField(default="1", max_length=20)),
                ("value_json", models.JSONField(default=dict)),
                ("review_state", models.CharField(default="suggested", max_length=20)),
                ("review_revision", models.PositiveIntegerField(default=1)),
                ("support", models.JSONField(default=list)),
                ("origin", models.CharField(default="extraction", max_length=40)),
                ("created_at", models.DateTimeField()),
                (
                    "post",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="content_features",
                        to="context.peermedia",
                    ),
                ),
                (
                    "source_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="feature_values",
                        to="context.contentanalysisrun",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ContentEmbedding",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("encoder_version", models.CharField(max_length=80)),
                ("dimensions", models.PositiveIntegerField()),
                ("vector_blob", models.BinaryField()),
                ("vector_hash", models.CharField(max_length=64)),
                ("frame_role", models.CharField(blank=True, default="", max_length=40)),
                ("created_at", models.DateTimeField()),
                (
                    "asset",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="embeddings",
                        to="context.mediaasset",
                    ),
                ),
                (
                    "post",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="embeddings",
                        to="context.peermedia",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="InspirationRequestRecord",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("schema_version", models.CharField(default="inspiration-request-v1", max_length=40)),
                ("fingerprint", models.CharField(max_length=64, unique=True)),
                ("payload", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField()),
            ],
        ),
        migrations.CreateModel(
            name="InspirationRecommendationRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("policy_version", models.CharField(default="inspiration-rank-v1", max_length=40)),
                ("request_fingerprint", models.CharField(max_length=64)),
                ("candidates", models.JSONField(default=list)),
                ("excluded", models.JSONField(default=list)),
                ("gaps", models.JSONField(default=list)),
                ("created_at", models.DateTimeField()),
                (
                    "request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="runs",
                        to="context.inspirationrequestrecord",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="RecommendationExposure",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("event", models.CharField(max_length=20)),
                ("position", models.PositiveIntegerField(null=True)),
                ("note", models.CharField(blank=True, default="", max_length=200)),
                ("created_at", models.DateTimeField()),
                (
                    "reference",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="context.inspirationreference",
                    ),
                ),
                (
                    "run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="context.inspirationrecommendationrun",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="mediaasset",
            index=models.Index(fields=["post", "role"], name="context_media_post_role"),
        ),
        migrations.AddIndex(
            model_name="contentfeaturevalue",
            index=models.Index(fields=["post", "feature_key", "review_state"], name="context_feat_post_key"),
        ),
    ]
