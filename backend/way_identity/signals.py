"""WAY Identity Signals"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import User, Device, Permission

@receiver(post_save, sender=User)
def invalidate_user_cache(sender, instance, **kwargs):
    cache.delete(f"user:{instance.id}")
    cache.delete(f"user:email:{instance.email}")

@receiver(post_save, sender=Device)
def invalidate_device_cache(sender, instance, **kwargs):
    cache.delete(f"device:{instance.id}")

@receiver(post_save, sender=Permission)
def invalidate_permission_cache(sender, instance, **kwargs):
    cache.delete(f"permissions:{instance.user_id}")
