"""WAY Identity Serializers"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Device, Permission, RefreshToken, Group, GroupMembership

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "username", "display_name", "avatar_url", "bio", "language", "timezone", "phone", "country", "wallet_id", "settings", "two_factor_enabled", "date_joined", "last_login"]
        read_only_fields = ["id", "date_joined", "last_login", "wallet_id"]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=12)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "username", "password", "confirm_password", "display_name"]

    def validate(self, data):
        if data["password"] != data.pop("confirm_password"):
            raise serializers.ValidationError("Passwords do not match")
        return data

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        return user


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ["id", "name", "device_type", "fingerprint", "trust_level", "is_approved", "last_used", "ip_address", "biometric_enabled"]
        read_only_fields = ["id", "last_used"]


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "scope", "permission_type", "target_id", "granted", "granted_at", "expires_at", "revoked"]
        read_only_fields = ["id", "granted_at"]


class GroupSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ["id", "name", "description", "owner", "member_count", "settings", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_member_count(self, obj):
        return obj.members.count()


class GroupMembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = GroupMembership
        fields = ["id", "group", "user", "user_email", "role", "joined_at"]


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    device_fingerprint = serializers.CharField(required=False, allow_blank=True)
    device_name = serializers.CharField(required=False, allow_blank=True)
    device_type = serializers.CharField(required=False, allow_blank=True)


class WalletAuthSerializer(serializers.Serializer):
    wallet_address = serializers.CharField()
    message = serializers.CharField()
    signature = serializers.CharField()
    public_key = serializers.CharField()


class TokenResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    expires_in = serializers.IntegerField()
    token_type = serializers.CharField(default="Bearer")
