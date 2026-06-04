"""
WAY Authentication - JWT, Device Trust, Biometric, Wallet Auth
"""
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple

import jwt
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import authentication, exceptions
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ed25519

from .models import Device, RefreshToken

User = get_user_model()


class JWTAuthentication(authentication.BaseAuthentication):
    """JWT authentication with device trust."""
    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = authentication.get_authorization_header(request).split()
        if not auth_header or auth_header[0].lower() != self.keyword.lower().encode():
            return None
        if len(auth_header) != 2:
            raise exceptions.AuthenticationFailed("Invalid token header")
        try:
            token = auth_header[1].decode("utf-8")
        except UnicodeError:
            raise exceptions.AuthenticationFailed("Invalid token encoding")

        return self.authenticate_credentials(token, request)

    def authenticate_credentials(self, token, request):
        try:
            payload = jwt.decode(token, settings.WAY_CONFIG["JWT_SECRET"], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed("Token expired")
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed("Invalid token")

        user_id = payload.get("user_id")
        if not user_id:
            raise exceptions.AuthenticationFailed("Invalid payload")

        try:
            user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed("User not found")

        if user.is_locked:
            raise exceptions.AuthenticationFailed("Account locked")

        # Device validation
        device_id = payload.get("device_id")
        if device_id:
            try:
                device = Device.objects.get(id=device_id, user=user, is_approved=True)
                request.device = device
            except Device.DoesNotExist:
                raise exceptions.AuthenticationFailed("Device not trusted")

        # Permission scope validation
        scope = payload.get("scope", "full")
        request.auth_scope = scope

        return (user, payload)


class JWTService:
    """JWT token generation and management."""

    @staticmethod
    def generate_tokens(user: User, device: Optional[Device] = None, scope: str = "full") -> Tuple[str, str]:
        access_payload = {
            "user_id": str(user.id),
            "email": user.email,
            "scope": scope,
            "device_id": str(device.id) if device else None,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(seconds=settings.WAY_CONFIG["JWT_ACCESS_LIFETIME"]),
            "type": "access",
        }
        refresh_payload = {
            "user_id": str(user.id),
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(seconds=settings.WAY_CONFIG["JWT_REFRESH_LIFETIME"]),
            "type": "refresh",
            "jti": str(uuid.uuid4()),
        }

        access_token = jwt.encode(access_payload, settings.WAY_CONFIG["JWT_SECRET"], algorithm="HS256")
        refresh_token = jwt.encode(refresh_payload, settings.WAY_CONFIG["JWT_SECRET"], algorithm="HS256")

        # Store refresh token hash
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        RefreshToken.objects.create(
            user=user,
            token_hash=token_hash,
            device=device,
            expires_at=timezone.now() + timedelta(seconds=settings.WAY_CONFIG["JWT_REFRESH_LIFETIME"]),
            ip_address=getattr(device, "ip_address", None) if device else None,
        )

        return access_token, refresh_token

    @staticmethod
    def refresh_access_token(refresh_token: str) -> Optional[str]:
        try:
            payload = jwt.decode(refresh_token, settings.WAY_CONFIG["JWT_SECRET"], algorithms=["HS256"])
            if payload.get("type") != "refresh":
                return None

            token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
            stored = RefreshToken.objects.get(token_hash=token_hash, revoked=False)
            if stored.expires_at < timezone.now():
                return None

            user = User.objects.get(id=payload["user_id"], is_active=True)
            access_payload = {
                "user_id": str(user.id),
                "email": user.email,
                "scope": "full",
                "iat": datetime.utcnow(),
                "exp": datetime.utcnow() + timedelta(seconds=settings.WAY_CONFIG["JWT_ACCESS_LIFETIME"]),
                "type": "access",
            }
            return jwt.encode(access_payload, settings.WAY_CONFIG["JWT_SECRET"], algorithm="HS256")
        except (jwt.InvalidTokenError, RefreshToken.DoesNotExist, User.DoesNotExist):
            return None

    @staticmethod
    def revoke_token(token_hash: str) -> bool:
        try:
            token = RefreshToken.objects.get(token_hash=token_hash)
            token.revoke()
            return True
        except RefreshToken.DoesNotExist:
            return False


class WalletAuthService:
    """Wallet-based authentication using Ed25519 signatures."""

    @staticmethod
    def verify_signature(wallet_address: str, message: str, signature: str, public_key: str) -> bool:
        """Verify Ed25519 signature for wallet auth."""
        try:
            # In production: verify against blockchain or stored public key
            # Simplified: verify signature format
            if not all([wallet_address, message, signature, public_key]):
                return False
            # Actual Ed25519 verification would use cryptography library
            return True  # Placeholder - implement actual crypto verification
        except Exception:
            return False

    @staticmethod
    def authenticate_wallet(wallet_address: str, signature: str, message: str, public_key: str) -> Optional[User]:
        if not WalletAuthService.verify_signature(wallet_address, message, signature, public_key):
            return None
        try:
            # Find user by wallet address
            user = User.objects.get(wallet_id=wallet_address, is_active=True)
            return user
        except User.DoesNotExist:
            return None


class DeviceService:
    """Device trust management."""

    @staticmethod
    def register_device(user: User, fingerprint: str, name: str, device_type: str, 
                        ip_address: str = None, user_agent: str = "", public_key: str = "") -> Device:
        device, created = Device.objects.update_or_create(
            user=user,
            fingerprint=fingerprint,
            defaults={
                "name": name,
                "device_type": device_type,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "public_key": public_key,
            }
        )
        if created:
            device.trust_level = "basic"
        else:
            device.trust_level = "verified"
        device.save(update_fields=["trust_level"])
        return device

    @staticmethod
    def approve_device(device_id: str, trust_level: str = "verified") -> bool:
        try:
            device = Device.objects.get(id=device_id)
            device.is_approved = True
            device.trust_level = trust_level
            device.save(update_fields=["is_approved", "trust_level"])
            return True
        except Device.DoesNotExist:
            return False

    @staticmethod
    def verify_biometric(device: Device, biometric_data: bytes) -> bool:
        """Verify biometric data against stored template."""
        if not device.biometric_enabled or not device.biometric_data:
            return False
        # In production: use secure biometric comparison
        # Simplified: compare hashes
        stored_hash = hashlib.sha256(device.biometric_data).hexdigest()
        provided_hash = hashlib.sha256(biometric_data).hexdigest()
        return stored_hash == provided_hash


class PermissionService:
    """Permission checking and management."""

    @staticmethod
    def check_permission(user: User, scope: str, permission_type: str, target_id: str = None) -> bool:
        """Check if user has permission."""
        # Superusers have all permissions
        if user.is_superuser:
            return True

        # Check specific permission
        qs = user.permissions.filter(scope=scope, permission_type=permission_type, granted=True, revoked=False)
        if target_id:
            qs = qs.filter(models.Q(target_id=target_id) | models.Q(target_id=None))
        else:
            qs = qs.filter(target_id=None)

        for perm in qs:
            if perm.is_valid():
                return True
        return False

    @staticmethod
    def grant_permission(user: User, scope: str, permission_type: str, target_id: str = None,
                         expires_minutes: int = None, granted_by: str = "system") -> "Permission":
        from .models import Permission
        expires = timezone.now() + timedelta(minutes=expires_minutes) if expires_minutes else None
        perm, _ = Permission.objects.update_or_create(
            user=user,
            scope=scope,
            permission_type=permission_type,
            target_id=target_id,
            defaults={"granted": True, "granted_at": timezone.now(), "expires_at": expires, "granted_by": granted_by, "revoked": False}
        )
        return perm

    @staticmethod
    def revoke_permission(user: User, scope: str, permission_type: str, target_id: str = None) -> bool:
        from .models import Permission
        qs = Permission.objects.filter(user=user, scope=scope, permission_type=permission_type)
        if target_id:
            qs = qs.filter(target_id=target_id)
        count = qs.update(revoked=True, revoked_at=timezone.now())
        return count > 0

    @staticmethod
    def get_device_permissions(user: User, device_id: str = None) -> list:
        """Get all device permissions for user."""
        qs = user.permissions.filter(scope="device", granted=True, revoked=False)
        if device_id:
            qs = qs.filter(models.Q(target_id=device_id) | models.Q(target_id=None))
        return [p.permission_type for p in qs if p.is_valid()]
