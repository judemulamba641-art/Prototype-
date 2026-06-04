"""WAY Finance Views"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction, models, models
from decimal import Decimal

from .models import Wallet, CreditLedger, Payment, CreditTransfer, BillingReport, CreditReserve
from .serializers import (
    WalletSerializer, WalletCreateSerializer, CreditLedgerSerializer, PaymentSerializer,
    PaymentCreateSerializer, CreditTransferSerializer, TransferCreateSerializer,
    BillingReportSerializer, ReserveSerializer, WebhookSerializer
)
from .services import WalletService, CreditService, PaymentService, BillingService
from way_infra.permissions import IsAdminOrReadOnly, IsOwner


class WalletViewSet(viewsets.ModelViewSet):
    """Wallet management."""
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Wallet.objects.all()
        return Wallet.objects.filter(user_id=self.request.user.id)

    def create(self, request):
        serializer = WalletCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wallet = WalletService.create_wallet(
            str(serializer.validated_data["user_id"]),
            serializer.validated_data.get("public_key", ""),
            serializer.validated_data.get("private_key_encrypted", "")
        )
        return Response(WalletSerializer(wallet).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def balance(self, request, pk=None):
        wallet = self.get_object()
        balance = WalletService.get_balance(str(wallet.id))
        return Response(balance)

    @action(detail=True, methods=["post"])
    def freeze(self, request, pk=None):
        wallet = self.get_object()
        reason = request.data.get("reason", "manual")
        success = WalletService.freeze_wallet(str(wallet.id), reason)
        return Response({"success": success})

    @action(detail=True, methods=["post"])
    def unfreeze(self, request, pk=None):
        wallet = self.get_object()
        success = WalletService.unfreeze_wallet(str(wallet.id))
        return Response({"success": success})


class CreditLedgerViewSet(viewsets.ReadOnlyModelViewSet):
    """Credit ledger (immutable)."""
    queryset = CreditLedger.objects.all()
    serializer_class = CreditLedgerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return CreditLedger.objects.all()
        wallet = Wallet.objects.filter(user_id=self.request.user.id).first()
        if wallet:
            return CreditLedger.objects.filter(wallet=wallet)
        return CreditLedger.objects.none()


class PaymentViewSet(viewsets.ModelViewSet):
    """Payment management."""
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Payment.objects.all()
        wallet = Wallet.objects.filter(user_id=self.request.user.id).first()
        if wallet:
            return Payment.objects.filter(wallet=wallet)
        return Payment.objects.none()

    def create(self, request):
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = PaymentService.create_payment(
            str(serializer.validated_data["wallet_id"]),
            serializer.validated_data["provider"],
            serializer.validated_data["direction"],
            serializer.validated_data["amount"],
            serializer.validated_data.get("currency", "USD")
        )
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def webhook(self, request):
        """Process payment webhooks."""
        serializer = WebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        success = PaymentService.process_webhook(str(data["payment_id"]), {
            "transaction_id": data.get("transaction_id", ""),
            "status": data["status"],
            "error": data.get("error", ""),
            **data.get("metadata", {})
        })
        return Response({"success": success})


class TransferViewSet(viewsets.ModelViewSet):
    """Credit transfers."""
    queryset = CreditTransfer.objects.all()
    serializer_class = CreditTransferSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return CreditTransfer.objects.all()
        wallet = Wallet.objects.filter(user_id=self.request.user.id).first()
        if wallet:
            return CreditTransfer.objects.filter(models.Q(from_wallet=wallet) | models.Q(to_wallet=wallet))
        return CreditTransfer.objects.none()

    def create(self, request):
        serializer = TransferCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            transfer = CreditService.transfer_credits(
                str(data["from_wallet_id"]),
                str(data["to_wallet_id"]),
                data["amount"],
                data["signature"],
                data.get("description", "")
            )
            return Response(CreditTransferSerializer(transfer).data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BillingViewSet(viewsets.ReadOnlyModelViewSet):
    """Billing reports."""
    queryset = BillingReport.objects.all()
    serializer_class = BillingReportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return BillingReport.objects.all()
        wallet = Wallet.objects.filter(user_id=self.request.user.id).first()
        if wallet:
            return BillingReport.objects.filter(wallet=wallet)
        return BillingReport.objects.none()

    @action(detail=False, methods=["post"])
    def generate(self, request):
        wallet = Wallet.objects.filter(user_id=request.user.id).first()
        if not wallet:
            return Response({"error": "No wallet found"}, status=status.HTTP_404_NOT_FOUND)
        year = request.data.get("year", __import__('django.utils.timezone', fromlist=['now']).now().year)
        month = request.data.get("month", __import__('django.utils.timezone', fromlist=['now']).now().month)
        report = BillingService.generate_report(str(wallet.id), year, month)
        return Response(BillingReportSerializer(report).data)


class ReserveViewSet(viewsets.ReadOnlyModelViewSet):
    """Credit reserve (admin only)."""
    queryset = CreditReserve.objects.all()
    serializer_class = ReserveSerializer
    permission_classes = [IsAdminOrReadOnly]
