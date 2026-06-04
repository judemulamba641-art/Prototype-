"""WAY Core App"""
from django.apps import AppConfig

class WayCoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "way_core"
    verbose_name = "WAY Core"

    def ready(self):
        from . import signals
