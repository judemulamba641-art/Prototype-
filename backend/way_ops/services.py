"""
WAY Operations Services - Notifications, Admin, Currency
"""
from typing import Dict, List
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import structlog

from .models import Notification, AdminAction, CurrencyRate

logger = structlog.get_logger("way.ops")


class NotificationService:
    """Multi-channel notification service."""

    @staticmethod
    def send(user_id: str, notification_type: str, payload: Dict, channels: List[str] = None) -> Notification:
        """Send notification via multiple channels."""
        channels = channels or ["push", "ws"]
        title = payload.get("title", "WAY Notification")
        body = payload.get("body", "")

        notification = Notification.objects.create(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            body=body,
            payload=payload,
            sent_via=channels,
        )

        # WebSocket
        if "ws" in channels:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"user_{user_id}",
                {
                    "type": "notification",
                    "notification_type": notification_type,
                    "payload": payload,
                    "timestamp": timezone.now().isoformat(),
                }
            )

        # Push (FCM/APNS) - placeholder
        if "push" in channels:
            logger.info("notification.push_sent", user_id=user_id, notification_id=str(notification.id))

        # Email - placeholder
        if "email" in channels:
            logger.info("notification.email_sent", user_id=user_id, notification_id=str(notification.id))

        logger.info("notification.sent", user_id=user_id, type=notification_type, channels=channels)
        return notification

    @staticmethod
    def send_admin_alert(alert_type: str, payload: Dict):
        """Send alert to admin channels."""
        logger.warning("admin.alert", alert_type=alert_type, payload=payload)
        # In production: send to admin dashboard, Slack, PagerDuty

    @staticmethod
    def mark_read(notification_id: str) -> bool:
        try:
            notification = Notification.objects.get(id=notification_id)
            notification.read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["read", "read_at"])
            return True
        except Notification.DoesNotExist:
            return False

    @staticmethod
    def get_unread(user_id: str) -> List[Notification]:
        return list(Notification.objects.filter(user_id=user_id, read=False).order_by("-created_at"))


class AdminService:
    """Admin action management."""

    @staticmethod
    def log_action(admin_id: str, action: str, target_type: str, target_id: str, reason: str, metadata: Dict = None) -> AdminAction:
        return AdminAction.objects.create(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            metadata=metadata or {},
        )

    @staticmethod
    def revert_action(action_id: str) -> bool:
        try:
            action = AdminAction.objects.get(id=action_id)
            # Revert logic based on action type
            if action.action == "freeze_wallet":
                from way_finance.services import WalletService
                WalletService.unfreeze_wallet(str(action.target_id))
            elif action.action == "suspend_skill":
                from way_skills.models import Skill
                Skill.objects.filter(id=action.target_id).update(lifecycle="production")
            action.reverted = True
            action.reverted_at = timezone.now()
            action.save(update_fields=["reverted", "reverted_at"])
            return True
        except AdminAction.DoesNotExist:
            return False


class CurrencyService:
    """Currency conversion service."""

    @staticmethod
    def get_rate(from_currency: str, to_currency: str) -> float:
        cache_key = f"currency:{from_currency}:{to_currency}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            rate = CurrencyRate.objects.get(from_currency=from_currency, to_currency=to_currency)
            cache.set(cache_key, float(rate.rate), 3600)
            return float(rate.rate)
        except CurrencyRate.DoesNotExist:
            if from_currency == to_currency:
                return 1.0
            return 0.0

    @staticmethod
    def convert(amount: float, from_currency: str, to_currency: str) -> float:
        rate = CurrencyService.get_rate(from_currency, to_currency)
        return amount * rate

    @staticmethod
    def update_rate(from_currency: str, to_currency: str, rate: float, source: str = "internal"):
        CurrencyRate.objects.update_or_create(
            from_currency=from_currency,
            to_currency=to_currency,
            defaults={"rate": rate, "source": source}
        )
        cache.delete(f"currency:{from_currency}:{to_currency}")
