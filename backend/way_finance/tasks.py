"""WAY Finance Tasks"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import structlog
from .models import Payment, Wallet, BillingReport
from .services import BillingService

logger = structlog.get_logger("way.finance.tasks")

@shared_task
def process_pending():
    """Process pending payments."""
    pending = Payment.objects.filter(status="pending", created_at__lt=timezone.now() - timedelta(minutes=30))
    count = pending.update(status="failed")
    logger.info("payments.expired", count=count)
    return count

@shared_task
def generate_monthly_billing():
    """Generate monthly billing for all wallets."""
    now = timezone.now()
    wallets = Wallet.objects.filter(is_active=True)
    count = 0
    for wallet in wallets:
        try:
            BillingService.generate_report(str(wallet.id), now.year, now.month)
            count += 1
        except Exception as e:
            logger.error("billing.failed", wallet_id=str(wallet.id), error=str(e))
    logger.info("billing.generated", count=count)
    return count

@shared_task
def audit_reserve():
    """Audit credit reserve backing."""
    from .models import CreditReserve
    from .services import CreditService
    reserve = CreditService.get_reserve("USD")
    total_minted = reserve.total_credits_minted
    total_burned = reserve.total_credits_burned
    total_in_circulation = total_minted - total_burned
    # Sum all wallet balances
    from django.db.models import Sum
    total_wallets = Wallet.objects.aggregate(Sum("balance"))["balance__sum"] or 0
    discrepancy = total_in_circulation - total_wallets
    logger.info("reserve.audit", reserve=str(reserve.total_reserve), minted=str(total_minted), burned=str(total_burned), circulation=str(total_in_circulation), wallets=str(total_wallets), discrepancy=str(discrepancy))
    return {"discrepancy": str(discrepancy), "valid": discrepancy == 0}
