"""WAY Core Signals"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import RegistryEntry, SystemConfig


@receiver(post_save, sender=RegistryEntry)
def invalidate_registry_cache(sender, instance, **kwargs):
    cache_key = f"registry:{instance.entity_type}:{instance.entity_id}"
    cache.delete(cache_key)


@receiver(post_save, sender=SystemConfig)
def invalidate_config_cache(sender, instance, **kwargs):
    cache_key = f"config:{instance.key}"
    cache.delete(cache_key)


@receiver(post_delete, sender=SystemConfig)
def delete_config_cache(sender, instance, **kwargs):
    cache_key = f"config:{instance.key}"
    cache.delete(cache_key)
