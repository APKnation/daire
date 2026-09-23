from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        # Install DB-level delete-protection triggers for blockchain-produced records.
        from . import immutability  # noqa: F401

        from django.db.models.signals import post_migrate

        post_migrate.connect(immutability.install_after_migrate, sender=self)
