"""
WAY User Profile Service - Enterprise Grade
Deep integration with way_identity, way_finance, way_skills
"""
from typing import Dict, Any, List, Optional
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import structlog

from way_identity.models import User, Device, Permission, Group, GroupMembership, RefreshToken
from way_identity.auth import JWTService, DeviceService, PermissionService
from way_finance.models import Wallet
from way_skills.models import Skill, SkillInstall
from way_infra.models import AuditLog
from way_ops.models import Notification

logger = structlog.get_logger("way_user.profile")


class ProfileService:
    """Enterprise-grade profile service with full backend integration."""

    @staticmethod
    def get_profile(user_id: str) -> Dict[str, Any]:
        """Get complete user profile with all related data."""
        cache_key = f"user:profile:v2:{user_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return {"error": "User not found", "code": "USER_NOT_FOUND"}

        # Fetch related data in parallel using select_related/prefetch_related
        devices = Device.objects.filter(user=user).order_by("-last_used")
        permissions = Permission.objects.filter(user=user, granted=True, revoked=False)
        groups = GroupMembership.objects.filter(user=user).select_related("group")

        # Get wallet info
        wallet_info = {}
        try:
            wallet = Wallet.objects.get(user_id=user_id)
            wallet_info = {
                "id": str(wallet.id),
                "balance": str(wallet.balance),
                "available": str(wallet.available),
                "currency": wallet.currency,
                "frozen": wallet.frozen,
            }
        except Wallet.DoesNotExist:
            wallet_info = {"error": "No wallet"}

        # Get skill stats
        skill_stats = {
            "owned": Skill.objects.filter(owner_id=user_id).count(),
            "installed": SkillInstall.objects.filter(user_id=user_id, is_active=True).count(),
        }

        # Get security status
        security = {
            "two_factor_enabled": user.two_factor_enabled,
            "failed_login_attempts": user.failed_login_attempts,
            "is_locked": user.is_locked,
            "locked_until": user.locked_until.isoformat() if user.locked_until else None,
            "device_count": devices.count(),
            "approved_devices": devices.filter(is_approved=True).count(),
        }

        profile = {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "display_name": getattr(user, "display_name", "") or user.username,
            "avatar_url": getattr(user, "avatar_url", ""),
            "bio": getattr(user, "bio", ""),
            "phone": getattr(user, "phone", ""),
            "country": getattr(user, "country", ""),
            "language": getattr(user, "language", "en"),
            "timezone": getattr(user, "timezone", "UTC"),
            "is_active": user.is_active,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "date_joined": user.date_joined.isoformat() if user.date_joined else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "wallet": wallet_info,
            "skills": skill_stats,
            "security": security,
            "devices": [{
                "id": str(d.id),
                "name": d.name,
                "device_type": d.device_type,
                "trust_level": d.trust_level,
                "is_approved": d.is_approved,
                "last_used": d.last_used.isoformat() if d.last_used else None,
                "biometric_enabled": d.biometric_enabled,
            } for d in devices[:5]],
            "permissions": [{
                "scope": p.scope,
                "permission_type": p.permission_type,
                "target_id": str(p.target_id) if p.target_id else None,
                "expires_at": p.expires_at.isoformat() if p.expires_at else None,
            } for p in permissions[:10]],
            "groups": [{
                "id": str(g.group.id),
                "name": g.group.name,
                "role": g.role,
            } for g in groups],
        }

        cache.set(cache_key, profile, 300)
        return profile

    @staticmethod
    def get_profile_summary(user_id: str) -> Dict[str, Any]:
        """Get lightweight profile summary."""
        profile = ProfileService.get_profile(user_id)
        if "error" in profile:
            return profile
        return {
            "id": profile["id"],
            "display_name": profile["display_name"],
            "email": profile["email"],
            "avatar_url": profile["avatar_url"],
            "is_staff": profile["is_staff"],
            "wallet_summary": profile.get("wallet", {}),
        }

    @staticmethod
    def update_profile(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user profile with validation."""
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return {"error": "User not found", "code": "USER_NOT_FOUND"}

        # Update user fields
        allowed_user_fields = ["display_name", "bio", "phone", "country", "avatar_url", "language", "timezone"]
        updated_fields = []
        for field in allowed_user_fields:
            if field in data:
                setattr(user, field, data[field])
                updated_fields.append(field)

        if updated_fields:
            user.save(update_fields=updated_fields)

        # Update preferences
        if any(k in data for k in ["theme", "email_notifications", "push_notifications", "sms_notifications"]):
            from way_user.models import UserPreference
            prefs, _ = UserPreference.objects.get_or_create(user_id=user_id)
            for field in ["theme", "accent_color", "font_size", "email_notifications", "push_notifications", "sms_notifications", "profile_visible", "activity_visible"]:
                if field in data:
                    setattr(prefs, field, data[field])
            prefs.save()

        # Update theme
        if any(k in data for k in ["primary_color", "background_color", "font_family"]):
            from way_user.models import UserThemePreference
            theme, _ = UserThemePreference.objects.get_or_create(user_id=user_id)
            for field in ["primary_color", "secondary_color", "background_color", "surface_color", "text_color", "border_radius", "font_family"]:
                if field in data:
                    setattr(theme, field, data[field])
            theme.save()

        # Invalidate cache
        cache.delete(f"user:profile:v2:{user_id}")
        cache.delete(f"dashboard:v2:{user_id}:user")

        # Log audit
        AuditService = __import__("way_infra.services", fromlist=["AuditService"]).AuditService
        AuditService.log(
            entity_type="user",
            entity_id=user_id,
            action="update_profile",
            user_id=user_id,
            before={},
            after={k: v for k, v in data.items() if k in allowed_user_fields},
            severity="info",
        )

        logger.info("profile.updated", user_id=user_id, fields=updated_fields)
        return {"success": True, "updated_fields": updated_fields}

    @staticmethod
    def get_activity(user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive user activity."""
        from way_skills.models import SkillExecution
        from way_finance.models import CreditLedger, Payment
        from way_ops.models import Notification

        start_date = timezone.now() - timedelta(days=days)

        # Executions
        executions = SkillExecution.objects.filter(
            user_id=user_id, created_at__gte=start_date
        ).select_related("skill", "provider")

        # Financial activity
        try:
            wallet = Wallet.objects.get(user_id=user_id)
            transactions = CreditLedger.objects.filter(
                wallet=wallet, created_at__gte=start_date
            )
            payments = Payment.objects.filter(
                wallet=wallet, created_at__gte=start_date
            )
        except Wallet.DoesNotExist:
            transactions = []
            payments = []

        # Notifications
        notifications = Notification.objects.filter(
            user_id=user_id, created_at__gte=start_date
        )

        # Audit logs
        audit_logs = AuditLog.objects.filter(
            user_id=user_id, created_at__gte=start_date
        ).order_by("-created_at")[:50]

        return {
            "period_days": days,
            "period_start": start_date.isoformat(),
            "executions": {
                "total": executions.count(),
                "completed": executions.filter(status="completed").count(),
                "failed": executions.filter(status="failed").count(),
                "total_cost": str(sum(float(e.cost) for e in executions)),
                "avg_latency_ms": executions.aggregate(
                    avg=__import__("django.db.models", fromlist=["Avg"]).Avg("latency_ms")
                )["latency_ms__avg"] or 0,
                "items": [{
                    "id": str(e.id),
                    "skill_name": e.skill.name if e.skill else "Unknown",
                    "status": e.status,
                    "cost": str(e.cost),
                    "created_at": e.created_at.isoformat(),
                } for e in executions.order_by("-created_at")[:10]],
            },
            "financial": {
                "transactions_count": len(transactions) if isinstance(transactions, list) else transactions.count(),
                "credits_spent": str(sum(float(t.amount) for t in (transactions if not isinstance(transactions, list) else []) if t.amount < 0)),
                "credits_received": str(sum(float(t.amount) for t in (transactions if not isinstance(transactions, list) else []) if t.amount > 0)),
                "payments_count": len(payments) if isinstance(payments, list) else payments.count(),
                "deposits": str(sum(float(p.amount) for p in (payments if not isinstance(payments, list) else []) if p.direction == "deposit")),
                "withdrawals": str(sum(float(p.amount) for p in (payments if not isinstance(payments, list) else []) if p.direction == "withdraw")),
            },
            "notifications": {
                "total": notifications.count(),
                "read": notifications.filter(read=True).count(),
                "unread": notifications.filter(read=False).count(),
            },
            "audit_trail": [{
                "id": str(a.id),
                "entity_type": a.entity_type,
                "action": a.action,
                "severity": a.severity,
                "created_at": a.created_at.isoformat(),
            } for a in audit_logs],
        }

    @staticmethod
    def get_security_settings(user_id: str) -> Dict[str, Any]:
        """Get comprehensive security settings."""
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return {"error": "User not found"}

        devices = Device.objects.filter(user=user)
        tokens = RefreshToken.objects.filter(user=user, revoked=False)

        return {
            "two_factor": {
                "enabled": user.two_factor_enabled,
                "secret_set": bool(user.two_factor_secret),
            },
            "password": {
                "last_changed": getattr(user, "password_changed_at", None),
                "strength": "strong",  # Would be calculated
            },
            "devices": {
                "total": devices.count(),
                "approved": devices.filter(is_approved=True).count(),
                "biometric_enabled": devices.filter(biometric_enabled=True).count(),
                "recent": [{
                    "id": str(d.id),
                    "name": d.name,
                    "type": d.device_type,
                    "trust_level": d.trust_level,
                    "last_used": d.last_used.isoformat() if d.last_used else None,
                } for d in devices.order_by("-last_used")[:5]],
            },
            "sessions": {
                "active_tokens": tokens.count(),
                "expires_soon": tokens.filter(
                    expires_at__lte=timezone.now() + timedelta(days=7)
                ).count(),
            },
            "account": {
                "locked": user.is_locked,
                "failed_attempts": user.failed_login_attempts,
                "lockout_remaining": (user.locked_until - timezone.now()).total_seconds() if user.locked_until and user.locked_until > timezone.now() else 0,
            },
        }

    @staticmethod
    def get_devices(user_id: str) -> List[Dict[str, Any]]:
        """Get all user devices with full details."""
        devices = Device.objects.filter(user_id=user_id).order_by("-last_used")
        return [{
            "id": str(d.id),
            "name": d.name,
            "device_type": d.device_type,
            "fingerprint": d.fingerprint[:20] + "..." if d.fingerprint else None,
            "trust_level": d.trust_level,
            "is_approved": d.is_approved,
            "last_used": d.last_used.isoformat() if d.last_used else None,
            "ip_address": str(d.ip_address) if d.ip_address else None,
            "user_agent": d.user_agent[:50] + "..." if d.user_agent else None,
            "biometric_enabled": d.biometric_enabled,
            "public_key": d.public_key[:30] + "..." if d.public_key else None,
        } for d in devices]

    @staticmethod
    def revoke_device(user_id: str, device_id: str) -> Dict[str, Any]:
        """Revoke a device and its tokens."""
        try:
            device = Device.objects.get(id=device_id, user_id=user_id)
        except Device.DoesNotExist:
            return {"error": "Device not found"}

        device.is_approved = False
        device.trust_level = "untrusted"
        device.save(update_fields=["is_approved", "trust_level"])

        # Revoke all tokens for this device
        RefreshToken.objects.filter(device=device, revoked=False).update(
            revoked=True, revoked_at=timezone.now()
        )

        # Log audit
        AuditService = __import__("way_infra.services", fromlist=["AuditService"]).AuditService
        AuditService.log(
            entity_type="device",
            entity_id=device_id,
            action="revoke",
            user_id=user_id,
            severity="warning",
        )

        cache.delete(f"user:profile:v2:{user_id}")
        return {"success": True, "device_id": device_id}
