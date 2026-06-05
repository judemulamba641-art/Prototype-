"""
WAY User Dashboard Service - Enterprise Grade
Full integration with all WAY backend services
"""
from typing import Dict, Any, List, Optional
from decimal import Decimal
from django.core.cache import cache
from django.conf import settings
from django.db import connection
from django.utils import timezone
from datetime import timedelta
import structlog
import asyncio
from concurrent.futures import ThreadPoolExecutor

from way_core.models import RegistryEntry, RuntimeSession, SystemConfig
from way_core.services import RegistryService, RuntimeService, HealthService, ConfigService
from way_identity.models import User, Device, Permission, Group, GroupMembership
from way_identity.auth import JWTService, PermissionService
from way_finance.models import Wallet, CreditReserve, CreditLedger, Payment, CreditTransfer, BillingReport
from way_finance.services import WalletService, CreditService, PaymentService, BillingService
from way_skills.models import Skill, Provider, SkillExecution, PricingRule, SkillInstall, MarketplaceReview
from way_skills.services import SkillService, ProviderRouter, PricingEngine, ExecutionService, MarketplaceService
from way_infra.models import AuditLog, EventLog, TelemetryMetric, CacheMetadata, StorageObject
from way_infra.services import EventBus, CacheService, StorageService, AuditService, TelemetryService, BackupService
from way_ops.models import Notification, AdminAction, CurrencyRate
from way_ops.services import NotificationService, AdminService, CurrencyService

logger = structlog.get_logger("way_user.dashboard")


