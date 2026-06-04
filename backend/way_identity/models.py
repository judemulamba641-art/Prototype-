"""
WAY Identity Models - Unified: Users + Auth + Permissions + Device + JWT
"""
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.core.validators import RegexValidator
from django.utils import timezone
from django.conf import settings

from way_core.models import BaseModel


class UserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError("Email required")
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, username, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    objects = UserManager()
    """Unified user model with profile, wallet reference, settings."""
    email = models.EmailField(unique=True, db_index=True)
    username = models.CharField(max_length=50, unique=True, db_index=True, validators=[
        RegexValidator(regex=r"^[a-zA-Z0-9_]+$", message="Username must be alphanumeric")
    ])
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    # Profile (embedded to avoid joins)
    display_name = models.CharField(max_length=100, blank=True)
    avatar_url = models.URLField(blank=True)
    bio = models.TextField(blank=True, max_length=500)
    language = models.CharField(max_length=10, default="en")
    timezone = models.CharField(max_length=50, default="UTC")
    phone = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=2, blank=True)

    # Wallet reference (actual wallet in way_finance)
    wallet_id = models.UUIDField(null=True, blank=True, db_index=True)

    # Settings (JSON for flexibility)
    settings = models.JSONField(default=dict, blank=True)  # {theme: "dark", notifications: true, 2fa: false}

    # Security
    failed_login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(auto_now_add=True)
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=32, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        indexes = [
            models.Index(fields=["email", "is_active"]),
            models.Index(fields=["wallet_id"]),
            models.Index(fields=["locked_until"]),
        ]

    def __str__(self):
        return self.email

    @property
    def is_locked(self):
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False

    def lock(self, minutes=30):
        self.locked_until = timezone.now() + timezone.timedelta(minutes=minutes)
        self.save(update_fields=["locked_until"])

    def unlock(self):
        self.locked_until = None
        self.failed_login_attempts = 0
        self.save(update_fields=["locked_until", "failed_login_attempts"])


class Device(BaseModel):
    """Device trust and biometric tracking."""
    TRUST_LEVELS = [
        ("untrusted", "Untrusted"), ("basic", "Basic"), ("verified", "Verified"),
        ("biometric", "Biometric"), ("hardware", "Hardware"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="devices")
    name = models.CharField(max_length=100)
    device_type = models.CharField(max_length=20, choices=[("mobile", "Mobile"), ("desktop", "Desktop"), ("web", "Web"), ("sdk", "SDK")])
    fingerprint = models.CharField(max_length=255, db_index=True)  # Device fingerprint hash
    public_key = models.TextField(blank=True)  # For device attestation
    trust_level = models.CharField(max_length=20, choices=TRUST_LEVELS, default="untrusted")
    is_approved = models.BooleanField(default=False)
    last_used = models.DateTimeField(auto_now=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    biometric_enabled = models.BooleanField(default=False)
    biometric_data = models.BinaryField(null=True, blank=True)  # Encrypted biometric template

    class Meta:
        unique_together = [["user", "fingerprint"]]
        indexes = [models.Index(fields=["user", "trust_level", "is_approved"])]

    def __str__(self):
        return f"{self.user.email} - {self.name}"


class Permission(BaseModel):
    """Granular permissions for skills, runtime, devices."""
    SCOPE_CHOICES = [
        ("device", "Device"), ("skill", "Skill"), ("runtime", "Runtime"),
        ("wallet", "Wallet"), ("storage", "Storage"), ("network", "Network"),
    ]
    PERMISSION_TYPES = [
        ("camera", "Camera"), ("bluetooth", "Bluetooth"), ("microphone", "Microphone"),
        ("storage", "Storage"), ("gpu", "GPU"), ("asic", "ASIC"), ("local_server", "Local Server"),
        ("execute", "Execute"), ("install", "Install"), ("delete", "Delete"),
        ("read", "Read"), ("write", "Write"), ("admin", "Admin"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="permissions")
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES)
    permission_type = models.CharField(max_length=20, choices=PERMISSION_TYPES)
    target_id = models.UUIDField(null=True, blank=True)  # Specific skill/device ID, null = all
    granted = models.BooleanField(default=False)
    granted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    granted_by = models.CharField(max_length=50, blank=True)  # user, system, admin
    temporary_token = models.CharField(max_length=255, blank=True)
    revoked = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [["user", "scope", "permission_type", "target_id"]]
        indexes = [models.Index(fields=["user", "scope", "granted", "revoked"])]

    def __str__(self):
        return f"{self.user.email} - {self.scope}:{self.permission_type}"

    def is_valid(self):
        if self.revoked or not self.granted:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True


class RefreshToken(BaseModel):
    """JWT refresh token tracking."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="refresh_tokens")
    token_hash = models.CharField(max_length=255, db_index=True)
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["token_hash", "revoked", "expires_at"])]

    def revoke(self):
        self.revoked = True
        self.revoked_at = timezone.now()
        self.save(update_fields=["revoked", "revoked_at"])


class Group(BaseModel):
    """User groups with roles."""
    ROLES = [("owner", "Owner"), ("admin", "Admin"), ("member", "Member")]
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_groups")
    members = models.ManyToManyField(User, through="GroupMembership", related_name="way_groups")
    settings = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.name


class GroupMembership(BaseModel):
    """Group membership with role."""
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=Group.ROLES, default="member")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["group", "user"]]
