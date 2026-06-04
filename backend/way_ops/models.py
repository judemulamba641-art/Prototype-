"""
WAY Operations Models - Notifications + Admin + Rate Limiting + Groups
"""
from django.db import models
from django.utils import timezone
from way_core.models import BaseModel


class Notification(BaseModel):
    """User notifications."""
    TYPES = [
        ("payment_success", "Payment Success"), ("payment_failed", "Payment Failed"),
        ("credits_received", "Credits Received"), ("skill_installed", "Skill Installed"),
        ("skill_executed", "Skill Executed"), ("wallet_updated", "Wallet Updated"),
        ("security_alert", "Security Alert"), ("system", "System"),
    ]
    user_id = models.UUIDField(db_index=True)
    notification_type = models.CharField(max_length=20, choices=TYPES)
    title = models.CharField(max_length=255)
    body = models.TextField()
    payload = models.JSONField(default=dict, blank=True)
    read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    sent_via = models.JSONField(default=list, blank=True)  # ["push", "email", "ws"]
    priority = models.CharField(max_length=10, choices=[("low", "Low"), ("normal", "Normal"), ("high", "High")], default="normal")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user_id", "read", "created_at"])]


class AdminAction(BaseModel):
    """Admin action log."""
    ACTIONS = [
        ("freeze_wallet", "Freeze Wallet"), ("unfreeze_wallet", "Unfreeze Wallet"),
        ("approve_skill", "Approve Skill"), ("suspend_skill", "Suspend Skill"),
        ("grant_permission", "Grant Permission"), ("revoke_permission", "Revoke Permission"),
        ("ban_user", "Ban User"), ("unban_user", "Unban User"),
    ]
    admin_id = models.UUIDField(db_index=True)
    action = models.CharField(max_length=20, choices=ACTIONS)
    target_type = models.CharField(max_length=20)  # user, wallet, skill
    target_id = models.UUIDField()
    reason = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    reverted = models.BooleanField(default=False)
    reverted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["admin_id", "action", "created_at"])]


class CurrencyRate(BaseModel):
    """Currency conversion rates."""
    from_currency = models.CharField(max_length=3, db_index=True)
    to_currency = models.CharField(max_length=3, db_index=True)
    rate = models.DecimalField(max_digits=20, decimal_places=10)
    source = models.CharField(max_length=50, default="internal")
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["from_currency", "to_currency"]]