class DashboardService:
    """
    Enterprise-grade dashboard aggregation service.
    Fetches data from ALL backend services in parallel with caching.
    """

    DASHBOARD_TYPES = ["user", "developer", "auditor", "investor", "admin", "ops"]

    @staticmethod
    def get_dashboard(user_id: str, dashboard_type: str = "user") -> Dict[str, Any]:
        """Get complete dashboard with parallel data fetching."""
        cache_key = f"dashboard:v2:{user_id}:{dashboard_type}"
        cached = cache.get(cache_key)
        if cached:
            logger.info("dashboard.cache_hit", user_id=user_id, type=dashboard_type)
            return cached

        # Parallel data fetching using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                "profile": executor.submit(DashboardService._get_profile_data, user_id),
                "wallet": executor.submit(DashboardService._get_wallet_data, user_id),
                "credits": executor.submit(DashboardService._get_credits_data, user_id),
                "skills": executor.submit(DashboardService._get_skills_data, user_id),
                "notifications": executor.submit(DashboardService._get_notifications_data, user_id),
                "system": executor.submit(DashboardService._get_system_data),
            }

            # Add dashboard-specific futures
            if dashboard_type == "developer":
                futures["developer"] = executor.submit(DashboardService._get_developer_data, user_id)
            elif dashboard_type == "admin":
                futures["admin"] = executor.submit(DashboardService._get_admin_data)
            elif dashboard_type == "ops":
                futures["ops"] = executor.submit(DashboardService._get_ops_data)
            elif dashboard_type == "auditor":
                futures["auditor"] = executor.submit(DashboardService._get_auditor_data)
            elif dashboard_type == "investor":
                futures["investor"] = executor.submit(DashboardService._get_investor_data)

            results = {k: v.result() for k, v in futures.items()}

        dashboard = {
            "type": dashboard_type,
            "user_id": user_id,
            "profile": results["profile"],
            "wallet": results["wallet"],
            "credits": results["credits"],
            "skills": results["skills"],
            "notifications": results["notifications"],
            "system": results["system"],
            "widgets": DashboardService._get_widgets_for_type(dashboard_type, user_id),
            "timestamp": timezone.now().isoformat(),
            "version": "2.4.0",
        }

        # Add dashboard-specific data
        for key in ["developer", "admin", "ops", "auditor", "investor"]:
            if key in results:
                dashboard[f"{key}_stats"] = results[key]

        # Cache for 30 seconds (real-time feel)
        cache.set(cache_key, dashboard, 30)
        logger.info("dashboard.loaded", user_id=user_id, type=dashboard_type)
        return dashboard

    @staticmethod
    def _get_profile_data(user_id: str) -> Dict[str, Any]:
        """Fetch profile data from way_identity."""
        try:
            user = User.objects.get(id=user_id)
            return {
                "id": str(user.id),
                "email": user.email,
                "username": user.username,
                "display_name": getattr(user, "display_name", ""),
                "avatar_url": getattr(user, "avatar_url", ""),
                "bio": getattr(user, "bio", ""),
                "phone": getattr(user, "phone", ""),
                "country": getattr(user, "country", ""),
                "two_factor_enabled": getattr(user, "two_factor_enabled", False),
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "date_joined": user.date_joined.isoformat() if user.date_joined else None,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "device_count": Device.objects.filter(user=user).count(),
                "group_count": GroupMembership.objects.filter(user=user).count(),
            }
        except User.DoesNotExist:
            return {"error": "User not found"}

    @staticmethod
    def _get_wallet_data(user_id: str) -> Dict[str, Any]:
        """Fetch wallet data from way_finance."""
        try:
            wallet = Wallet.objects.get(user_id=user_id)
            balance_data = WalletService.get_balance(str(wallet.id))

            # Get recent transactions
            recent_tx = CreditLedger.objects.filter(
                wallet=wallet
            ).order_by("-created_at")[:5]

            # Get recent payments
            recent_payments = Payment.objects.filter(
                wallet=wallet
            ).order_by("-created_at")[:5]

            return {
                "id": str(wallet.id),
                "balance": str(balance_data.get("balance", "0")),
                "reserved": str(balance_data.get("reserved", "0")),
                "available": str(balance_data.get("available", "0")),
                "currency": wallet.currency,
                "is_active": wallet.is_active,
                "frozen": wallet.frozen,
                "frozen_reason": wallet.frozen_reason if wallet.frozen else None,
                "last_transaction": wallet.last_transaction.isoformat() if wallet.last_transaction else None,
                "recent_transactions": [{
                    "id": str(t.id),
                    "type": t.tx_type,
                    "amount": str(t.amount),
                    "created_at": t.created_at.isoformat(),
                } for t in recent_tx],
                "recent_payments": [{
                    "id": str(p.id),
                    "provider": p.provider,
                    "direction": p.direction,
                    "amount": str(p.amount),
                    "status": p.status,
                    "created_at": p.created_at.isoformat(),
                } for p in recent_payments],
            }
        except Wallet.DoesNotExist:
            return {"error": "No wallet found", "user_id": user_id}

    @staticmethod
    def _get_credits_data(user_id: str) -> Dict[str, Any]:
        """Fetch credits data from way_finance."""
        try:
            wallet = Wallet.objects.get(user_id=user_id)
            reserve = CreditReserve.objects.filter(currency=wallet.currency).first()

            # Get ledger summary
            ledger_summary = CreditLedger.objects.filter(
                wallet=wallet
            ).aggregate(
                total_minted=__import__("django.db.models", fromlist=["Sum"]).Sum(
                    "amount", filter=__import__("django.db.models", fromlist=["Q"]).Q(amount__gt=0)
                ),
                total_burned=__import__("django.db.models", fromlist=["Sum"]).Sum(
                    "amount", filter=__import__("django.db.models", fromlist=["Q"]).Q(amount__lt=0)
                ),
            )

            return {
                "balance": str(wallet.balance),
                "available": str(wallet.available),
                "currency": wallet.currency,
                "rate": str(reserve.rate) if reserve else "100",
                "usd_equivalent": str(float(wallet.balance) / float(reserve.rate)) if reserve else "0",
                "total_minted": str(ledger_summary.get("total_minted") or 0),
                "total_burned": str(abs(ledger_summary.get("total_burned") or 0)),
                "reserve_backing": str(reserve.total_reserve) if reserve else "0",
            }
        except Wallet.DoesNotExist:
            return {"error": "No wallet found"}

    @staticmethod
    def _get_skills_data(user_id: str) -> Dict[str, Any]:
        """Fetch skills data from way_skills."""
        user_skills = Skill.objects.filter(owner_id=user_id)
        installed = SkillInstall.objects.filter(user_id=user_id, is_active=True)

        # Get recent executions
        recent_executions = SkillExecution.objects.filter(
            user_id=user_id
        ).select_related("skill", "provider").order_by("-created_at")[:5]

        return {
            "owned": {
                "total": user_skills.count(),
                "published": user_skills.filter(lifecycle="production").count(),
                "draft": user_skills.filter(lifecycle="draft").count(),
                "suspended": user_skills.filter(lifecycle="suspended").count(),
                "total_usage": sum(s.usage_count for s in user_skills),
                "avg_rating": sum(s.rating_avg for s in user_skills) / user_skills.count() if user_skills.count() > 0 else 0,
            },
            "installed": {
                "total": installed.count(),
                "recently_used": installed.filter(
                    last_used__gte=timezone.now() - timedelta(days=7)
                ).count(),
            },
            "recent_executions": [{
                "id": str(e.id),
                "skill_name": e.skill.name if e.skill else "Unknown",
                "provider_name": e.provider.name if e.provider else "Unknown",
                "status": e.status,
                "cost": str(e.cost),
                "tokens_used": e.tokens_used,
                "latency_ms": e.latency_ms,
                "cache_hit": e.cache_hit,
                "created_at": e.created_at.isoformat(),
            } for e in recent_executions],
        }

    @staticmethod
    def _get_notifications_data(user_id: str) -> Dict[str, Any]:
        """Fetch notifications from way_ops."""
        unread = Notification.objects.filter(user_id=user_id, read=False).count()
        recent = Notification.objects.filter(
            user_id=user_id
        ).order_by("-created_at")[:5]

        # Get high priority alerts
        high_priority = Notification.objects.filter(
            user_id=user_id, read=False, priority="high"
        ).count()

        return {
            "unread_count": unread,
            "high_priority": high_priority,
            "recent": [{
                "id": str(n.id),
                "type": n.notification_type,
                "title": n.title,
                "read": n.read,
                "priority": n.priority,
                "created_at": n.created_at.isoformat(),
            } for n in recent],
        }

    @staticmethod
    def _get_system_data() -> Dict[str, Any]:
        """Fetch system health data from way_core."""
        health = HealthService.check()
        providers = Provider.objects.all()

        return {
            "status": health.get("status", "unknown"),
            "version": health.get("version", "2.4.0"),
            "uptime": health.get("uptime", 0),
            "services": health.get("services", {}),
            "providers": {
                p.name: {
                    "status": p.status,
                    "latency_ms": p.latency_ms,
                    "success_rate": p.success_rate,
                    "quota_remaining": p.quota_remaining,
                }
                for p in providers
            },
            "active_providers": Provider.objects.filter(status="active").count(),
            "degraded_providers": Provider.objects.filter(status="degraded").count(),
        }

    @staticmethod
    def _get_developer_data(user_id: str) -> Dict[str, Any]:
        """Fetch developer-specific stats."""
        skills = Skill.objects.filter(owner_id=user_id)
        skill_ids = [s.id for s in skills]

        executions = SkillExecution.objects.filter(
            skill_id__in=skill_ids, status="completed"
        )

        reviews = MarketplaceReview.objects.filter(
            skill_id__in=skill_ids
        )

        total_revenue = sum(float(e.cost) for e in executions)

        return {
            "total_skills": skills.count(),
            "published_skills": skills.filter(lifecycle="production").count(),
            "total_executions": executions.count(),
            "total_revenue": str(total_revenue),
            "avg_rating": sum(s.rating_avg for s in skills) / skills.count() if skills.count() > 0 else 0,
            "total_reviews": reviews.count(),
            "avg_review_rating": sum(r.rating for r in reviews) / reviews.count() if reviews.count() > 0 else 0,
        }

    @staticmethod
    def _get_admin_data() -> Dict[str, Any]:
        """Fetch admin-specific stats."""
        now = timezone.now()
        today = now.date()

        return {
            "users": {
                "total": User.objects.count(),
                "active": User.objects.filter(is_active=True).count(),
                "new_today": User.objects.filter(date_joined__date=today).count(),
                "locked": User.objects.filter(
                    locked_until__isnull=False, locked_until__gt=now
                ).count(),
            },
            "skills": {
                "total": Skill.objects.count(),
                "pending_approval": Skill.objects.filter(lifecycle="review").count(),
                "suspended": Skill.objects.filter(lifecycle="suspended").count(),
            },
            "payments": {
                "pending": Payment.objects.filter(status="pending").count(),
                "completed_today": Payment.objects.filter(
                    status="completed", processed_at__date=today
                ).count(),
                "failed_today": Payment.objects.filter(
                    status="failed", created_at__date=today
                ).count(),
            },
            "audit": {
                "total_logs": AuditLog.objects.count(),
                "today_logs": AuditLog.objects.filter(created_at__date=today).count(),
                "critical_events": AuditLog.objects.filter(severity="critical").count(),
            },
        }

    @staticmethod
    def _get_ops_data() -> Dict[str, Any]:
        """Fetch ops-specific stats."""
        # System metrics
        cpu_metric = TelemetryMetric.objects.filter(
            metric_type="cpu", window="1m"
        ).order_by("-created_at").first()

        ram_metric = TelemetryMetric.objects.filter(
            metric_type="ram", window="1m"
        ).order_by("-created_at").first()

        # Cache stats
        cache_stats = CacheService.get_stats()

        # Events
        pending_events = EventLog.objects.filter(processed=False).count()

        return {
            "providers": {
                "active": Provider.objects.filter(status="active").count(),
                "degraded": Provider.objects.filter(status="degraded").count(),
                "down": Provider.objects.filter(status="down").count(),
            },
            "system": {
                "cpu": cpu_metric.value if cpu_metric else 0,
                "ram": ram_metric.value if ram_metric else 0,
            },
            "cache": cache_stats,
            "events": {
                "pending": pending_events,
                "failed_today": EventLog.objects.filter(
                    processed=False, retry_count__gte=5, created_at__date=timezone.now().date()
                ).count(),
            },
            "runtime": {
                "active_sessions": RuntimeSession.objects.filter(status="running").count(),
                "queued_executions": SkillExecution.objects.filter(status="queued").count(),
            },
        }

    @staticmethod
    def _get_auditor_data() -> Dict[str, Any]:
        """Fetch auditor-specific stats."""
        return {
            "audit_trail": {
                "total_entries": AuditLog.objects.count(),
                "verified": AuditService.verify_chain()[0],
                "by_entity": {
                    entity: AuditLog.objects.filter(entity_type=entity).count()
                    for entity in ["credit", "wallet", "admin", "skill", "payment", "auth"]
                },
            },
            "fraud": {
                "total_detected": Payment.objects.filter(fraud_score__gt=0).count(),
                "high_risk": Payment.objects.filter(fraud_score__gt=80).count(),
                "frozen_wallets": Wallet.objects.filter(frozen=True).count(),
            },
            "compliance": {
                "unprocessed_events": EventLog.objects.filter(processed=False).count(),
                "backup_status": BackupService.create_backup("postgres").status if hasattr(BackupService, 'create_backup') else "unknown",
            },
        }

    @staticmethod
    def _get_investor_data() -> Dict[str, Any]:
        """Fetch investor-specific stats."""
        total_wallets = Wallet.objects.filter(is_active=True).count()
        total_balance = Wallet.objects.aggregate(
            total=__import__("django.db.models", fromlist=["Sum"]).Sum("balance")
        )["total"] or 0

        reserve = CreditReserve.objects.first()

        # Monthly growth
        last_month = timezone.now() - timedelta(days=30)
        new_users = User.objects.filter(date_joined__gte=last_month).count()

        return {
            "platform": {
                "total_users": User.objects.count(),
                "active_users": User.objects.filter(is_active=True).count(),
                "new_users_last_month": new_users,
                "user_growth_rate": (new_users / max(User.objects.count() - new_users, 1)) * 100,
            },
            "financial": {
                "total_wallets": total_wallets,
                "total_volume": str(total_balance),
                "reserve_status": {
                    "currency": reserve.currency if reserve else "USD",
                    "total_reserve": str(reserve.total_reserve) if reserve else "0",
                    "total_minted": str(reserve.total_credits_minted) if reserve else "0",
                    "total_burned": str(reserve.total_credits_burned) if reserve else "0",
                },
                "monthly_volume": str(Payment.objects.filter(
                    status="completed", created_at__gte=last_month
                ).aggregate(
                    total=__import__("django.db.models", fromlist=["Sum"]).Sum("amount")
                )["total"] or 0),
            },
            "skills": {
                "total_skills": Skill.objects.count(),
                "published": Skill.objects.filter(lifecycle="production").count(),
                "total_executions": SkillExecution.objects.filter(status="completed").count(),
            },
        }

    @staticmethod
    def _get_widgets_for_type(dashboard_type: str, user_id: str) -> List[Dict[str, Any]]:
        """Get configured widgets for dashboard type."""
        from way_user.models import UserDashboardConfig, UserWidgetConfig

        # Try to get user's saved config
        try:
            config = UserDashboardConfig.objects.get(
                user_id=user_id, dashboard_type=dashboard_type, is_active=True
            )
            if config.layout and config.layout.get("widgets"):
                return config.layout["widgets"]
        except UserDashboardConfig.DoesNotExist:
            pass

        # Return default widgets
        defaults = {
            "user": [
                {"id": "wallet_summary", "name": "Wallet", "x": 0, "y": 0, "w": 3, "h": 2, "component": "WalletWidget"},
                {"id": "credits_summary", "name": "Credits", "x": 3, "y": 0, "w": 3, "h": 2, "component": "CreditsWidget"},
                {"id": "skills_summary", "name": "My Skills", "x": 6, "y": 0, "w": 3, "h": 2, "component": "SkillsWidget"},
                {"id": "notifications_summary", "name": "Notifications", "x": 9, "y": 0, "w": 3, "h": 2, "component": "NotificationsWidget"},
                {"id": "recent_activity", "name": "Recent Activity", "x": 0, "y": 2, "w": 6, "h": 3, "component": "ActivityWidget"},
                {"id": "marketplace_preview", "name": "Marketplace", "x": 6, "y": 2, "w": 6, "h": 3, "component": "MarketplaceWidget"},
                {"id": "system_health", "name": "System Health", "x": 0, "y": 5, "w": 4, "h": 2, "component": "MonitoringWidget"},
                {"id": "execution_chart", "name": "Executions", "x": 4, "y": 5, "w": 4, "h": 2, "component": "AnalyticsWidget"},
                {"id": "quick_actions", "name": "Quick Actions", "x": 8, "y": 5, "w": 4, "h": 2, "component": "RuntimeWidget"},
            ],
            "developer": [
                {"id": "skills_published", "name": "Published Skills", "x": 0, "y": 0, "w": 4, "h": 2, "component": "SkillsWidget"},
                {"id": "skill_usage_chart", "name": "Skill Usage", "x": 4, "y": 0, "w": 4, "h": 2, "component": "AnalyticsWidget"},
                {"id": "revenue_chart", "name": "Revenue", "x": 8, "y": 0, "w": 4, "h": 2, "component": "WalletWidget"},
                {"id": "executions_table", "name": "Executions", "x": 0, "y": 2, "w": 6, "h": 3, "component": "ActivityWidget"},
                {"id": "reviews_table", "name": "Reviews", "x": 6, "y": 2, "w": 6, "h": 3, "component": "NotificationsWidget"},
                {"id": "provider_performance", "name": "Provider Performance", "x": 0, "y": 5, "w": 6, "h": 2, "component": "MonitoringWidget"},
                {"id": "skill_health", "name": "Skill Health", "x": 6, "y": 5, "w": 6, "h": 2, "component": "RuntimeWidget"},
            ],
            "admin": [
                {"id": "users_count", "name": "Total Users", "x": 0, "y": 0, "w": 3, "h": 2, "component": "MonitoringWidget"},
                {"id": "transactions_volume", "name": "Transactions", "x": 3, "y": 0, "w": 3, "h": 2, "component": "WalletWidget"},
                {"id": "skills_overview", "name": "Total Skills", "x": 6, "y": 0, "w": 3, "h": 2, "component": "SkillsWidget"},
                {"id": "providers_health", "name": "Providers Health", "x": 9, "y": 0, "w": 3, "h": 2, "component": "MonitoringWidget"},
                {"id": "audit_trail", "name": "Audit Trail", "x": 0, "y": 2, "w": 6, "h": 3, "component": "ActivityWidget"},
                {"id": "system_health", "name": "System Health", "x": 6, "y": 2, "w": 6, "h": 3, "component": "MonitoringWidget"},
                {"id": "fraud_alerts", "name": "Fraud Alerts", "x": 0, "y": 5, "w": 4, "h": 2, "component": "NotificationsWidget"},
                {"id": "admin_actions", "name": "Admin Actions", "x": 4, "y": 5, "w": 4, "h": 2, "component": "ActivityWidget"},
                {"id": "user_growth", "name": "User Growth", "x": 8, "y": 5, "w": 4, "h": 2, "component": "AnalyticsWidget"},
            ],
            "ops": [
                {"id": "provider_status", "name": "Provider Status", "x": 0, "y": 0, "w": 4, "h": 2, "component": "MonitoringWidget"},
                {"id": "system_metrics", "name": "System Metrics", "x": 4, "y": 0, "w": 4, "h": 2, "component": "AnalyticsWidget"},
                {"id": "cache_stats", "name": "Cache Stats", "x": 8, "y": 0, "w": 4, "h": 2, "component": "MonitoringWidget"},
                {"id": "event_queue", "name": "Event Queue", "x": 0, "y": 2, "w": 6, "h": 3, "component": "ActivityWidget"},
                {"id": "runtime_sessions", "name": "Runtime Sessions", "x": 6, "y": 2, "w": 6, "h": 3, "component": "RuntimeWidget"},
                {"id": "backup_status", "name": "Backup Status", "x": 0, "y": 5, "w": 4, "h": 2, "component": "MonitoringWidget"},
                {"id": "error_rates", "name": "Error Rates", "x": 4, "y": 5, "w": 4, "h": 2, "component": "AnalyticsWidget"},
                {"id": "quick_actions", "name": "Quick Actions", "x": 8, "y": 5, "w": 4, "h": 2, "component": "RuntimeWidget"},
            ],
            "auditor": [
                {"id": "audit_overview", "name": "Audit Overview", "x": 0, "y": 0, "w": 6, "h": 2, "component": "MonitoringWidget"},
                {"id": "fraud_summary", "name": "Fraud Summary", "x": 6, "y": 0, "w": 6, "h": 2, "component": "NotificationsWidget"},
                {"id": "audit_chain", "name": "Audit Chain", "x": 0, "y": 2, "w": 6, "h": 3, "component": "ActivityWidget"},
                {"id": "compliance_status", "name": "Compliance", "x": 6, "y": 2, "w": 6, "h": 3, "component": "MonitoringWidget"},
            ],
            "investor": [
                {"id": "platform_metrics", "name": "Platform Metrics", "x": 0, "y": 0, "w": 6, "h": 2, "component": "AnalyticsWidget"},
                {"id": "financial_overview", "name": "Financial Overview", "x": 6, "y": 0, "w": 6, "h": 2, "component": "WalletWidget"},
                {"id": "user_growth", "name": "User Growth", "x": 0, "y": 2, "w": 6, "h": 3, "component": "AnalyticsWidget"},
                {"id": "skill_ecosystem", "name": "Skill Ecosystem", "x": 6, "y": 2, "w": 6, "h": 3, "component": "SkillsWidget"},
            ],
        }

        return defaults.get(dashboard_type, defaults["user"])

    @staticmethod
    def save_layout(user_id: str, dashboard_type: str, layout: Dict[str, Any]) -> Dict[str, Any]:
        """Save dashboard layout configuration."""
        from way_user.models import UserDashboardConfig

        config, created = UserDashboardConfig.objects.update_or_create(
            user_id=user_id,
            dashboard_type=dashboard_type,
            defaults={
                "layout": layout,
                "is_active": True,
                "is_default": False,
            }
        )

        # Invalidate cache
        cache.delete(f"dashboard:v2:{user_id}:{dashboard_type}")

        logger.info("dashboard.layout_saved", 
                   user_id=user_id, type=dashboard_type, created=created)

        return {
            "success": True,
            "config_id": str(config.id),
            "created": created,
        }
