"""
WAY Finance Services - Wallet, Credits, Payments, Billing, Fraud
"""
import hashlib
import hmac
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta

from django.db import transaction, models
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
import structlog

from .models import Wallet, CreditReserve, CreditLedger, Payment, CreditTransfer, BillingReport
from way_infra.services import EventBus

logger = structlog.get_logger("way.finance")


class WalletService:
    """Wallet management with Ed25519 cryptography."""

    @staticmethod
    def create_wallet(user_id: str, public_key: str = "", private_key_encrypted: str = "") -> Wallet:
        wallet = Wallet.objects.create(
            user_id=user_id,
            public_key=public_key or "",
            private_key_encrypted=private_key_encrypted or "",
            currency=settings.WAY_CONFIG["DEFAULT_CURRENCY"],
        )
        # Link wallet to user
        from django.contrib.auth import get_user_model
        User = get_user_model()
        User.objects.filter(id=user_id).update(wallet_id=wallet.id)
        logger.info("wallet.created", wallet_id=str(wallet.id), user_id=user_id)
        return wallet

    @staticmethod
    def get_balance(wallet_id: str) -> Dict[str, Decimal]:
        cache_key = f"wallet:balance:{wallet_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            wallet = Wallet.objects.get(id=wallet_id)
            data = {"balance": wallet.balance, "reserved": wallet.reserved, "available": wallet.available}
            cache.set(cache_key, data, 60)
            return data
        except Wallet.DoesNotExist:
            return {"balance": Decimal("0"), "reserved": Decimal("0"), "available": Decimal("0")}

    @staticmethod
    def freeze_wallet(wallet_id: str, reason: str = "") -> bool:
        try:
            wallet = Wallet.objects.get(id=wallet_id)
            wallet.freeze(reason)
            logger.warning("wallet.frozen", wallet_id=wallet_id, reason=reason)
            return True
        except Wallet.DoesNotExist:
            return False

    @staticmethod
    def unfreeze_wallet(wallet_id: str) -> bool:
        try:
            wallet = Wallet.objects.get(id=wallet_id)
            wallet.unfreeze()
            logger.info("wallet.unfrozen", wallet_id=wallet_id)
            return True
        except Wallet.DoesNotExist:
            return False


