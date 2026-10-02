from django.apps import AppConfig
from django.db.backends.signals import connection_created


class CoreConfig(AppConfig):
    name = "core"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from .sqlite_runtime import configure_connection

        connection_created.connect(configure_connection, dispatch_uid="core.sqlite_runtime")
