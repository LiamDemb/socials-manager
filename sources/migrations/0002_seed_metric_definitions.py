from django.db import migrations


def seed(apps, schema_editor):
    from sources.metric_registry import sync_definitions

    sync_definitions(apps.get_model("sources", "MetricDefinition"))


class Migration(migrations.Migration):
    dependencies = [("sources", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
