"""WAY Test Configuration"""
import pytest
from django.conf import settings
from rest_framework.test import APIClient
import jwt
from datetime import datetime, timedelta

from way_identity.models import User
from way_finance.models import Wallet
from way_core.models import RegistryEntry, SystemConfig
from way_skills.models import Skill, Provider
from way_infra.models import AuditLog, EventLog


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def test_user(db):
    user = User.objects.create_user(
        email="test@way.com",
        username="testuser",
        password="TestPassword123!",
        display_name="Test User"
    )
    return user


@pytest.fixture
def auth_client(api_client, test_user):
    # Generate JWT manually using PyJWT
    access_payload = {
        "user_id": str(test_user.id),
        "email": test_user.email,
        "scope": "full",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(seconds=900),
        "type": "access",
    }
    access_token = jwt.encode(access_payload, settings.WAY_CONFIG["JWT_SECRET"], algorithm="HS256")
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
    return api_client


@pytest.fixture
def admin_user(db):
    user = User.objects.create_user(
        email="admin@way.com",
        username="admin",
        password="AdminPassword123!",
        is_staff=True,
        is_superuser=True
    )
    return user


@pytest.fixture
def admin_client(api_client, admin_user):
    access_payload = {
        "user_id": str(admin_user.id),
        "email": admin_user.email,
        "scope": "full",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(seconds=900),
        "type": "access",
    }
    access_token = jwt.encode(access_payload, settings.WAY_CONFIG["JWT_SECRET"], algorithm="HS256")
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
    return api_client


@pytest.fixture
def test_wallet(db, test_user):
    wallet = Wallet.objects.create(
        user_id=test_user.id,
        public_key="test_public_key",
        private_key_encrypted="encrypted_key",
        balance=1000.00
    )
    test_user.wallet_id = wallet.id
    test_user.save()
    return wallet


@pytest.fixture
def test_skill(db, test_user):
    skill = Skill.objects.create(
        owner_id=test_user.id,
        name="Test Skill",
        skill_type="creation",
        lifecycle="production",
        manifest={"entrypoint": "main.py", "runtime": "python3.11"},
        price_per_use=0.50,
        is_public=True,
        is_approved=True
    )
    return skill


@pytest.fixture
def test_provider(db):
    provider = Provider.objects.create(
        name="openai",
        display_name="OpenAI",
        status="active",
        priority=1,
        cost_per_1k_tokens=0.03,
        cost_per_request=0.001,
        capabilities={"completion": True, "vision": True, "embedding": True, "audio": False},
        models_available=["gpt-4", "gpt-3.5-turbo"]
    )
    return provider


@pytest.fixture
def system_config(db):
    return SystemConfig.objects.create(key="test_config", value={"test": True})
