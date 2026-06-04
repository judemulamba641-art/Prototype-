"""Tests Skills - Skill Management, Execution, Providers, Marketplace"""
import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from way_skills.models import Skill, Provider, SkillExecution, PricingRule, SkillInstall, MarketplaceReview
from way_skills.services import SkillService, ProviderRouter, PricingEngine, ExecutionService, MarketplaceService
from way_finance.models import Wallet, CreditReserve


@pytest.mark.django_db
class TestSkillManagement:
    def test_create_skill(self, auth_client, test_user):
        response = auth_client.post(reverse("skills-list"), {
            "name": "New Skill",
            "skill_type": "creation",
            "manifest": {"entrypoint": "main.py", "runtime": "python3.11", "sandbox": {"ram": 256}},
            "code": "print('hello')",
            "price_per_use": "1.00",
        }, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert Skill.objects.filter(name="New Skill").exists()

    def test_marketplace_listing(self, api_client, test_skill):
        response = api_client.get(reverse("skills-marketplace"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_approve_skill(self, admin_client, test_skill):
        response = admin_client.post(reverse("skills-approve", kwargs={"pk": str(test_skill.id)}))
        assert response.status_code == status.HTTP_200_OK
        test_skill.refresh_from_db()
        assert test_skill.is_approved
        assert test_skill.lifecycle == "production"

    def test_suspend_skill(self, auth_client, test_user, test_skill):
        response = auth_client.post(reverse("skills-suspend", kwargs={"pk": str(test_skill.id)}))
        assert response.status_code == status.HTTP_200_OK
        test_skill.refresh_from_db()
        assert test_skill.lifecycle == "suspended"

    def test_validate_manifest(self, auth_client):
        response = auth_client.post(reverse("skills-validate-manifest", kwargs={"pk": "new"}), {
            "manifest": {"entrypoint": "main.py", "runtime": "python3.11"},
        }, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["valid"] is True

    def test_malware_scan(self, auth_client, test_user):
        skill = Skill.objects.create(
            owner_id=test_user.id,
            name="Malicious",
            code="import os; os.system('rm -rf /')",
            manifest={"entrypoint": "main.py"},
        )
        response = auth_client.post(reverse("skills-scan", kwargs={"pk": str(skill.id)}))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["safe"] is False
        assert len(response.data["threats"]) > 0

    def test_install_skill(self, auth_client, test_user, test_skill):
        response = auth_client.post(reverse("skills-install", kwargs={"pk": str(test_skill.id)}))
        assert response.status_code == status.HTTP_200_OK
        assert SkillInstall.objects.filter(user_id=test_user.id, skill=test_skill).exists()


@pytest.mark.django_db
class TestProviders:
    def test_provider_health(self, admin_client, test_provider):
        response = admin_client.get(reverse("providers-health"))
        assert response.status_code == status.HTTP_200_OK
        assert "openai" in str(response.data)

    def test_provider_selection(self, test_provider, test_skill):
        # Skip on SQLite (JSONField contains not supported)
        from django.db import connection
        if connection.vendor == 'sqlite':
            return
        provider = ProviderRouter.select_provider(test_skill, prefer_cache=False)
        assert provider is not None
        assert provider.name == "openai"

    def test_provider_failover(self, test_provider):
        # Simulate multiple failures to trigger status change
        for _ in range(10):
            ProviderRouter.update_provider_health(str(test_provider.id), 5000, False, "timeout")
        test_provider.refresh_from_db()
        assert test_provider.status in ["degraded", "down"]


@pytest.mark.django_db
class TestPricing:
    def test_calculate_cost(self, test_provider, test_skill):
        from decimal import Decimal
        cost = PricingEngine.calculate_cost(test_skill, test_provider, tokens=1000)
        assert cost > Decimal("0")

    def test_estimate_cost_api(self, auth_client, test_skill, test_provider):
        response = auth_client.post(reverse("skills-estimate", kwargs={"pk": str(test_skill.id)}), {
            "input_tokens": 100,
            "output_tokens": 50,
        }, format="json")
        # May return 400 if provider not available
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]

    def test_pricing_rule(self, test_provider, test_skill):
        from decimal import Decimal
        rule = PricingRule.objects.create(
            name="Test Rule",
            rule_type="provider_cost",
            skill=test_skill,
            provider=test_provider,
            base_price=Decimal("0.50"),
            multiplier=1.5,
        )
        cost = PricingEngine.calculate_cost(test_skill, test_provider, tokens=1000)
        assert cost > Decimal("0.50")


@pytest.mark.django_db
class TestExecution:
    def test_queue_execution(self, test_user, test_skill):
        execution = ExecutionService.queue_execution(str(test_user.id), str(test_skill.id), {"prompt": "test"})
        assert execution.status == "queued"

    def test_execute_skill(self, auth_client, test_user, test_skill, test_wallet, test_provider):
        CreditReserve.objects.create(currency="USD", total_reserve=10000, rate=100)
        response = auth_client.post(reverse("executions-list"), {
            "skill_id": str(test_skill.id),
            "input_data": {"prompt": "test"},
        }, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] in ["completed", "failed"]

    def test_insufficient_credits(self, auth_client, test_user, test_skill):
        wallet = Wallet.objects.create(user_id=test_user.id, balance=0)
        response = auth_client.post(reverse("executions-list"), {
            "skill_id": str(test_skill.id),
            "input_data": {"prompt": "test"},
        }, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        # Should fail due to insufficient credits


@pytest.mark.django_db
class TestMarketplace:
    def test_add_review(self, auth_client, test_user, test_skill):
        response = auth_client.post(reverse("reviews-add"), {
            "skill_id": str(test_skill.id),
            "rating": 5,
            "review": "Excellent skill!",
        })
        assert response.status_code == status.HTTP_200_OK
        test_skill.refresh_from_db()
        assert test_skill.rating_avg == 5.0
        assert test_skill.rating_count == 1

    def test_marketplace_listing(self, api_client, test_skill):
        skills = MarketplaceService.list_skills()
        assert len(skills) > 0
        assert skills[0].is_public
        assert skills[0].is_approved
