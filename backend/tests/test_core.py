import uuid
"""Tests Core - Registry, Runtime, SDK, Health"""
import pytest
from django.urls import reverse
from rest_framework import status
from way_core.models import RegistryEntry, RuntimeSession, SDKManifest, SystemConfig
from way_core.services import RegistryService, RuntimeService, ConfigService, HealthService


@pytest.mark.django_db
class TestRegistry:
    def test_register_entity(self):
        entity_id = str(uuid.uuid4())
        entry = RegistryService.register("skill", entity_id, "Test Skill", {"version": "1.0"})
        assert entry.entity_type == "skill"
        assert entry.name == "Test Skill"
        assert RegistryEntry.objects.filter(entity_id=entity_id).exists()

    def test_heartbeat(self):
        entity_id = str(uuid.uuid4())
        entry = RegistryService.register("node", entity_id, "Worker 1")
        success = RegistryService.heartbeat("node", entity_id, {"cpu": 45, "ram": 60})
        assert success
        entry.refresh_from_db()
        assert entry.health["cpu"] == 45

    def test_unregister(self):
        entity_id = str(uuid.uuid4())
        RegistryService.register("session", entity_id, "Session 1")
        success = RegistryService.unregister("session", entity_id)
        assert success
        assert not RegistryEntry.objects.filter(entity_id=entity_id).exists()

    def test_get_status(self):
        entity_id = str(uuid.uuid4())
        RegistryService.register("provider", entity_id, "Provider 1", version="2.0")
        status_data = RegistryService.get_status("provider", entity_id)
        assert status_data is not None
        assert status_data["name"] == "Provider 1"
        assert status_data["version"] == "2.0"


@pytest.mark.django_db
class TestRuntime:
    def test_create_session(self, test_user):
        session = RuntimeService.create_session(str(test_user.id), str(uuid.uuid4()), {"ram": 512})
        assert session.status == "pending"
        assert session.sandbox_config["ram"] == 512

    def test_start_session(self, test_user):
        session = RuntimeService.create_session(str(test_user.id), str(uuid.uuid4()))
        success = RuntimeService.start_session(str(session.id))
        assert success
        session.refresh_from_db()
        assert session.status == "running"
        assert session.started_at is not None

    def test_complete_session(self, test_user):
        session = RuntimeService.create_session(str(test_user.id), str(uuid.uuid4()))
        RuntimeService.start_session(str(session.id))
        success = RuntimeService.complete_session(str(session.id), 0, "Execution completed")
        assert success
        session.refresh_from_db()
        assert session.status == "completed"
        assert session.exit_code == 0

    def test_kill_session(self, test_user):
        session = RuntimeService.create_session(str(test_user.id), str(uuid.uuid4()))
        RuntimeService.start_session(str(session.id))
        success = RuntimeService.kill_session(str(session.id), "manual kill")
        assert success
        session.refresh_from_db()
        assert session.status == "killed"

    def test_sandbox_enforcement(self, test_user):
        import time
        session = RuntimeService.create_session(str(test_user.id), str(uuid.uuid4()), {"timeout": 1})
        RuntimeService.start_session(str(session.id))
        # Wait for timeout
        time.sleep(1.1)
        session.refresh_from_db()
        actions = RuntimeService.enforce_sandbox(session)
        # Should have killed the session
        assert actions.get("timeout") or session.status == "killed"


@pytest.mark.django_db
class TestSDK:
    def test_compatibility_check(self, api_client):
        SDKManifest.objects.create(sdk_version="2.0", runtime_version="2.4", compatibility="compatible")
        response = api_client.get(reverse("sdk-check") + "?sdk_version=2.0&runtime_version=2.4")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["compatible"] is True

    def test_incompatible_version(self, api_client):
        response = api_client.get(reverse("sdk-check") + "?sdk_version=1.0&runtime_version=2.4")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestConfig:
    def test_get_config(self):
        ConfigService.set("test_key", {"value": 123})
        value = ConfigService.get("test_key")
        assert value == {"value": 123}

    def test_get_default(self):
        value = ConfigService.get("nonexistent", "default")
        assert value == "default"

    def test_config_api(self, admin_client):
        # Use direct URL instead of reverse
        response = admin_client.post("/api/core/config/set_value/", {
            "key": "api_test",
            "value": {"test": True},
        }, format="json")
        assert response.status_code == status.HTTP_200_OK
        response = admin_client.get("/api/core/config/get_value/?key=api_test")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["value"] == {"test": True}


@pytest.mark.django_db
class TestHealth:
    def test_health_check(self, api_client):
        response = api_client.get("/api/health/")
        # May return 503 if Redis is not available
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]
        assert "status" in response.data
        assert "services" in response.data

    def test_health_service(self):
        health = HealthService.check()
        assert "status" in health
        assert "database" in health["services"]
        assert "cache" in health["services"]
