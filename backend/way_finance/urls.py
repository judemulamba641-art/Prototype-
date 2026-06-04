"""WAY Finance URLs"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WalletViewSet, CreditLedgerViewSet, PaymentViewSet, TransferViewSet, BillingViewSet, ReserveViewSet

router = DefaultRouter()
router.register(r"wallets", WalletViewSet, basename="wallets")
router.register(r"ledger", CreditLedgerViewSet, basename="ledger")
router.register(r"payments", PaymentViewSet, basename="payments")
router.register(r"transfers", TransferViewSet, basename="transfers")
router.register(r"billing", BillingViewSet, basename="billing")
router.register(r"reserve", ReserveViewSet, basename="reserve")

urlpatterns = [
    path("", include(router.urls)),
]
