"""
WAY User Notification Service - Enterprise Grade
Full integration with way_ops notifications
"""
from typing import Dict, Any, List
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import structlog

from way_ops.models import Notification
from way_ops.services import NotificationService as CoreNotificationService
from way_user.models import UserNotificationPreference

logger = structlog.get_logger("way_user.notifications")


class NotificationService:
    """Enterprise-grade notification aggregation service."""

    @staticmethod
    def get_notifications(
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
        notification_type: str = None
    ) -> Dict[str, Any]:
        """Get paginated notifications with filtering."""
        qs = Notification.objects.filter(user_id=user_id)

        if unread_only:
            qs = qs.filter(read=False)

        if notification_type:
            qs = qs.filter(notification_type=notification_type)

        total = qs.count()
        notifications = qs.order_by("-created_at")[offset:offset + limit]

        return {
            "items": [{
                "id": str(n.id),
                "type": n.notification_type,
                "title": n.title,
                "body": n.body,
                "payload": n.payload,
                "read": n.read,
                "read_at": n.read_at.isoformat() if n.read_at else None,
                "priority": n.priority,
                "sent_via": n.sent_via,
                "created_at": n.created_at.isoformat(),
            } for n in notifications],
            "total": total,
            "unread": qs.filter(read=False).count(),
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        }

    @staticmethod
    def get_unread_count(user_id: str) -> int:
        """Get unread notification count with caching."""
        cache_key = f"notifications:unread:v2:{user_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        count = Notification.objects.filter(user_id=user_id, read=False).count()
        cache.set(cache_key, count, 30)
        return count

    @staticmethod
    def mark_read(user_id: str, notification_id: str = None) -> bool:
        """Mark notification(s) as read."""
        if notification_id:
            return CoreNotificationService.mark_read(notification_id)
        else:
            count = Notification.objects.filter(
                user_id=user_id, read=False
            ).update(
                read=True,
                read_at=timezone.now()
            )
            cache.delete(f"notifications:unread:v2:{user_id}")
            logger.info("notifications.marked_all_read", user_id=user_id, count=count)
            return True

    @staticmethod
    def get_preferences(user_id: str) -> List[Dict[str, Any]]:
        """Get notification preferences."""
        prefs = UserNotificationPreference.objects.filter(user_id=user_id)

        # Get all possible combinations
        all_types = [t[0] for t in Notification.TYPES]
        all_channels = [c[0] for c in UserNotificationPreference._meta.get_field("channel").choices]

        result = []
        for ntype in all_types:
            for channel in all_channels:
                pref = prefs.filter(notification_type=ntype, channel=channel).first()
                result.append({
                    "notification_type": ntype,
                    "channel": channel,
                    "enabled": pref.enabled if pref else True,
                    "configured": pref is not None,
                })

        return result

    @staticmethod
    def update_preference(
        user_id: str,
        notification_type: str,
        channel: str,
        enabled: bool
    ) -> bool:
        """Update notification preference."""
        pref, _ = UserNotificationPreference.objects.update_or_create(
            user_id=user_id,
            notification_type=notification_type,
            channel=channel,
            defaults={"enabled": enabled}
        )
        logger.info("notification.preference_updated",
                   user_id=user_id, type=notification_type, channel=channel, enabled=enabled)
        return True

    @staticmethod
    def get_recent_alerts(user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent high-priority alerts."""
        alerts = Notification.objects.filter(
            user_id=user_id,
            priority="high",
            read=False
        ).order_by("-created_at")[:limit]

        return [{
            "id": str(a.id),
            "type": a.notification_type,
            "title": a.title,
            "body": a.body,
            "created_at": a.created_at.isoformat(),
        } for a in alerts]
