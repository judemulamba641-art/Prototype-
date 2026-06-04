"""WAY Skills Views"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import models

from .models import Skill, Provider, SkillExecution, PricingRule, SkillInstall, MarketplaceReview
from .serializers import (
    SkillSerializer, SkillCreateSerializer, SkillInstallSerializer, ProviderSerializer,
    SkillExecutionSerializer, ExecutionCreateSerializer, PricingRuleSerializer,
    MarketplaceReviewSerializer, CostEstimateSerializer, ManifestValidationSerializer
)
from .services import SkillService, ProviderRouter, PricingEngine, ExecutionService, MarketplaceService
from way_infra.permissions import IsAdminOrReadOnly, IsOwnerOrAdmin


class SkillViewSet(viewsets.ModelViewSet):
    """Skill management and marketplace."""
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["skill_type", "lifecycle", "is_public", "is_approved"]
    search_fields = ["name", "description", "tags"]

    def get_permissions(self):
        if self.action in ["list", "retrieve", "marketplace"]:
            return [AllowAny()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(owner_id=self.request.user.id)

    def create(self, request):
        serializer = SkillCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        skill = SkillService.create_skill(
            str(request.user.id), data["name"], data["skill_type"],
            data["manifest"], data.get("code", ""), data["price_per_use"]
        )
        return Response(SkillSerializer(skill).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def marketplace(self, request):
        """Public marketplace listing."""
        skill_type = request.query_params.get("type")
        skills = MarketplaceService.list_skills(skill_type)
        page = self.paginate_queryset(skills)
        if page is not None:
            return self.get_paginated_response(SkillSerializer(page, many=True).data)
        return Response(SkillSerializer(skills, many=True).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        skill = self.get_object()
        if not request.user.is_staff:
            return Response({"error": "Admin only"}, status=status.HTTP_403_FORBIDDEN)
        skill.approve(str(request.user.id))
        return Response({"success": True})

    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        skill = self.get_object()
        if not request.user.is_staff and skill.owner_id != request.user.id:
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
        skill.suspend()
        return Response({"success": True})

    @action(detail=True, methods=["post"])
    def validate_manifest(self, request, pk=None):
        serializer = ManifestValidationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid, errors = SkillService.validate_manifest(serializer.validated_data["manifest"])
        return Response({"valid": valid, "errors": errors})

    @action(detail=True, methods=["post"])
    def scan(self, request, pk=None):
        skill = self.get_object()
        if not skill.code:
            return Response({"safe": True, "threats": []})
        safe, threats = SkillService.scan_malware(skill.code)
        return Response({"safe": safe, "threats": threats})

    @action(detail=True, methods=["post"])
    def install(self, request, pk=None):
        skill = self.get_object()
        config = request.data.get("config", {})
        install = SkillService.install_skill(str(request.user.id), str(skill.id), config)
        return Response(SkillInstallSerializer(install).data)

    @action(detail=True, methods=["post"])
    def estimate(self, request, pk=None):
        serializer = CostEstimateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        estimate = PricingEngine.estimate_cost(str(pk), data["input_tokens"], data["output_tokens"])
        return Response(estimate)


class ProviderViewSet(viewsets.ModelViewSet):
    """Provider management."""
    queryset = Provider.objects.all()
    serializer_class = ProviderSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["status", "name"]

    @action(detail=False, methods=["get"])
    def health(self, request):
        providers = Provider.objects.all()
        health = {
            p.name: {"status": p.status, "latency_ms": p.latency_ms, "success_rate": p.success_rate, "quota": p.quota_remaining}
            for p in providers
        }
        return Response(health)


class ExecutionViewSet(viewsets.ModelViewSet):
    """Skill execution management."""
    queryset = SkillExecution.objects.all()
    serializer_class = SkillExecutionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "skill", "provider"]

    def get_queryset(self):
        if self.request.user.is_staff:
            return SkillExecution.objects.all()
        return SkillExecution.objects.filter(user_id=self.request.user.id)

    def create(self, request):
        serializer = ExecutionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        execution = ExecutionService.queue_execution(str(request.user.id), str(data["skill_id"]), data["input_data"])
        # Execute immediately (in production, this would be async)
        execution = ExecutionService.execute_skill(str(execution.id))
        return Response(SkillExecutionSerializer(execution).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        execution = self.get_object()
        if execution.status not in ["failed", "cancelled"]:
            return Response({"error": "Can only retry failed executions"}, status=status.HTTP_400_BAD_REQUEST)
        new_execution = ExecutionService.queue_execution(str(execution.user_id), str(execution.skill_id), execution.input_data)
        new_execution = ExecutionService.execute_skill(str(new_execution.id))
        return Response(SkillExecutionSerializer(new_execution).data)


class InstallViewSet(viewsets.ModelViewSet):
    """User skill installations."""
    queryset = SkillInstall.objects.all()
    serializer_class = SkillInstallSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SkillInstall.objects.filter(user_id=self.request.user.id)


class ReviewViewSet(viewsets.ModelViewSet):
    """Skill reviews."""
    queryset = MarketplaceReview.objects.all()
    serializer_class = MarketplaceReviewSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user_id=self.request.user.id)

    @action(detail=False, methods=["post"])
    def add(self, request):
        skill_id = request.data.get("skill_id")
        rating = request.data.get("rating")
        review = request.data.get("review", "")
        rev = MarketplaceService.add_review(skill_id, str(request.user.id), rating, review)
        return Response(MarketplaceReviewSerializer(rev).data)


class PricingViewSet(viewsets.ModelViewSet):
    """Pricing rules management."""
    queryset = PricingRule.objects.all()
    serializer_class = PricingRuleSerializer
    permission_classes = [IsAdminOrReadOnly]
