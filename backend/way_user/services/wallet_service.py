"""
WAY User Wallet Service - Enterprise Grade
Full integration with way_finance services
"""
from typing import Dict, Any, List, Optional
from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import structlog

from way_finance.models import Wallet, CreditReserve, CreditLedger, Payment, CreditTransfer, BillingReport
from way_finance.services import WalletService as FinanceWalletService, CreditService, PaymentService, BillingService
from way_infra.services import AuditService

logger = structlog.get_logger("way_user.wallet")


class WalletService:
    """Enterprise-grade wallet aggregation service."""

    @staticmethod
    def get_wallet(user_id: str) -> Dict[str, Any]:
        """Get complete wallet with all related data."""
        cache_key = f"wallet:v2:{user_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            wallet = Wallet.objects.get(user_id=user_id)
        except Wallet.DoesNotExist:
            return {"error": "No wallet found", "code": "WALLET_NOT_FOUND"}

        # Get balance from service
        balance_data = FinanceWalletService.get_balance(str(wallet.id))

        # Get monthly stats
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        monthly_tx = CreditLedger.objects.filter(
            wallet=wallet, created_at__gte=month_start
        )

        monthly_payments = Payment.objects.filter(
            wallet=wallet, created_at__gte=month_start
        )

        # Get credit reserve info
        reserve = CreditReserve.objects.filter(currency=wallet.currency).first()

        wallet_data = {
            "id": str(wallet.id),
            "balance": str(balance_data.get("balance", "0")),
            "reserved": str(balance_data.get("reserved", "0")),
            "available": str(balance_data.get("available", "0")),
            "currency": wallet.currency,
            "is_active": wallet.is_active,
            "frozen": wallet.frozen,
            "frozen_reason": wallet.frozen_reason if wallet.frozen else None,
            "frozen_at": wallet.frozen_at.isoformat() if wallet.frozen_at else None,
            "public_key": wallet.public_key[:30] + "..." if wallet.public_key else None,
            "last_transaction": wallet.last_transaction.isoformat() if wallet.last_transaction else None,
            "nonce": wallet.nonce,
            "reserve_rate": str(reserve.rate) if reserve else "100",
            "usd_equivalent": str(float(wallet.balance) / float(reserve.rate)) if reserve else "0",
            "monthly_stats": {
                "credits_spent": str(sum(float(t.amount) for t in monthly_tx if t.amount < 0)),
                "credits_received": str(sum(float(t.amount) for t in monthly_tx if t.amount > 0)),
                "deposits": str(sum(float(p.amount) for p in monthly_payments if p.direction == "deposit")),
                "withdrawals": str(sum(float(p.amount) for p in monthly_payments if p.direction == "withdraw")),
                "fees": str(sum(float(p.fee) for p in monthly_payments)),
            },
        }

        cache.set(cache_key, wallet_data, 60)
        return wallet_data

    @staticmethod
    def get_wallet_summary(user_id: str) -> Dict[str, Any]:
        """Get lightweight wallet summary."""
        wallet = WalletService.get_wallet(user_id)
        if "error" in wallet:
            return wallet
        return {
            "id": wallet["id"],
            "balance": wallet["balance"],
            "available": wallet["available"],
            "currency": wallet["currency"],
            "frozen": wallet["frozen"],
            "usd_equivalent": wallet.get("usd_equivalent", "0"),
        }

    @staticmethod
    def get_transactions(user_id: str, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """Get paginated wallet transactions."""
        try:
            wallet = Wallet.objects.get(user_id=user_id)
        except Wallet.DoesNotExist:
            return {"error": "No wallet found", "items": []}

        transactions = CreditLedger.objects.filter(
            wallet=wallet
        ).select_related("wallet").order_by("-created_at")[offset:offset + limit]

        total = CreditLedger.objects.filter(wallet=wallet).count()

        return {
            "items": [{
                "id": str(t.id),
                "type": t.tx_type,
                "amount": str(t.amount),
                "balance_after": str(t.balance_after),
                "description": t.description,
                "reference_id": str(t.reference_id) if t.reference_id else None,
                "nonce": t.nonce,
                "current_hash": t.current_hash[:20] + "..." if t.current_hash else None,
                "created_at": t.created_at.isoformat(),
            } for t in transactions],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        }

    @staticmethod
    def get_payments(user_id: str, limit: int = 20, status: str = None) -> Dict[str, Any]:
        """Get paginated payments with optional filtering."""
        try:
            wallet = Wallet.objects.get(user_id=user_id)
        except Wallet.DoesNotExist:
            return {"error": "No wallet found", "items": []}

        qs = Payment.objects.filter(wallet=wallet)
        if status:
            qs = qs.filter(status=status)

        payments = qs.order_by("-created_at")[:limit]
        total = qs.count()

        return {
            "items": [{
                "id": str(p.id),
                "provider": p.provider,
                "direction": p.direction,
                "amount": str(p.amount),
                "currency": p.currency,
                "credits_amount": str(p.credits_amount) if p.credits_amount else None,
                "status": p.status,
                "fee": str(p.fee),
                "fraud_score": p.fraud_score,
                "fraud_flags": p.fraud_flags,
                "processed_at": p.processed_at.isoformat() if p.processed_at else None,
                "provider_tx_id": p.provider_tx_id,
                "created_at": p.created_at.isoformat(),
            } for p in payments],
            "total": total,
            "limit": limit,
        }

    @staticmethod
    def get_transfers(user_id: str, limit: int = 20) -> Dict[str, Any]:
        """Get credit transfers."""
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
                "amount": str(t.amount),
                "status": t.status,
                "description": t.description,
                "created_at": t.created_at.isoformat(),
            } for t in sent],
            "received": [{
                "id": str(t.id),
                "from_wallet_id": str(t.from_wallet.id),
                "amount": str(t.amount),
                "status": t.status,
                "description": t.description,
                "created_at": t.created_at.isoformat(),
            } for t in received],
        }

    @staticmethod
    def get_billing_reports(user_id: str, year: int = None, month: int = None) -> Dict[str, Any]:
        """Get billing reports."""
        try:
            wallet = Wallet.objects.get(user_id=user_id)
        except Wallet.DoesNotExist:
            return {"error": "No wallet found", "items": []}

        qs = BillingReport.objects.filter(wallet=wallet).order_by("-period_start")

        if year and month:
            qs = qs.filter(period_start__year=year, period_start__month=month)

        reports = qs[:12]  # Last 12 months

        return {
            "items": [{
                "id": str(r.id),
                "period_start": r.period_start.isoformat(),
                "period_end": r.period_end.isoformat(),
                "total_deposits": str(r.total_deposits),
                "total_withdrawals": str(r.total_withdrawals),
                "total_fees": str(r.total_fees),
                "total_skill_usage": str(r.total_skill_usage),
                "provider_costs": r.provider_costs,
                "generated_at": r.generated_at.isoformat() if r.generated_at else None,
            } for r in reports],
        }