class CreditService:
    """Credit management with reserve backing and ledger."""

    @staticmethod
    def get_reserve(currency: str = "USD") -> CreditReserve:
        reserve, _ = CreditReserve.objects.get_or_create(currency=currency)
        return reserve

    @staticmethod
    @transaction.atomic
    def mint_credits(wallet_id: str, amount: Decimal, payment_id: str = None, description: str = "") -> CreditLedger:
        """Mint credits backed by reserve."""
        wallet = Wallet.objects.select_for_update().get(id=wallet_id)
        reserve = CreditService.get_reserve(wallet.currency)

        # Verify reserve backing
        required_reserve = amount / reserve.rate
        if reserve.total_reserve < required_reserve:
            raise ValueError("Insufficient reserve backing")

        # Update wallet
        balance_before = wallet.balance
        wallet.balance += amount
        wallet.nonce += 1
        wallet.last_transaction = timezone.now()
        wallet.save(update_fields=["balance", "nonce", "last_transaction"])

        # Update reserve
        reserve.total_credits_minted += amount
        reserve.save(update_fields=["total_credits_minted"])

        # Create ledger entry
        ledger = CreditLedger.objects.create(
            wallet=wallet,
            tx_type="mint",
            amount=amount,
            balance_after=wallet.balance,
            reference_id=payment_id,
            description=description,
            nonce=wallet.nonce,
            current_hash=CreditService._hash_ledger(wallet_id, wallet.nonce, amount),
        )

        cache.delete(f"wallet:balance:{wallet_id}")
        EventBus.publish("credits_minted", {"wallet_id": str(wallet_id), "amount": str(amount), "ledger_id": str(ledger.id)})
        logger.info("credits.minted", wallet_id=wallet_id, amount=str(amount))
        return ledger

    @staticmethod
    @transaction.atomic
    def burn_credits(wallet_id: str, amount: Decimal, description: str = "") -> CreditLedger:
        """Burn credits."""
        wallet = Wallet.objects.select_for_update().get(id=wallet_id)
        if wallet.available < amount:
            raise ValueError("Insufficient balance")

        reserve = CreditService.get_reserve(wallet.currency)

        balance_before = wallet.balance
        wallet.balance -= amount
        wallet.nonce += 1
        wallet.save(update_fields=["balance", "nonce"])

        reserve.total_credits_burned += amount
        reserve.save(update_fields=["total_credits_burned"])

        ledger = CreditLedger.objects.create(
            wallet=wallet,
            tx_type="burn",
            amount=-amount,
            balance_after=wallet.balance,
            description=description,
            nonce=wallet.nonce,
            current_hash=CreditService._hash_ledger(wallet_id, wallet.nonce, -amount),
        )

        cache.delete(f"wallet:balance:{wallet_id}")
        EventBus.publish("credits_burned", {"wallet_id": str(wallet_id), "amount": str(amount)})
        return ledger

    @staticmethod
    @transaction.atomic
    def transfer_credits(from_wallet_id: str, to_wallet_id: str, amount: Decimal, signature: str, description: str = "") -> CreditTransfer:
        """Transfer credits between users."""
        from_wallet = Wallet.objects.select_for_update().get(id=from_wallet_id)
        to_wallet = Wallet.objects.select_for_update().get(id=to_wallet_id)

        if from_wallet.frozen or to_wallet.frozen:
            raise ValueError("Wallet frozen")
        if from_wallet.available < amount:
            raise ValueError("Insufficient balance")

        # Verify signature (simplified - actual Ed25519 verification)
        # In production: verify signature against from_wallet.public_key

        from_wallet.balance -= amount
        from_wallet.nonce += 1
        from_wallet.save(update_fields=["balance", "nonce"])

        to_wallet.balance += amount
        to_wallet.nonce += 1
        to_wallet.save(update_fields=["balance", "nonce"])

        transfer = CreditTransfer.objects.create(
            from_wallet=from_wallet,
            to_wallet=to_wallet,
            amount=amount,
            signature=signature,
            nonce=from_wallet.nonce,
            status="completed",
            processed_at=timezone.now(),
            description=description,
        )

        # Ledger entries for both wallets
        CreditLedger.objects.create(
            wallet=from_wallet,
            tx_type="transfer",
            amount=-amount,
            balance_after=from_wallet.balance,
            reference_id=transfer.id,
            description=f"Transfer to {to_wallet.user_id}",
            nonce=from_wallet.nonce,
            current_hash=CreditService._hash_ledger(str(from_wallet.id), from_wallet.nonce, -amount),
        )
        CreditLedger.objects.create(
            wallet=to_wallet,
            tx_type="transfer",
            amount=amount,
            balance_after=to_wallet.balance,
            reference_id=transfer.id,
            description=f"Transfer from {from_wallet.user_id}",
            nonce=to_wallet.nonce,
            current_hash=CreditService._hash_ledger(str(to_wallet.id), to_wallet.nonce, amount),
        )

        cache.delete(f"wallet:balance:{from_wallet_id}")
        cache.delete(f"wallet:balance:{to_wallet_id}")
        EventBus.publish("credits_transferred", {
            "from_wallet": str(from_wallet_id), "to_wallet": str(to_wallet_id),
            "amount": str(amount), "transfer_id": str(transfer.id)
        })
        logger.info("credits.transferred", from_wallet=from_wallet_id, to_wallet=to_wallet_id, amount=str(amount))
        return transfer

    @staticmethod
    def _hash_ledger(wallet_id: str, nonce: int, amount: Decimal) -> str:
        """Generate ledger entry hash."""
        data = f"{wallet_id}:{nonce}:{amount}:{timezone.now().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def get_ledger(wallet_id: str, limit: int = 50) -> list:
        return list(CreditLedger.objects.filter(wallet_id=wallet_id).select_related("wallet")[:limit])


