"""WAY Skills App"""
from django.apps import AppConfig

class WaySkillsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "way_skills"
    verbose_name = "WAY Skills"

    def ready(self):
        from . import signals
