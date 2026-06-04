"""WAY Operations Views"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from .models import Notification, AdminAction, CurrencyRate
from .serializers import NotificationSerializer, AdminActionSerializer, CurrencyRateSerializer, ConvertSerializer
from .services import NotificationService, AdminService, CurrencyService
from way_infra.permissions import IsAdminOrReadOnly


class NotificationViewSet(viewsets.ModelViewSet):
    """User notifications."""
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user_id=self.request.user.id)

    @action(detail=False, methods=["get"])
    def unread(self, request):
        notifications = NotificationService.get_unread(str(request.user.id))
        return Response(NotificationSerializer(notifications, many=True).data)

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        success = NotificationService.mark_read(pk)
        return Response({"success": success})

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        Notification.objects.filter(user_id=request.user.id, read=False).update(read=True, read_at=__import__("django.utils.timezone").now())
        return Response({"success": True})


class AdminActionViewSet(viewsets.ModelViewSet):
    """Admin actions log."""
    queryset = AdminAction.objects.all()
    serializer_class = AdminActionSerializer
    permission_classes = [IsAdminUser]

    @action(detail=True, methods=["post"])
    def revert(self, request, pk=None):
        success = AdminService.revert_action(pk)
        return Response({"success": success})


class CurrencyViewSet(viewsets.ModelViewSet):
    """Currency rates."""
    queryset = CurrencyRate.objects.all()
    serializer_class = CurrencyRateSerializer
    permission_classes = [IsAdminOrReadOnly]

    @action(detail=False, methods=["post"])
    def convert(self, request):
        serializer = ConvertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = CurrencyService.convert(data["amount"], data["from_currency"], data["to_currency"])
        return Response({
            "amount": data["amount"],
            "from": data["from_currency"],
            "to": data["to_currency"],
            "result": result,
            "rate": CurrencyService.get_rate(data["from_currency"], data["to_currency"]),
        })
