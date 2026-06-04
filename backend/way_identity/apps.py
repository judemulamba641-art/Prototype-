"""WAY Identity App"""
from django.apps import AppConfig

class WayIdentityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "way_identity"
    verbose_name = "WAY Identity"

    def ready(self):
        from . import signals
