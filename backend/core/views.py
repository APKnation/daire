from django.shortcuts import get_object_or_404
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db.models.deletion import ProtectedError
import uuid
from urllib.parse import urlencode
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import (
    AIReputationResult, Assessment, BlockchainTransaction, Borrower, BorrowerAccount,
    BorrowerFinancialProfile, BorrowerLoan, Consent, CreditFeature, CreditProfile,
    IntegrationRequest, Lender, RepaymentRecord, SmartContractResult, DataExchange, DataRoutingPolicy,
)
from .serializers import (
    AIReputationResultSerializer, AssessmentSerializer, BorrowerAccountSerializer,
    BorrowerFinancialProfileSerializer, BorrowerLoanSerializer, BorrowerSerializer,
    BlockchainTransactionSerializer, ConsentSerializer, CreditFeatureSerializer,
    CreditProfileSerializer, IntegrationRequestSerializer, LenderSerializer,
    RepaymentRecordSerializer, SmartContractResultSerializer, UnifiedBorrowerSerializer,
    DataExchangeSerializer, DataRoutingPolicySerializer,
    AdminLogEntrySerializer,
)
from .services import (
    borrower_routing_payload, create_integration_request, fields_for_destination,
    merge_vendor_borrower_data, refresh_borrower_financial_profile, _get_json, _post_json,
    ExternalServiceUnavailable, record_exchange, active_routing_policy,
    explain_score,
)
from .services import (
    AIReputationService, BlockchainScoreService, BlockchainVerificationService,
    FeatureGenerationService,
)
from .services import blockchain_dimensions


