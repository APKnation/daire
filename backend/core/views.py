from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import (
    AIReputationResult, Assessment, AuditLog, BlockchainTransaction, Borrower, Consent,
    CreditFeature, CreditProfile, IntegrationRequest, Lender, SmartContractResult,
)
from .serializers import (
    AIReputationResultSerializer, AuditLogSerializer, AssessmentSerializer, BorrowerSerializer,
    BlockchainTransactionSerializer, ConsentSerializer, CreditFeatureSerializer,
    CreditProfileSerializer, IntegrationRequestSerializer, LenderSerializer,
    SmartContractResultSerializer,
)
from .services import create_integration_request
from .services import (
    AIReputationService, BlockchainScoreService, BlockchainVerificationService,
    ExternalServiceUnavailable, FeatureGenerationService,
)


class LenderViewSet(viewsets.ModelViewSet):
    queryset = Lender.objects.all()
    serializer_class = LenderSerializer


class BorrowerViewSet(viewsets.ModelViewSet):
    queryset = Borrower.objects.all()
    serializer_class = BorrowerSerializer


class ConsentViewSet(viewsets.ModelViewSet):
    queryset = Consent.objects.select_related("lender", "borrower")
    serializer_class = ConsentSerializer


class AssessmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Assessment.objects.select_related("borrower")
    serializer_class = AssessmentSerializer

    @action(detail=True, methods=["get"])
    def verify(self, request, pk=None):
        assessment = self.get_object()
        try:
            transaction = BlockchainVerificationService().verify(assessment)
        except ExternalServiceUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        verified = transaction.status == "CONFIRMED"
        return Response({
            "assessment_reference": assessment.assessment_reference,
            "credit_score": assessment.credit_score,
            "verified": verified,
            "transaction_hash": transaction.transaction_hash,
            "block_number": transaction.block_number,
            "ruleset_version": assessment.ruleset_version,
        })

    def _features(self, assessment):
        profile = CreditProfile.objects.filter(borrower=assessment.borrower).order_by("-created_at").first()
        if not profile:
            raise ExternalServiceUnavailable("Credit profile is unavailable.")
        return {feature.name: float(feature.value) for feature in profile.features.all()}

    @action(detail=True, methods=["post"], url_path="ai-reputation")
    def ai_reputation(self, request, pk=None):
        assessment = self.get_object()
        try:
            result = AIReputationService().calculate(assessment, self._features(assessment))
        except ExternalServiceUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        assessment.reputation, assessment.reputation_score = result.reputation, result.score
        assessment.risk_level, assessment.behavior_summary = result.risk_level, result.behavior_summary
        assessment.model_version = result.model_version
        assessment.save(update_fields=("reputation", "reputation_score", "risk_level", "behavior_summary", "model_version", "updated_at"))
        return Response(AIReputationResultSerializer(result).data)

    @action(detail=True, methods=["post"], url_path="blockchain-score")
    def blockchain_score(self, request, pk=None):
        assessment = self.get_object()
        try:
            result = BlockchainScoreService().calculate(assessment, self._features(assessment))
        except ExternalServiceUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        assessment.credit_score, assessment.ruleset_version = result.credit_score, result.ruleset_version
        assessment.save(update_fields=("credit_score", "ruleset_version", "updated_at"))
        return Response(SmartContractResultSerializer(result).data)


class CreditProfileViewSet(viewsets.ModelViewSet):
    queryset = CreditProfile.objects.prefetch_related("features")
    serializer_class = CreditProfileSerializer

    @action(detail=True, methods=["post"], url_path="generate-features")
    def generate_features(self, request, pk=None):
        features = FeatureGenerationService().generate(self.get_object())
        return Response(CreditFeatureSerializer(features, many=True).data)

    @action(detail=True, methods=["get"], url_path="features")
    def feature_list(self, request, pk=None):
        return Response(CreditFeatureSerializer(self.get_object().features.all(), many=True).data)


class CreditFeatureViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CreditFeature.objects.select_related("profile")
    serializer_class = CreditFeatureSerializer


class AIReputationResultViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AIReputationResult.objects.all()
    serializer_class = AIReputationResultSerializer


class SmartContractResultViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SmartContractResult.objects.all()
    serializer_class = SmartContractResultSerializer


class BlockchainTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BlockchainTransaction.objects.all()
    serializer_class = BlockchainTransactionSerializer


class IntegrationRequestViewSet(viewsets.ModelViewSet):
    queryset = IntegrationRequest.objects.select_related("lender", "borrower", "consent")
    serializer_class = IntegrationRequestSerializer
    http_method_names = ("get", "post", "head", "options")

    def create(self, request):
        lender = get_object_or_404(Lender, lender_id=request.data.get("lender_id"))
        borrower = get_object_or_404(Borrower, borrower_reference=request.data.get("borrower_reference"))
        consent = get_object_or_404(Consent, consent_id=request.data.get("consent_reference"))
        integration_request = create_integration_request(
            lender=lender, borrower=borrower, consent=consent, actor=request.user,
        )
        return Response(IntegrationRequestSerializer(integration_request).data, status=status.HTTP_201_CREATED)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("actor")
    serializer_class = AuditLogSerializer


from rest_framework.views import APIView


class DashboardView(APIView):
    def get(self, request):
        return Response({
            "lenders": LenderSerializer(Lender.objects.all(), many=True).data,
            "borrowers": BorrowerSerializer(Borrower.objects.all(), many=True).data,
            "consents": ConsentSerializer(Consent.objects.all(), many=True).data,
            "assessments": AssessmentSerializer(
                Assessment.objects.select_related("borrower"), many=True
            ).data,
            "integrations": IntegrationRequestSerializer(
                IntegrationRequest.objects.select_related("lender", "borrower", "consent"), many=True
            ).data,
            "auditLogs": AuditLogSerializer(
                AuditLog.objects.select_related("actor"), many=True
            ).data,
        })
