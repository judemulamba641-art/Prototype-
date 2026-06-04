"""WAY Finance Signals"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Wallet, CreditLedger, Payment

@receiver(post_save, sender=Wallet)
def invalidate_wallet_cache(sender, instance, **kwargs):
    cache.delete(f"wallet:balance:{instance.id}")

@receiver(post_save, sender=CreditLedger)
def invalidate_ledger_cache(sender, instance, **kwargs):
    cache.delete(f"wallet:balance:{instance.wallet_id}")
    cache.delete(f"ledger:{instance.wallet_id}")

@receiver(post_save, sender=Payment)
def invalidate_payment_cache(sender, instance, **kwargs):
    cache.delete(f"payments:{instance.wallet_id}")
