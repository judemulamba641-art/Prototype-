"""WAY Identity Views"""
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
import structlog

from .models import Device, Permission, RefreshToken, Group, GroupMembership
from .serializers import (
    UserSerializer, UserCreateSerializer, DeviceSerializer, PermissionSerializer,
    GroupSerializer, GroupMembershipSerializer, LoginSerializer, WalletAuthSerializer, TokenResponseSerializer
)
from .auth import JWTService, DeviceService, WalletAuthService, PermissionService
from way_infra.permissions import IsAdminOrReadOnly, IsOwnerOrAdmin

User = get_user_model()
logger = structlog.get_logger("way.identity")


class AuthViewSet(viewsets.ViewSet):
    """Authentication endpoints."""
    permission_classes = [AllowAny]

    @action(detail=False, methods=["post"])
    def register(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        logger.info("auth.registered", user_id=str(user.id), email=user.email)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def login(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            user = User.objects.get(email=data["email"], is_active=True)
        except User.DoesNotExist:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        if user.is_locked:
            return Response({"error": "Account locked"}, status=status.HTTP_403_FORBIDDEN)

        if not user.check_password(data["password"]):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.lock()
            user.save(update_fields=["failed_login_attempts"])
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        # Reset failed attempts
        user.failed_login_attempts = 0
        user.last_login = __import__('django.utils.timezone', fromlist=['now']).now()
        user.save(update_fields=["failed_login_attempts", "last_login"])

        # Register device if provided
        device = None
        if data.get("device_fingerprint"):
            device = DeviceService.register_device(
                user, data["device_fingerprint"], data.get("device_name", "Unknown"),
                data.get("device_type", "web"), request.META.get("REMOTE_ADDR"),
                request.META.get("HTTP_USER_AGENT", "")
            )

        access_token, refresh_token = JWTService.generate_tokens(user, device)
        logger.info("auth.login", user_id=str(user.id), device_id=str(device.id) if device else None)

        return Response({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": 900,
            "token_type": "Bearer",
            "user": UserSerializer(user).data,
        })

    @action(detail=False, methods=["post"])
    def wallet_login(self, request):
        serializer = WalletAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = WalletAuthService.authenticate_wallet(
            data["wallet_address"], data["signature"], data["message"], data["public_key"]
        )
        if not user:
            return Response({"error": "Invalid wallet signature"}, status=status.HTTP_401_UNAUTHORIZED)

        access_token, refresh_token = JWTService.generate_tokens(user)
        return Response({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": 900,
            "token_type": "Bearer",
            "user": UserSerializer(user).data,
        })

    @action(detail=False, methods=["post"])
    def refresh(self, request):
        refresh_token = request.data.get("refresh_token")
        if not refresh_token:
            return Response({"error": "Refresh token required"}, status=status.HTTP_400_BAD_REQUEST)

        access_token = JWTService.refresh_access_token(refresh_token)
        if not access_token:
            return Response({"error": "Invalid or expired refresh token"}, status=status.HTTP_401_UNAUTHORIZED)

        return Response({"access_token": access_token, "expires_in": 900, "token_type": "Bearer"})

    @action(detail=False, methods=["post"])
    def logout(self, request):
        refresh_token = request.data.get("refresh_token")
        if refresh_token:
            import hashlib
            token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
            JWTService.revoke_token(token_hash)
        return Response({"success": True})


class UserViewSet(viewsets.ModelViewSet):
    """User management."""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return User.objects.all()
        return User.objects.filter(id=self.request.user.id)

    def get_object(self):
        pk = self.kwargs.get("pk")
        if pk == "me" or pk == str(self.request.user.id):
            return self.request.user
        return super().get_object()

    @action(detail=True, methods=["post"])
    def change_password(self, request, pk=None):
        user = self.get_object()
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")

        if not user.check_password(old_password):
            return Response({"error": "Invalid current password"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.password_changed_at = __import__('django.utils.timezone', fromlist=['now']).now()
        user.save(update_fields=["password", "password_changed_at"])
        return Response({"success": True})

    @action(detail=True, methods=["post"])
    def enable_2fa(self, request, pk=None):
        user = self.get_object()
        # Generate TOTP secret
        import pyotp
        secret = pyotp.random_base32()
        user.two_factor_secret = secret
        user.two_factor_enabled = True
        user.save(update_fields=["two_factor_secret", "two_factor_enabled"])
        # Return QR code URI
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(user.email, issuer_name="WAY")
        return Response({"secret": secret, "qr_uri": uri})


class DeviceViewSet(viewsets.ModelViewSet):
    """Device management."""
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Device.objects.filter(user=self.request.user)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        device = self.get_object()
        trust_level = request.data.get("trust_level", "verified")
        success = DeviceService.approve_device(str(device.id), trust_level)
        return Response({"success": success})

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        device = self.get_object()
        device.is_approved = False
        device.trust_level = "untrusted"
        device.save(update_fields=["is_approved", "trust_level"])
        # Revoke all tokens for this device
        RefreshToken.objects.filter(device=device, revoked=False).update(revoked=True)
        return Response({"success": True})


class PermissionViewSet(viewsets.ModelViewSet):
    """Permission management."""
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Permission.objects.all()
        return Permission.objects.filter(user=self.request.user)

    @action(detail=False, methods=["post"])
    def grant(self, request):
        user_id = request.data.get("user_id", str(request.user.id))
        scope = request.data.get("scope")
        permission_type = request.data.get("permission_type")
        target_id = request.data.get("target_id")
        expires = request.data.get("expires_minutes")

        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        perm = PermissionService.grant_permission(target_user, scope, permission_type, target_id, expires)
        return Response(PermissionSerializer(perm).data)

    @action(detail=False, methods=["post"])
    def revoke(self, request):
        user_id = request.data.get("user_id", str(request.user.id))
        scope = request.data.get("scope")
        permission_type = request.data.get("permission_type")
        target_id = request.data.get("target_id")

        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        success = PermissionService.revoke_permission(target_user, scope, permission_type, target_id)
        return Response({"success": success})

    @action(detail=False, methods=["get"])
    def check(self, request):
        scope = request.query_params.get("scope")
        permission_type = request.query_params.get("permission_type")
        target_id = request.query_params.get("target_id")

        has_perm = PermissionService.check_permission(request.user, scope, permission_type, target_id)
        return Response({"has_permission": has_perm, "scope": scope, "permission_type": permission_type})


class GroupViewSet(viewsets.ModelViewSet):
    """Group management."""
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def add_member(self, request, pk=None):
        group = self.get_object()
        user_id = request.data.get("user_id")
        role = request.data.get("role", "member")

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        if group.owner != request.user and not request.user.is_staff:
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        membership, created = GroupMembership.objects.get_or_create(
            group=group, user=user, defaults={"role": role}
        )
        if not created:
            membership.role = role
            membership.save(update_fields=["role"])

        return Response(GroupMembershipSerializer(membership).data)

    @action(detail=True, methods=["post"])
    def remove_member(self, request, pk=None):
        group = self.get_object()
        user_id = request.data.get("user_id")

        if group.owner != request.user and not request.user.is_staff:
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        GroupMembership.objects.filter(group=group, user_id=user_id).delete()
        return Response({"success": True})
