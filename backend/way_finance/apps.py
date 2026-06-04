"""WAY Finance App"""
from django.apps import AppConfig

class WayFinanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "way_finance"
    verbose_name = "WAY Finance"

    def ready(self):
        from . import signals