class LenderViewSet(viewsets.ModelViewSet):
    queryset = Lender.objects.all()
    serializer_class = LenderSerializer

    @action(detail=True, methods=["post"], url_path="pull-borrower-data")
    def pull_borrower_data(self, request, pk=None):
        lender = self.get_object()
        borrower_reference = str(request.data.get("borrower_reference") or "").strip()
        if not borrower_reference:
            return Response({"detail": "borrower_reference is required."}, status=status.HTTP_400_BAD_REQUEST)
        exchange = record_exchange(system=DataExchange.System.LENDER, direction=DataExchange.Direction.PULL,
                                   operation="pull_borrower_data", lender=lender,
                                   fields_sent=["borrower_reference"], payload={"borrower_reference": borrower_reference})
        try:
            url = request.data.get("source_url") or f"{lender.api_base_url.rstrip('/')}/borrowers?{urlencode({'borrower_reference': borrower_reference})}"
            payload = fields_for_destination(_get_json(url), "lender")
            profile = merge_vendor_borrower_data(lender=lender, borrower_reference=borrower_reference, payload=payload,
                                                  account_reference=request.data.get("account_reference") or payload.get("account_reference"))
            exchange.status = DataExchange.Status.COMPLETED
            exchange.borrower = profile.borrower
            exchange.response = {"borrower_reference": borrower_reference, "fields": list(payload.keys())}
            exchange.save(update_fields=("status", "borrower", "response", "updated_at"))
            return Response(UnifiedBorrowerSerializer(profile.borrower).data)
        except (ExternalServiceUnavailable, ValidationError) as exc:
            exchange.status = DataExchange.Status.FAILED
            exchange.error_message = str(exc)
            exchange.save(update_fields=("status", "error_message", "updated_at"))
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=True, methods=["post"], url_path="push-borrower-data")
    def push_borrower_data(self, request, pk=None):
        lender = self.get_object()
        borrower = get_object_or_404(Borrower, borrower_reference=request.data.get("borrower_reference"))
        payload = request.data.get("payload") or borrower_routing_payload(borrower, "ai")
        exchange = record_exchange(system=DataExchange.System.LENDER, direction=DataExchange.Direction.PUSH,
                                   operation="push_borrower_data", lender=lender, borrower=borrower,
                                   fields_sent=list(payload.keys()), payload=payload)
        try:
            response = _post_json(request.data.get("target_url") or lender.api_base_url, payload)
            exchange.status, exchange.response = DataExchange.Status.COMPLETED, response
            exchange.save(update_fields=("status", "response", "updated_at"))
            return Response(response)
        except ExternalServiceUnavailable as exc:
            exchange.status, exchange.error_message = DataExchange.Status.FAILED, str(exc)
            exchange.save(update_fields=("status", "error_message", "updated_at"))
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class BorrowerViewSet(viewsets.ModelViewSet):
    queryset = Borrower.objects.prefetch_related("accounts__lender", "loans__repayments").all()
    serializer_class = BorrowerSerializer
    http_method_names = ("get", "post", "put", "patch", "head", "options")

    def get_serializer_class(self):
        if self.action in ("retrieve", "search", "ingest"):
            return UnifiedBorrowerSerializer
        return super().get_serializer_class()

    def perform_update(self, serializer):
        previous_active = serializer.instance.is_active
        borrower = serializer.save()
        if "is_active" not in self.request.data or previous_active == borrower.is_active:
            return
        if not self.request.user.is_authenticated:
            return
        action = "activated" if borrower.is_active else "deactivated"
        LogEntry.objects.log_action(
            user_id=self.request.user.pk,
            content_type_id=ContentType.objects.get_for_model(Borrower).pk,
            object_id=str(borrower.pk),
            object_repr=borrower.borrower_reference,
            action_flag=CHANGE,
            change_message=f"Borrower {action} from the frontend.",
        )

    def destroy(self, request, *args, **kwargs):
        borrower = self.get_object()
        try:
            borrower.delete()
        except ProtectedError as exc:
            protected_by = sorted({
                obj._meta.verbose_name_plural
                for obj in exc.protected_objects
            })
            return Response(
                {
                    "detail": (
                        "This borrower cannot be deleted because linked records exist. "
                        "Preserve the credit history or remove the linked records first."
                    ),
                    "protected_by": protected_by,
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        lender_name = (request.query_params.get("lender_name") or request.query_params.get("lender") or "").strip().lower()
        account_reference = (request.query_params.get("account_reference") or request.query_params.get("account") or "").strip()
        borrower_reference = (request.query_params.get("borrower_reference") or "").strip()
        queryset = self.get_queryset()
        if borrower_reference:
            queryset = queryset.filter(borrower_reference=borrower_reference)
        if lender_name or account_reference:
            account_qs = BorrowerAccount.objects.select_related("borrower", "lender")
            if lender_name:
                account_qs = account_qs.filter(lender__institution_name__icontains=lender_name)
            if account_reference:
                account_qs = account_qs.filter(account_reference__icontains=account_reference)
            queryset = queryset.filter(accounts__in=account_qs).distinct()
        serializer = UnifiedBorrowerSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="pull-from-all-lenders")
    def pull_from_all_lenders(self, request):
        """Pull a borrower from every lender; the caller never chooses a lender."""
        borrower_reference = str(request.data.get("borrower_reference") or "").strip()
        if not borrower_reference:
            return Response({"detail": "borrower_reference is required."}, status=status.HTTP_400_BAD_REQUEST)

        batch_reference = uuid.uuid4()
        successful, failed, results = [], [], []
        for lender in Lender.objects.all():
            exchange = record_exchange(
                system=DataExchange.System.LENDER, direction=DataExchange.Direction.PULL,
                operation="pull_borrower_data_all_lenders", lender=lender,
                batch_reference=batch_reference,
                fields_sent=["borrower_reference"], payload={"borrower_reference": borrower_reference},
            )
            try:
                url = f"{lender.api_base_url.rstrip('/')}/borrowers?{urlencode({'borrower_reference': borrower_reference})}"
                payload = fields_for_destination(_get_json(url), "lender")
                profile = merge_vendor_borrower_data(
                    lender=lender, borrower_reference=borrower_reference, payload=payload,
                    account_reference=payload.get("account_reference"),
                )
                exchange.status = DataExchange.Status.COMPLETED
                exchange.borrower = profile.borrower
                exchange.response = {"borrower_reference": borrower_reference, "fields": list(payload.keys())}
                exchange.save(update_fields=("status", "borrower", "response", "updated_at"))
                successful.append(lender.institution_name)
                results.append({"lender": lender.institution_name, "status": exchange.status, "exchange_id": exchange.id})
            except (ExternalServiceUnavailable, ValidationError) as exc:
                exchange.status = DataExchange.Status.FAILED
                exchange.error_message = str(exc)
                exchange.save(update_fields=("status", "error_message", "updated_at"))
                failed.append({"lender": lender.institution_name, "detail": str(exc)})
                results.append({"lender": lender.institution_name, "status": exchange.status, "exchange_id": exchange.id, "detail": str(exc)})

        borrower = Borrower.objects.filter(borrower_reference=borrower_reference).first()
        if not borrower:
            return Response({"detail": "Borrower was not found at any lender.", "failed": failed}, status=status.HTTP_404_NOT_FOUND)
        total = len(results)
        batch_status = "COMPLETED" if successful and not failed else "PARTIAL_SUCCESS" if successful else "FAILED"
        return Response({
            "borrower": UnifiedBorrowerSerializer(borrower).data,
            "pulled_from": successful,
            "failed": failed,
            "pull_reference": str(batch_reference),
            "status": batch_status,
            "total_lenders": total,
            "successful_lenders": len(successful),
            "failed_lenders": len(failed),
            "conflicts": borrower.data_conflicts or [],
            "results": results,
        })

    @action(detail=False, methods=["post"], url_path="ingest")
    def ingest(self, request):
        """Accept one institution's normalized payload and merge it into a borrower."""
        lender_id = request.data.get("lender_id")
        payload = request.data.get("payload") or {}
        if not isinstance(payload, dict):
            return Response({"detail": "payload must be a JSON object."}, status=status.HTTP_400_BAD_REQUEST)
        borrower_reference = str(
            request.data.get("borrower_reference")
            or payload.get("borrower_reference")
            or payload.get("customer_id")
            or ""
        ).strip()
        if not lender_id or not borrower_reference:
            return Response(
                {"detail": "lender_id, borrower_reference and a JSON payload are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        lender = get_object_or_404(Lender, lender_id=lender_id)
        profile = merge_vendor_borrower_data(
            lender=lender,
            borrower_reference=borrower_reference,
            payload=payload,
            account_reference=request.data.get("account_reference") or payload.get("account_reference"),
        )
        return Response(UnifiedBorrowerSerializer(profile.borrower).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="merge-vendor-data")
    def merge_vendor_data(self, request, pk=None):
        borrower = self.get_object()
        lender_id = request.data.get("lender_id")
        lender = get_object_or_404(Lender, lender_id=lender_id)
        payload = request.data.get("payload") or request.data
        profile = merge_vendor_borrower_data(
            lender=lender,
            borrower_reference=borrower.borrower_reference,
            payload=payload,
            account_reference=request.data.get("account_reference") or payload.get("account_reference"),
        )
        return Response(BorrowerFinancialProfileSerializer(profile).data)

    @action(detail=True, methods=["post"], url_path="broadcast-result")
    def broadcast_result(self, request, pk=None):
        """Broadcast a selected AI/blockchain result to every linked lender."""
        borrower = self.get_object()
        result_type = request.data.get("result_type") or "CREDIT_RESULT"
        result_payload = request.data.get("payload")
        if not isinstance(result_payload, dict):
            return Response({"detail": "payload must be a JSON object."}, status=status.HTTP_400_BAD_REQUEST)
        results = []
        sent_to = set()
        for account in borrower.accounts.select_related("lender").all():
            lender = account.lender
            if lender.id in sent_to:
                continue
            sent_to.add(lender.id)
            exchange = record_exchange(system=DataExchange.System.LENDER, direction=DataExchange.Direction.PUSH,
                                       operation="broadcast_credit_result", borrower=borrower, lender=lender,
                                       fields_sent=list(result_payload.keys()),
                                       payload={"borrower_reference": borrower.borrower_reference,
                                                "result_type": result_type, "result": result_payload})
            try:
                response = _post_json(request.data.get("target_url") or lender.api_base_url, exchange.payload)
                exchange.status, exchange.response = DataExchange.Status.COMPLETED, response
                exchange.save(update_fields=("status", "response", "updated_at"))
                results.append({"lender": lender.institution_name, "status": "COMPLETED", "response": response})
            except ExternalServiceUnavailable as exc:
                exchange.status, exchange.error_message = DataExchange.Status.FAILED, str(exc)
                exchange.save(update_fields=("status", "error_message", "updated_at"))
                results.append({"lender": lender.institution_name, "status": "FAILED", "detail": str(exc)})
        return Response({"borrower_reference": borrower.borrower_reference, "result_type": result_type, "broadcasts": results})


class BorrowerAccountViewSet(viewsets.ModelViewSet):
    queryset = BorrowerAccount.objects.select_related("borrower", "lender")
    serializer_class = BorrowerAccountSerializer


class BorrowerLoanViewSet(viewsets.ModelViewSet):
    queryset = BorrowerLoan.objects.select_related("borrower", "lender").prefetch_related("repayments")
    serializer_class = BorrowerLoanSerializer


class RepaymentRecordViewSet(viewsets.ModelViewSet):
    queryset = RepaymentRecord.objects.select_related("borrower", "lender", "loan")
    serializer_class = RepaymentRecordSerializer


class BorrowerFinancialProfileViewSet(viewsets.ModelViewSet):
    queryset = BorrowerFinancialProfile.objects.select_related("borrower")
    serializer_class = BorrowerFinancialProfileSerializer


class ConsentViewSet(viewsets.ModelViewSet):
    queryset = Consent.objects.select_related("lender", "borrower")
    serializer_class = ConsentSerializer


class AssessmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Assessment.objects.select_related("borrower")
    serializer_class = AssessmentSerializer
    lookup_field = "assessment_reference"

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        val = self.kwargs.get(lookup_url_kwarg)
        if val and str(val).isdigit():
            obj = queryset.filter(id=int(val)).first()
            if obj:
                self.check_object_permissions(self.request, obj)
                return obj
        return super().get_object()

    @action(detail=True, methods=["get"])
    def verify(self, request, assessment_reference=None, pk=None):
        assessment = self.get_object()
        if not assessment.blockchain_transaction_hash:
            return Response(
                {"detail": "This assessment has not been recorded on the blockchain yet, so there is no transaction to verify."},
                status=status.HTTP_409_CONFLICT,
            )
        exchange = record_exchange(system=DataExchange.System.BLOCKCHAIN, direction=DataExchange.Direction.PULL,
                                   operation="verify_transaction", borrower=assessment.borrower,
                                   assessment=assessment, fields_sent=["transaction_hash"],
                                   payload={"transaction_hash": assessment.blockchain_transaction_hash})
        try:
            transaction = BlockchainVerificationService().verify(assessment)
        except ExternalServiceUnavailable as exc:
            exchange.status, exchange.error_message = DataExchange.Status.FAILED, str(exc)
            exchange.save(update_fields=("status", "error_message", "updated_at"))
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        verified = transaction.status == "CONFIRMED"
        exchange.status = DataExchange.Status.COMPLETED
        exchange.response = BlockchainTransactionSerializer(transaction).data
        exchange.save(update_fields=("status", "response", "updated_at"))
        return Response({
            "assessment_reference": assessment.assessment_reference,
            "credit_score": assessment.credit_score,
            "verified": verified,
            "transaction_hash": transaction.transaction_hash,
            "block_number": transaction.block_number,
            "ruleset_version": assessment.ruleset_version,
        })

    @action(detail=True, methods=["get"], url_path="ai-result")
    def ai_result(self, request, pk=None):
        assessment = self.get_object()
        result = AIReputationResult.objects.filter(assessment=assessment).first()
        if not result:
            return Response({"detail": "AI result is not available."}, status=status.HTTP_404_NOT_FOUND)
        exchange = record_exchange(system=DataExchange.System.AI, direction=DataExchange.Direction.PULL,
                                   operation="read_reputation_result", borrower=assessment.borrower,
                                   assessment=assessment, fields_sent=[], response=AIReputationResultSerializer(result).data,
                                   status=DataExchange.Status.COMPLETED)
        return Response(AIReputationResultSerializer(result).data)

    def _features(self, assessment, destination="ai"):
        profile = CreditProfile.objects.filter(borrower=assessment.borrower).order_by("-created_at").first()
        if not profile:
            raise ExternalServiceUnavailable("Credit profile is unavailable.")
        features = {feature.name: float(feature.value) for feature in profile.features.all()}
        return fields_for_destination(features, destination)

    def _blockchain_dimensions(self, assessment):
        profile = CreditProfile.objects.filter(borrower=assessment.borrower).order_by("-created_at").first()
        if not profile:
            raise ExternalServiceUnavailable("Credit profile is unavailable.")
        features = {feature.name: float(feature.value) for feature in profile.features.all()}
        return blockchain_dimensions(features=features, borrower=assessment.borrower)

    @action(detail=True, methods=["post"], url_path="ai-reputation")
    def ai_reputation(self, request, pk=None):
        assessment = self.get_object()
        features = self._features(assessment, "ai")
        exchange = record_exchange(system=DataExchange.System.AI, direction=DataExchange.Direction.PUSH,
                                   operation="calculate_reputation", borrower=assessment.borrower,
                                   assessment=assessment, policy=active_routing_policy(),
                                   fields_sent=list(features.keys()), payload=features)
        try:
            result = AIReputationService().calculate(assessment, features)
        except ExternalServiceUnavailable as exc:
            exchange.status, exchange.error_message = DataExchange.Status.FAILED, str(exc)
            exchange.save(update_fields=("status", "error_message", "updated_at"))
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        assessment.reputation, assessment.reputation_score = result.reputation, result.score
        assessment.risk_level, assessment.behavior_summary = result.risk_level, result.behavior_summary
        assessment.model_version = result.model_version
        assessment.score_inputs = features
        assessment.score_explanation = [{"dimension": "AI", "name": "AI reputation", "value": result.score, "reason": result.behavior_summary or "The AI engine returned a reputation result."}]
        assessment.save(update_fields=("reputation", "reputation_score", "risk_level", "behavior_summary", "model_version", "score_inputs", "score_explanation", "updated_at"))
        exchange.status = DataExchange.Status.COMPLETED
        exchange.response = AIReputationResultSerializer(result).data
        exchange.save(update_fields=("status", "response", "updated_at"))
        return Response(AIReputationResultSerializer(result).data)

    @action(detail=True, methods=["post"], url_path="blockchain-score")
    def blockchain_score(self, request, pk=None):
        assessment = self.get_object()
        dimensions = self._blockchain_dimensions(assessment)
        exchange = record_exchange(system=DataExchange.System.BLOCKCHAIN, direction=DataExchange.Direction.PUSH,
                                   operation="calculate_credit_score", borrower=assessment.borrower,
                                   assessment=assessment, policy=active_routing_policy(),
                                   fields_sent=list(dimensions.keys()), payload=dimensions)
        try:
            result = BlockchainScoreService().calculate(assessment, dimensions)
        except ExternalServiceUnavailable as exc:
            exchange.status, exchange.error_message = DataExchange.Status.FAILED, str(exc)
            exchange.save(update_fields=("status", "error_message", "updated_at"))
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        assessment.credit_score, assessment.ruleset_version = result.credit_score, result.ruleset_version
        profile = CreditProfile.objects.filter(borrower=assessment.borrower).order_by("-created_at").first()
        features = {feature.name: float(feature.value) for feature in profile.features.all()} if profile else {}
        assessment.score_inputs = dimensions
        assessment.score_explanation = explain_score(dimensions=dimensions, features=features, borrower=assessment.borrower)
        assessment.save(update_fields=("credit_score", "ruleset_version", "score_inputs", "score_explanation", "updated_at"))
        exchange.status = DataExchange.Status.COMPLETED
        exchange.response = SmartContractResultSerializer(result).data
        exchange.save(update_fields=("status", "response", "updated_at"))
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


class DataRoutingPolicyViewSet(viewsets.ModelViewSet):
    queryset = DataRoutingPolicy.objects.all()
    serializer_class = DataRoutingPolicySerializer


class DataExchangeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DataExchange.objects.select_related("borrower", "lender", "assessment", "policy").all()
    serializer_class = DataExchangeSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        batch_reference = self.request.query_params.get("batch_reference")
        if batch_reference:
            queryset = queryset.filter(batch_reference=batch_reference)
        return queryset


class AdminLogEntryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LogEntry.objects.select_related("user", "content_type").order_by("-action_time")
    serializer_class = AdminLogEntrySerializer
    permission_classes = (IsAuthenticated,)


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
        })
