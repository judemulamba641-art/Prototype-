"""WAY Infrastructure Signals"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import AuditLog, EventLog, StorageObject

@receiver(post_save, sender=AuditLog)
def audit_created(sender, instance, **kwargs):
    # Audit logs are immutable, no cache invalidation needed
    pass

@receiver(post_save, sender=StorageObject)
def storage_updated(sender, instance, **kwargs):
    cache.delete(f"storage:{instance.id}")
