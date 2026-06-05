"""
WAY User Analytics Service - Enterprise Grade
Comprehensive analytics aggregation
"""
from typing import Dict, Any, List
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Count, Avg, Min, Max
import structlog

from way_skills.models import Skill, SkillExecution, Provider
from way_finance.models import Wallet, CreditLedger, Payment, CreditReserve
from way_infra.models import TelemetryMetric, AuditLog, EventLog
from django.contrib.auth import get_user_model

logger = structlog.get_logger("way_user.analytics")


class AnalyticsService:
    """Enterprise-grade analytics aggregation service."""

    @staticmethod
    def get_user_activity(user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive user activity analytics."""
        start_date = timezone.now() - timedelta(days=days)

        # Executions
        executions = SkillExecution.objects.filter(
            user_id=user_id, created_at__gte=start_date
        )

        # Financial
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

        # Daily breakdown
        daily_stats = {}
        for i in range(days):
            day = timezone.now().date() - timedelta(days=i)
            day_executions = executions.filter(created_at__date=day)
            daily_stats[day.isoformat()] = {
                "executions": day_executions.count(),
                "credits_spent": str(sum(float(e.cost) for e in day_executions)),
                "successful": day_executions.filter(status="completed").count(),
                "failed": day_executions.filter(status="failed").count(),
            }

        return {
            "period_days": days,
            "period_start": start_date.isoformat(),
            "executions": {
                "total": executions.count(),
                "completed": executions.filter(status="completed").count(),
                "failed": executions.filter(status="failed").count(),
                "cancelled": executions.filter(status="cancelled").count(),
                "total_cost": str(sum(float(e.cost) for e in executions)),
                "avg_cost": str(sum(float(e.cost) for e in executions) / executions.count()) if executions.count() > 0 else "0",
                "avg_latency_ms": executions.aggregate(avg=Avg("latency_ms"))["avg__avg"] or 0,
                "avg_tokens": executions.aggregate(avg=Avg("tokens_used"))["avg__avg"] or 0,
                "cache_hit_rate": executions.filter(cache_hit=True).count() / executions.count() * 100 if executions.count() > 0 else 0,
            },
            "financial": {
                "transactions_count": len(transactions) if isinstance(transactions, list) else transactions.count(),
                "credits_spent": str(sum(float(t.amount) for t in (transactions if not isinstance(transactions, list) else []) if t.amount < 0)),
                "credits_received": str(sum(float(t.amount) for t in (transactions if not isinstance(transactions, list) else []) if t.amount > 0)),
                "payments_count": len(payments) if isinstance(payments, list) else payments.count(),
                "deposits": str(sum(float(p.amount) for p in (payments if not isinstance(payments, list) else []) if p.direction == "deposit")),
                "withdrawals": str(sum(float(p.amount) for p in (payments if not isinstance(payments, list) else []) if p.direction == "withdraw")),
                "fees": str(sum(float(p.fee) for p in (payments if not isinstance(payments, list) else []))),
            },
            "daily_breakdown": daily_stats,
            "top_skills": [{
                "skill_id": str(item["skill"]),
                "skill_name": Skill.objects.get(id=item["skill"]).name if item["skill"] else "Unknown",
                "execution_count": item["count"],
                "total_cost": str(item["total_cost"] or 0),
            } for item in executions.values("skill").annotate(
                count=Count("id"),
                total_cost=Sum("cost")
            ).order_by("-count")[:5]],
        }

    @staticmethod
    def get_global_stats() -> Dict[str, Any]:
        """Get global platform statistics."""
        User = get_user_model()
        now = timezone.now()
        today = now.date()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        # User stats
        users = User.objects

        # Skill stats
        skills = Skill.objects

        # Execution stats
        executions = SkillExecution.objects

        # Financial stats
        wallets = Wallet.objects
        payments = Payment.objects

        return {
            "generated_at": now.isoformat(),
            "users": {
                "total": users.count(),
                "active": users.filter(is_active=True).count(),
                "new_today": users.filter(date_joined__date=today).count(),
                "new_this_week": users.filter(date_joined__gte=week_ago).count(),
                "new_this_month": users.filter(date_joined__gte=month_ago).count(),
                "active_today": users.filter(last_login__date=today).count(),
                "active_this_week": users.filter(last_login__gte=week_ago).count(),
            },
            "skills": {
                "total": skills.count(),
                "published": skills.filter(lifecycle="production").count(),
                "draft": skills.filter(lifecycle="draft").count(),
                "pending_approval": skills.filter(lifecycle="review").count(),
                "suspended": skills.filter(lifecycle="suspended").count(),
                "by_type": {
                    skill_type: skills.filter(skill_type=skill_type).count()
                    for skill_type in skills.values_list("skill_type", flat=True).distinct()
                },
            },
            "executions": {
                "total": executions.count(),
                "completed": executions.filter(status="completed").count(),
                "failed": executions.filter(status="failed").count(),
                "today": executions.filter(created_at__date=today).count(),
                "this_week": executions.filter(created_at__gte=week_ago).count(),
                "this_month": executions.filter(created_at__gte=month_ago).count(),
                "total_revenue": str(executions.filter(status="completed").aggregate(
                    total=Sum("cost")
                )["total__sum"] or 0),
                "avg_latency": executions.filter(status="completed").aggregate(
                    avg=Avg("latency_ms")
                )["avg__avg"] or 0,
            },
            "financial": {
                "total_wallets": wallets.count(),
                "total_balance": str(wallets.aggregate(total=Sum("balance"))["total__sum"] or 0),
                "active_wallets": wallets.filter(is_active=True).count(),
                "frozen_wallets": wallets.filter(frozen=True).count(),
                "total_payments": payments.count(),
                "completed_payments": payments.filter(status="completed").count(),
                "total_volume": str(payments.filter(status="completed").aggregate(
                    total=Sum("amount")
                )["total__sum"] or 0),
                "volume_today": str(payments.filter(
                    status="completed", processed_at__date=today
                ).aggregate(total=Sum("amount"))["total__sum"] or 0),
            },
            "providers": {
                "total": Provider.objects.count(),
                "active": Provider.objects.filter(status="active").count(),
                "degraded": Provider.objects.filter(status="degraded").count(),
                "down": Provider.objects.filter(status="down").count(),
                "avg_latency": Provider.objects.filter(status="active").aggregate(
                    avg=Avg("latency_ms")
                )["avg__avg"] or 0,
                "avg_success_rate": Provider.objects.filter(status="active").aggregate(
                    avg=Avg("success_rate")
                )["avg__avg"] or 0,
            },
        }

    @staticmethod
    def get_search_history(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get user search history (placeholder - would need search model)."""
        # In production, this would query a SearchHistory model
        return []

    @staticmethod
    def get_user_growth(days: int = 30) -> List[Dict[str, Any]]:
        """Get user growth over time."""
        User = get_user_model()
        result = []

        for i in range(days - 1, -1, -1):
            date = timezone.now().date() - timedelta(days=i)
            result.append({
                "date": date.isoformat(),
                "new_users": User.objects.filter(date_joined__date=date).count(),
                "active_users": User.objects.filter(last_login__date=date).count(),
                "cumulative_users": User.objects.filter(date_joined__date__lte=date).count(),
            })

        return result

    @staticmethod
    def get_revenue_analytics(days: int = 30) -> Dict[str, Any]:
        """Get revenue analytics."""
        start_date = timezone.now() - timedelta(days=days)

        executions = SkillExecution.objects.filter(
            status="completed", created_at__gte=start_date
        )

        payments = Payment.objects.filter(
            status="completed", processed_at__gte=start_date
        )

        daily_revenue = []
        for i in range(days - 1, -1, -1):
            date = timezone.now().date() - timedelta(days=i)
            day_executions = executions.filter(created_at__date=date)
            day_payments = payments.filter(processed_at__date=date)

            daily_revenue.append({
                "date": date.isoformat(),
                "skill_revenue": str(sum(float(e.cost) for e in day_executions)),
                "payment_volume": str(sum(float(p.amount) for p in day_payments)),
                "payment_fees": str(sum(float(p.fee) for p in day_payments)),
            })

        return {
            "period_days": days,
            "total_skill_revenue": str(sum(float(e.cost) for e in executions)),
            "total_payment_volume": str(sum(float(p.amount) for p in payments)),
            "total_fees": str(sum(float(p.fee) for p in payments)),
            "daily_breakdown": daily_revenue,
            "by_provider": [{
                "provider": item["provider__name"] or "Unknown",
                "revenue": str(item["total"] or 0),
                "executions": item["count"],
            } for item in executions.values("provider__name").annotate(
                total=Sum("cost"), count=Count("id")
            ).order_by("-total")],
        }
