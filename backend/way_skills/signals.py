"""WAY Skills Signals"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Skill, Provider, SkillExecution

@receiver(post_save, sender=Skill)
def invalidate_skill_cache(sender, instance, **kwargs):
    cache.delete(f"skill:{instance.id}")
    cache.delete(f"marketplace:{instance.skill_type}")

@receiver(post_save, sender=Provider)
def invalidate_provider_cache(sender, instance, **kwargs):
    for cap in instance.capabilities:
        cache.delete(f"providers:{cap}")

@receiver(post_save, sender=SkillExecution)
def invalidate_execution_cache(sender, instance, **kwargs):
    cache.delete(f"executions:{instance.user_id}")
