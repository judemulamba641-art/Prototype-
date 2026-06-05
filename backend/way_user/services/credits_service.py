"""
WAY User Credits Service - Enterprise Grade
Full integration with way_finance credit system
"""
from typing import Dict, Any, List
from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Count, Avg
import structlog

from way_finance.models import Wallet, CreditReserve, CreditLedger, CreditTransfer
from way_finance.services import CreditService as FinanceCreditService
from way_infra.services import AuditService

logger = structlog.get_logger("way_user.credits")


class CreditsService:
    """Enterprise-grade credits aggregation service."""

    @staticmethod
    def get_credits_summary(user_id: str) -> Dict[str, Any]:
        """Get comprehensive credits summary."""
        cache_key = f"credits:v2:{user_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            wallet = Wallet.objects.get(user_id=user_id)
        except Wallet.DoesNotExist:
            return {"error": "No wallet found", "code": "WALLET_NOT_FOUND"}

        reserve = CreditReserve.objects.filter(currency=wallet.currency).first()

        # Calculate stats
        now = timezone.now()
        today = now.date()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        # Daily stats
        daily_minted = CreditLedger.objects.filter(
            wallet=wallet, tx_type="mint", created_at__date=today
        ).aggregate(total=Sum("amount"))["total__sum"] or 0

        daily_burned = abs(CreditLedger.objects.filter(
            wallet=wallet, tx_type="burn", created_at__date=today
        ).aggregate(total=Sum("amount"))["total__sum"] or 0)

        # Weekly stats
        weekly_tx = CreditLedger.objects.filter(
            wallet=wallet, created_at__gte=week_ago
        )

        # Monthly stats
        monthly_tx = CreditLedger.objects.filter(
            wallet=wallet, created_at__gte=month_ago
        )

        # Top transaction types
        tx_types = CreditLedger.objects.filter(
            wallet=wallet
        ).values("tx_type").annotate(
            count=Count("id"),
            total=Sum("amount")
        ).order_by("-count")[:5]

        result = {
            "balance": str(wallet.balance),
            "available": str(wallet.available),
            "reserved": str(wallet.reserved),
            "currency": wallet.currency,
            "rate": str(reserve.rate) if reserve else "100",
            "usd_equivalent": str(float(wallet.balance) / float(reserve.rate)) if reserve else "0",
            "reserve": {
                "total_reserve": str(reserve.total_reserve) if reserve else "0",
                "total_minted": str(reserve.total_credits_minted) if reserve else "0",
                "total_burned": str(reserve.total_credits_burned) if reserve else "0",
                "currency": reserve.currency if reserve else wallet.currency,
            },
            "daily": {
                "minted": str(daily_minted),
                "burned": str(daily_burned),
                "net": str(daily_minted - daily_burned),
            },
            "weekly": {
                "transaction_count": weekly_tx.count(),
                "credits_spent": str(sum(float(t.amount) for t in weekly_tx if t.amount < 0)),
                "credits_earned": str(sum(float(t.amount) for t in weekly_tx if t.amount > 0)),
            },
            "monthly": {
                "transaction_count": monthly_tx.count(),
                "credits_spent": str(sum(float(t.amount) for t in monthly_tx if t.amount < 0)),
                "credits_earned": str(sum(float(t.amount) for t in monthly_tx if t.amount > 0)),
            },
            "transaction_types": [{
                "type": t["tx_type"],
                "count": t["count"],
                "total": str(t["total"]),
            } for t in tx_types],
        }

        cache.set(cache_key, result, 60)
        return result

    @staticmethod
    def get_ledger(user_id: str, limit: int = 50, offset: int = 0, 
                   tx_type: str = None) -> Dict[str, Any]:
        """Get paginated credit ledger with filtering."""
        try:
            wallet = Wallet.objects.get(user_id=user_id)
        except Wallet.DoesNotExist:
            return {"error": "No wallet found", "items": []}

        qs = CreditLedger.objects.filter(wallet=wallet)
        if tx_type:
            qs = qs.filter(tx_type=tx_type)

        total = qs.count()
        entries = qs.select_related("wallet").order_by("-created_at")[offset:offset + limit]

        return {
            "items": [{
                "id": str(e.id),
                "type": e.tx_type,
                "amount": str(e.amount),
                "balance_after": str(e.balance_after),
                "description": e.description,
                "reference_id": str(e.reference_id) if e.reference_id else None,
                "nonce": e.nonce,
                "current_hash": e.current_hash[:30] + "..." if e.current_hash else None,
                "previous_hash": e.previous_hash[:30] + "..." if e.previous_hash else None,
                "signature": e.signature[:30] + "..." if e.signature else None,
                "created_at": e.created_at.isoformat(),
            } for e in entries],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        }

    @staticmethod
    def get_reserve_status() -> Dict[str, Any]:
        """Get global reserve status with audit."""
        reserves = CreditReserve.objects.all()

        # Calculate total circulation
        total_minted = sum(r.total_credits_minted for r in reserves)
        total_burned = sum(r.total_credits_burned for r in reserves)
        total_circulation = total_minted - total_burned

        # Sum all wallet balances for verification
        total_wallets = Wallet.objects.aggregate(total=Sum("balance"))["total__sum"] or 0

        return {
            "reserves": [{
                "currency": r.currency,
                "total_reserve": str(r.total_reserve),
                "total_minted": str(r.total_credits_minted),
                "total_burned": str(r.total_credits_burned),
                "rate": str(r.rate),
                "last_audit": r.last_audit.isoformat() if r.last_audit else None,
                "audit_hash": r.audit_hash[:20] + "..." if r.audit_hash else None,
            } for r in reserves],
            "global": {
                "total_minted": str(total_minted),
                "total_burned": str(total_burned),
                "total_circulation": str(total_circulation),
                "total_in_wallets": str(total_wallets),
                "discrepancy": str(total_circulation - total_wallets),
                "is_valid": total_circulation == total_wallets,
            },
        }

    @staticmethod
    def get_transfer_history(user_id: str, limit: int = 50) -> Dict[str, Any]:
        """Get P2P transfer history."""
        try:
            wallet = Wallet.objects.get(user_id=user_id)
        except Wallet.DoesNotExist:
            return {"error": "No wallet found", "items": []}

        sent = CreditTransfer.objects.filter(from_wallet=wallet).order_by("-created_at")[:limit // 2]
        received = CreditTransfer.objects.filter(to_wallet=wallet).order_by("-created_at")[:limit // 2]

        return {
            "sent": [{
                "id": str(t.id),
                "to_wallet_id": str(t.to_wallet.id),
                "to_user_id": str(t.to_wallet.user_id),
                "amount": str(t.amount),
                "status": t.status,
                "signature": t.signature[:30] + "..." if t.signature else None,
                "description": t.description,
                "processed_at": t.processed_at.isoformat() if t.processed_at else None,
                "created_at": t.created_at.isoformat(),
            } for t in sent],
            "received": [{
                "id": str(t.id),
                "from_wallet_id": str(t.from_wallet.id),
                "from_user_id": str(t.from_wallet.user_id),
                "amount": str(t.amount),
                "status": t.status,
                "signature": t.signature[:30] + "..." if t.signature else None,
                "description": t.description,
                "processed_at": t.processed_at.isoformat() if t.processed_at else None,
                "created_at": t.created_at.isoformat(),
            } for t in received],
        }