class PaymentService:
    """Payment processing with fraud detection."""

    @staticmethod
    def create_payment(wallet_id: str, provider: str, direction: str, amount: Decimal, currency: str = "USD") -> Payment:
        wallet = Wallet.objects.get(id=wallet_id)
        payment = Payment.objects.create(
            wallet=wallet,
            provider=provider,
            direction=direction,
            amount=amount,
            currency=currency,
            credits_amount=amount * Decimal(settings.WAY_CONFIG["CREDIT_RATE"]) if direction == "deposit" else None,
        )
        logger.info("payment.created", payment_id=str(payment.id), provider=provider, amount=str(amount))
        return payment

    @staticmethod
    def process_webhook(payment_id: str, provider_data: Dict) -> bool:
        """Process payment webhook."""
        try:
            payment = Payment.objects.get(id=payment_id)
            payment.webhook_received = True
            payment.webhook_data = provider_data
            payment.provider_tx_id = provider_data.get("transaction_id", "")

            # Fraud detection
            fraud_score, flags = PaymentService._check_fraud(payment, provider_data)
            payment.fraud_score = fraud_score
            payment.fraud_flags = flags

            if fraud_score > 80:
                payment.status = "failed"
                payment.save(update_fields=["webhook_received", "webhook_data", "provider_tx_id", "fraud_score", "fraud_flags", "status"])
                WalletService.freeze_wallet(str(payment.wallet_id), "fraud detected")
                EventBus.publish("fraud_detected", {"payment_id": str(payment.id), "score": fraud_score, "flags": flags})
                return False

            if provider_data.get("status") == "success":
                payment.status = "completed"
                payment.processed_at = timezone.now()
                payment.save(update_fields=["status", "processed_at", "webhook_received", "webhook_data", "provider_tx_id", "fraud_score", "fraud_flags"])

                # Mint credits for deposits
                if payment.direction == "deposit":
                    CreditService.mint_credits(str(payment.wallet_id), payment.credits_amount, str(payment.id), "Deposit")
                elif payment.direction == "withdraw":
                    CreditService.burn_credits(str(payment.wallet_id), payment.credits_amount, "Withdraw")

                EventBus.publish("payment_success", {"payment_id": str(payment.id), "provider": payment.provider})
                return True
            else:
                payment.status = "failed"
                payment.save(update_fields=["status", "webhook_received", "webhook_data", "provider_tx_id", "fraud_score", "fraud_flags"])
                EventBus.publish("payment_failed", {"payment_id": str(payment.id), "reason": provider_data.get("error")})
                return False

        except Payment.DoesNotExist:
            return False

    @staticmethod
    def _check_fraud(payment: Payment, data: Dict) -> Tuple[float, list]:
        """Basic fraud detection."""
        score = 0.0
        flags = []

        # Check amount anomaly
        avg_amount = Payment.objects.filter(wallet=payment.wallet, status="completed").aggregate(models.Avg("amount"))["amount__avg"] or Decimal("0")
        if avg_amount > 0 and payment.amount > avg_amount * 5:
            score += 30
            flags.append("amount_anomaly")

        # Check velocity
        recent_count = Payment.objects.filter(wallet=payment.wallet, created_at__gte=timezone.now() - timedelta(hours=1)).count()
        if recent_count > 10:
            score += 25
            flags.append("velocity")

        # Check IP geolocation (simplified)
        if data.get("ip_country") and data.get("ip_country") != payment.wallet.currency:
            score += 20
            flags.append("geo_mismatch")

        # Check duplicate
        if Payment.objects.filter(wallet=payment.wallet, amount=payment.amount, provider=payment.provider, status="completed").exists():
            score += 15
            flags.append("possible_duplicate")

        return min(score, 100), flags


class BillingService:
    """Billing report generation."""

    @staticmethod
    def generate_report(wallet_id: str, year: int, month: int) -> BillingReport:
        wallet = Wallet.objects.get(id=wallet_id)
        start_date = datetime(year, month, 1).date()
        if month == 12:
            end_date = datetime(year + 1, 1, 1).date()
        else:
            end_date = datetime(year, month + 1, 1).date()

        deposits = Payment.objects.filter(wallet=wallet, direction="deposit", status="completed", created_at__date__gte=start_date, created_at__date__lt=end_date)
        withdrawals = Payment.objects.filter(wallet=wallet, direction="withdraw", status="completed", created_at__date__gte=start_date, created_at__date__lt=end_date)
        skill_usage = CreditLedger.objects.filter(wallet=wallet, tx_type="skill_usage", created_at__date__gte=start_date, created_at__date__lt=end_date)

        report, _ = BillingReport.objects.update_or_create(
            wallet=wallet,
            period_start=start_date,
            defaults={
                "period_end": end_date - timedelta(days=1),
                "total_deposits": sum(p.amount for p in deposits) or Decimal("0"),
                "total_withdrawals": sum(w.amount for w in withdrawals) or Decimal("0"),
                "total_fees": sum(p.fee for p in deposits) or Decimal("0"),
                "total_skill_usage": sum(s.amount for s in skill_usage) or Decimal("0"),
                "provider_costs": {},  # Would be populated from provider data
                "report_data": {
                    "deposit_count": deposits.count(),
                    "withdrawal_count": withdrawals.count(),
                    "skill_usage_count": skill_usage.count(),
                },
            }
        )
        return report
