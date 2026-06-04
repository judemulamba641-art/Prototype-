"""WAY Infrastructure App"""
from django.apps import AppConfig

class WayInfraConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "way_infra"
    verbose_name = "WAY Infrastructure"

    def ready(self):
        from . import signals
