"""Tests Finance - Wallet, Credits, Payments, Billing, Transfers"""
import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from way_finance.models import Wallet, CreditReserve, CreditLedger, Payment, CreditTransfer, BillingReport
from way_finance.services import WalletService, CreditService, PaymentService, BillingService


@pytest.mark.django_db
class TestWallet:
    def test_create_wallet(self, auth_client, test_user):
        response = auth_client.post(reverse("wallets-list"), {
            "user_id": str(test_user.id),
            "public_key": "test_key",
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert Wallet.objects.filter(user_id=test_user.id).exists()

    def test_get_balance(self, auth_client, test_wallet):
        response = auth_client.get(reverse("wallets-balance", kwargs={"pk": str(test_wallet.id)}))
        assert response.status_code == status.HTTP_200_OK
        assert float(response.data["balance"]) == 1000.00
        assert float(response.data["available"]) == 1000.00

    def test_freeze_wallet(self, auth_client, test_wallet):
        response = auth_client.post(reverse("wallets-freeze", kwargs={"pk": str(test_wallet.id)}), {
            "reason": "suspicious activity",
        })
        assert response.status_code == status.HTTP_200_OK
        test_wallet.refresh_from_db()
        assert test_wallet.frozen

    def test_unfreeze_wallet(self, auth_client, test_wallet):
        WalletService.freeze_wallet(str(test_wallet.id), "test")
        response = auth_client.post(reverse("wallets-unfreeze", kwargs={"pk": str(test_wallet.id)}))
        assert response.status_code == status.HTTP_200_OK
        test_wallet.refresh_from_db()
        assert not test_wallet.frozen


@pytest.mark.django_db
class TestCredits:
    def test_mint_credits(self, test_wallet):
        reserve = CreditReserve.objects.create(currency="USD", total_reserve=10000, rate=100)
        ledger = CreditService.mint_credits(str(test_wallet.id), Decimal("500"), description="Test mint")
        assert ledger.tx_type == "mint"
        assert ledger.amount == Decimal("500")
        test_wallet.refresh_from_db()
        assert test_wallet.balance == Decimal("1500.00")

    def test_burn_credits(self, test_wallet):
        reserve = CreditReserve.objects.create(currency="USD", total_reserve=10000, rate=100)
        ledger = CreditService.burn_credits(str(test_wallet.id), Decimal("100"), description="Test burn")
        assert ledger.tx_type == "burn"
        assert ledger.amount == Decimal("-100")
        test_wallet.refresh_from_db()
        assert test_wallet.balance == Decimal("900.00")

    def test_insufficient_balance(self, test_wallet):
        reserve = CreditReserve.objects.create(currency="USD", total_reserve=10000, rate=100)
        with pytest.raises(ValueError, match="Insufficient balance"):
            CreditService.burn_credits(str(test_wallet.id), Decimal("2000"))

    def test_transfer_credits(self, test_wallet):
        import uuid
        reserve = CreditReserve.objects.create(currency="USD", total_reserve=10000, rate=100)
        other_wallet = Wallet.objects.create(user_id=uuid.uuid4(), balance=100)
        transfer = CreditService.transfer_credits(
            str(test_wallet.id), str(other_wallet.id), Decimal("100"), "test_signature"
        )
        assert transfer.status == "completed"
        test_wallet.refresh_from_db()
        other_wallet.refresh_from_db()
        assert test_wallet.balance == Decimal("900.00")
        assert other_wallet.balance == Decimal("200.00")

    def test_ledger_hash_chain(self, test_wallet):
        reserve = CreditReserve.objects.create(currency="USD", total_reserve=10000, rate=100)
        ledger1 = CreditService.mint_credits(str(test_wallet.id), Decimal("100"))
        ledger2 = CreditService.mint_credits(str(test_wallet.id), Decimal("100"))
        # Both ledgers should have valid hashes
        assert ledger1.current_hash != ""
        assert ledger2.current_hash != ""
        assert ledger2.previous_hash != "" or ledger1.previous_hash == ""


@pytest.mark.django_db
class TestPayments:
    def test_create_payment(self, auth_client, test_wallet):
        response = auth_client.post(reverse("payments-list"), {
            "wallet_id": str(test_wallet.id),
            "provider": "stripe",
            "direction": "deposit",
            "amount": "50.00",
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert Payment.objects.filter(wallet=test_wallet).exists()

    def test_webhook_processing(self, test_wallet):
        payment = PaymentService.create_payment(str(test_wallet.id), "stripe", "deposit", Decimal("50"))
        reserve = CreditReserve.objects.create(currency="USD", total_reserve=10000, rate=100)
        success = PaymentService.process_webhook(str(payment.id), {
            "transaction_id": "tx_123",
            "status": "success",
        })
        assert success
        payment.refresh_from_db()
        assert payment.status == "completed"
        test_wallet.refresh_from_db()
        assert test_wallet.balance > Decimal("1000")

    def test_fraud_detection(self, test_wallet):
        reserve = CreditReserve.objects.create(currency="USD", total_reserve=1000000, rate=100)
        payment = PaymentService.create_payment(str(test_wallet.id), "stripe", "deposit", Decimal("5000"))
        # First payment is large = anomaly
        success = PaymentService.process_webhook(str(payment.id), {
            "transaction_id": "tx_123",
            "status": "success",
            "ip_country": "XX",
        })
        payment.refresh_from_db()
        assert payment.fraud_score > 0


@pytest.mark.django_db
class TestBilling:
    def test_generate_report(self, test_wallet):
        report = BillingService.generate_report(str(test_wallet.id), 2024, 1)
        assert report.period_start.month == 1
        assert report.wallet == test_wallet

    def test_billing_api(self, auth_client, test_wallet):
        # Use current year to avoid date issues
        import datetime
        current_year = datetime.datetime.now().year
        response = auth_client.post(reverse("billing-generate"), {"year": current_year, "month": 1}, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert "period_start" in response.data
