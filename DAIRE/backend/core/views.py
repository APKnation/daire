from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db.models.deletion import ProtectedError
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode, urlsplit, parse_qsl
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class ImmutableDeleteGuardMixin:
    """Turn the DB-level 'immutable' trigger error into a friendly 409.

    Assessment, AI-result, contract-result and transaction rows carry SQLite
    delete triggers (immutability.py). This mixin intercepts the resulting
    IntegrityError so the API answers 409 with an explanation instead of a
    raw 500 — deletion of externally-produced records stays impossible.
    """

    def destroy(self, request, *args, **kwargs):
        from django.db.utils import IntegrityError

        try:
            return super().destroy(request, *args, **kwargs)
        except IntegrityError as exc:
            if "immutable" in str(exc).lower():
                return Response(
                    {"detail": "This record is immutable: assessment, AI and blockchain results cannot be deleted."},
                    status=status.HTTP_409_CONFLICT,
                )
            raise
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
    RepaymentRecordSerializer, SmartContractResultSerializer,
    DataExchangeSerializer, DataRoutingPolicySerializer,
    AdminLogEntrySerializer, LenderDataReceiveSerializer,
    CompactBorrowerSerializer, CompactUnifiedBorrowerSerializer,
)
from .services import (
    borrower_routing_payload, create_integration_request, fields_for_destination,
    merge_vendor_borrower_data, refresh_borrower_financial_profile, _get_json, _post_json,
    ExternalServiceUnavailable, record_exchange, active_routing_policy,
    explain_score, ensure_credit_profile, summarize_transactions, lender_broadcast_url,
    api_keys_required,
)
from .services import (
    AIReputationService, BlockchainScoreService, BlockchainVerificationService,
    FeatureGenerationService,
)
from .services import blockchain_dimensions


def _lender_api_key_from_headers(headers) -> str:
    """Read the lender credential: `X-API-Key` or `Authorization: Api-Key <k>`."""
    get = getattr(headers, "get", None)
    key = (get("X-API-Key", "") if get else "") or ""
    if not key and get:
        auth = get("Authorization", "") or ""
        if auth.lower().startswith("api-key "):
            key = auth[8:]
    return key.strip()


def _check_lender_key(headers, lender):
    """Return a 401 Response unless the push is authorized.

    Subsystems share one trusted network, so plain keyless JSON is the
    default transport; keys are enforced only when REQUIRE_API_KEYS=true.
    Even then, lenders registered before API keys existed have a blank hash
    and stay usable without a key (legacy mode).
    """
    if not api_keys_required():
        return None
    if not lender.api_key_hash:
        return None
    if lender.check_api_key(_lender_api_key_from_headers(headers)):
        return None
    return Response(
        {"detail": "Invalid or missing lender API key. Send it as the X-API-Key header."},
        status=status.HTTP_401_UNAUTHORIZED,
    )


def _normalize_lender_push(data):
    """Normalize wrapped or flat lender pushes to {lender_id, borrower_reference, account_reference, payload}."""
    if not isinstance(data, dict):
        return None, None, None, None
    if isinstance(data.get("payload"), dict):
        payload = dict(data["payload"])
        lender = data.get("lender") or payload.get("lender")
        lender_id = str(
            data.get("lender_id") or payload.get("lender_id")
            or (lender.get("lender_id") if isinstance(lender, dict) else "")
            or (lender.get("id") if isinstance(lender, dict) else "")
            or ""
        ).strip()
        borrower_reference = str(
            data.get("borrower_reference") or payload.get("borrower_reference") or payload.get("customer_id") or ""
        ).strip()
        account_reference = str(data.get("account_reference") or payload.get("account_reference") or "").strip() or None
        # merge() validates payload.borrower_reference — keep it in sync.
        if borrower_reference:
            payload.setdefault("borrower_reference", borrower_reference)
        return lender_id or None, borrower_reference or None, account_reference, payload
    # Flat contract: everything except the routing keys is the payload.
    lender = data.get("lender")
    lender_id = str(
        data.get("lender_id")
        or (lender.get("lender_id") if isinstance(lender, dict) else "")
        or (lender.get("id") if isinstance(lender, dict) else "")
        or ""
    ).strip() or None
    borrower_reference = str(data.get("borrower_reference") or data.get("customer_id") or "").strip() or None
    account_reference = str(data.get("account_reference") or "").strip() or None
    payload = {key: value for key, value in data.items() if key not in ("lender_id", "borrower_reference", "account_reference")}
    if borrower_reference:
        payload.setdefault("borrower_reference", borrower_reference)
    return lender_id, borrower_reference, account_reference, payload


def _receive_lender_push(data, lender=None, headers=None):
    """Shared implementation for every LENDER -> Central push endpoint."""
    lender_id, borrower_reference, account_reference, payload = _normalize_lender_push(data)
    headers = headers or {}
    # Some lender integrations put the sender identity in a header rather than
    # in every JSON record. This is also useful while migrating old clients.
    if not lender_id:
        get_header = getattr(headers, "get", lambda _name, _default="": _default)
        lender_id = str(
            get_header("X-Lender-ID") or get_header("X-Lender-Id") or ""
        ).strip() or None
    if lender is not None and lender_id and lender_id != lender.lender_id:
        return Response(
            {"detail": f"lender_id '{lender_id}' does not match URL lender '{lender.lender_id}'."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if lender is None:
        # `lender_id` is the public stable identifier. `id` is accepted as a
        # compatibility fallback because some clients accidentally sent the
        # Django primary key shown by the admin/API. Public IDs remain the
        # canonical value returned in every successful response.
        if lender_id:
            lender = Lender.objects.filter(lender_id__iexact=lender_id).first()
            if lender is None and str(lender_id).isdigit():
                lender = Lender.objects.filter(pk=int(lender_id)).first()
        # If the body/header omitted the ID, a valid API key is an unambiguous
        # sender identity. This keeps key-authenticated legacy clients working.
        if lender is None and not lender_id:
            key = _lender_api_key_from_headers(headers)
            if key:
                candidates = [obj for obj in Lender.objects.exclude(api_key_hash="") if obj.check_api_key(key)]
                if len(candidates) == 1:
                    lender = candidates[0]
                    lender_id = lender.lender_id
        if lender is None and not lender_id:
            return Response(
                {"detail": "lender_id is required. Send it in JSON as lender_id, in X-Lender-ID, or use a registered X-API-Key."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if lender is None:
            return Response(
                {"detail": f"Lender '{lender_id}' is not registered. Use the exact lender_id returned by GET /api/lenders/."},
                status=status.HTTP_404_NOT_FOUND,
            )
        lender_id = lender.lender_id
    if not isinstance(payload, dict) or not payload:
        return Response({"detail": "payload must be a non-empty JSON object."}, status=status.HTTP_400_BAD_REQUEST)
    if not borrower_reference:
        return Response({"detail": "borrower_reference is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not isinstance(payload.get("loans", []), list):
        return Response({"detail": "payload.loans must be a list."}, status=status.HTTP_400_BAD_REQUEST)

    unauthorized = _check_lender_key(headers or {}, lender)
    if unauthorized is not None:
        return unauthorized

    exchange = record_exchange(
        system=DataExchange.System.LENDER, direction=DataExchange.Direction.PUSH,
        operation="receive_lender_data", lender=lender,
        fields_sent=list(payload.keys()), payload={"lender_id": lender.lender_id,
                                                    "borrower_reference": borrower_reference,
                                                    **payload},
    )
    try:
        profile = merge_vendor_borrower_data(
            lender=lender, borrower_reference=borrower_reference, payload=payload,
            account_reference=account_reference,
        )
    except ValidationError as exc:
        exchange.status = DataExchange.Status.FAILED
        exchange.error_message = str(exc.detail if hasattr(exc, "detail") else exc)
        exchange.save(update_fields=("status", "error_message", "updated_at"))
        return Response({"detail": exchange.error_message}, status=status.HTTP_400_BAD_REQUEST)

    loans_received = payload.get("loans", [])
    repayments_received = sum(len(loan.get("repayments", []) or []) for loan in loans_received if isinstance(loan, dict))
    tx_summary = summarize_transactions(payload)
    exchange.status = DataExchange.Status.COMPLETED
    exchange.borrower = profile.borrower
    exchange.response = {
        "borrower_reference": borrower_reference,
        "loans_received": len(loans_received),
        "repayments_received": repayments_received,
        "transaction_count": tx_summary["count"],
        "transaction_total_amount": tx_summary["total_amount"],
    }
    exchange.save(update_fields=("status", "borrower", "response", "updated_at"))
    borrower_data = CompactUnifiedBorrowerSerializer(profile.borrower).data
    return Response({
        "status": "COMPLETED",
        "exchange_id": exchange.id,
        "lender_id": lender.lender_id,
        "lender": lender.institution_name,
        "borrower_reference": borrower_reference,
        "summary": {
            "loans_received": len(loans_received),
            "repayments_received": repayments_received,
            "transaction_count": tx_summary["count"],
            "transaction_total_amount": tx_summary["total_amount"],
            "transaction_currency": tx_summary["currency"],
            "income_count": tx_summary["income_count"],
            "income_total_amount": tx_summary["income_total_amount"],
            "total_loans_for_borrower": profile.borrower.loans.count(),
            "active_loans": profile.active_loans,
            "total_outstanding_debt": str(profile.total_outstanding_debt),
        },
        "borrower": borrower_data,
    }, status=status.HTTP_201_CREATED)


class LenderViewSet(viewsets.ModelViewSet):
    queryset = Lender.objects.all()
    serializer_class = LenderSerializer

    def create(self, request, *args, **kwargs):
        """Register a lender: assigns the lender_id record plus a fresh API key.

        The plaintext `api_key` is returned ONLY here — store it now, it is
        never shown or stored again (only its hash is kept).
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lender = serializer.save()
        raw_key = lender.issue_api_key()
        data = self.get_serializer(lender).data
        data["api_key"] = raw_key
        data["api_key_notice"] = "Store this key now — it is shown only once."
        headers = self.get_success_headers(serializer.data)
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        """Save lender changes; auto-issue a key when the lender has none yet.

        Existing (legacy) lenders get their key on first save — shown once in
        the response, exactly like registration. Saving never rotates a key
        that already exists; use regenerate-key for rotation.
        """
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        lender = serializer.save()
        data = self.get_serializer(lender).data
        if not lender.api_key_hash:
            data["api_key"] = lender.issue_api_key()
            data["api_key_notice"] = "An API key was auto-issued on save — store it now, it is shown only once."
        return Response(data)

    @action(detail=True, methods=["post"], url_path="regenerate-key")
    def regenerate_key(self, request, pk=None):
        """Revoke the current key and issue a new one (plaintext shown once)."""
        lender = self.get_object()
        raw_key = lender.issue_api_key()
        return Response({
            "lender_id": lender.lender_id,
            "api_key_prefix": lender.api_key_prefix,
            "api_key": raw_key,
            "warning": "Store this key now — it is shown only once. The previous key is revoked.",
        })

    @action(detail=True, methods=["post"], url_path="receive-data")
    def receive_data(self, request, pk=None):
        """Receive a lender push on the lender's own URL.

        POST /api/lenders/{pk}/receive-data/
        Headers: X-API-Key: <key> (required when the lender has a key).
        Body: full lender contract, with or without a ``payload`` wrapper.
        ``lender_id`` in the body is optional here (URL identifies the lender)
        but when present it must match the URL lender.
        """
        lender = self.get_object()
        return _receive_lender_push(request.data, lender=lender, headers=request.headers)

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
            return Response(CompactUnifiedBorrowerSerializer(profile.borrower).data)
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
            return CompactUnifiedBorrowerSerializer
        if self.action == "list":
            return CompactBorrowerSerializer
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
        serializer = CompactUnifiedBorrowerSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="pull-from-all-lenders")
    def pull_from_all_lenders(self, request):
        """Pull a borrower from every lender; the caller never chooses a lender."""
        borrower_reference = str(request.data.get("borrower_reference") or "").strip()
        if not borrower_reference:
            return Response({"detail": "borrower_reference is required."}, status=status.HTTP_400_BAD_REQUEST)

        batch_reference = uuid.uuid4()
        successful, failed, results = [], [], []
        # Do not block an assessment on lenders already known to be offline.
        # DEGRADED remains eligible because it may still return this borrower.
        lenders = list(
            Lender.objects.filter(
                api_status__in=(Lender.Status.CONNECTED, Lender.Status.DEGRADED),
            ).exclude(api_base_url="")
        )
        exchanges = {}
        for lender in lenders:
            exchanges[lender.id] = record_exchange(
                system=DataExchange.System.LENDER, direction=DataExchange.Direction.PULL,
                operation="pull_borrower_data_all_lenders", lender=lender,
                batch_reference=batch_reference,
                fields_sent=["borrower_reference"], payload={"borrower_reference": borrower_reference},
            )

        def fetch_lender_payload(lender):
            query = {'borrower_reference': borrower_reference}
            # Preserve a lender_name hint embedded in the configured base URL.
            parsed = urlsplit(lender.api_base_url)
            if parsed.query:
                query.update(dict(parse_qsl(parsed.query)))
            base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            url = f"{base.rstrip('/')}/borrowers?{urlencode(query)}"
            return _get_json(url)

        fetched, fetch_errors = {}, {}
        # Network waits happen concurrently; database merges below remain
        # ordered and isolated so the unified borrower stays deterministic.
        with ThreadPoolExecutor(max_workers=max(1, min(16, len(lenders)))) as pool:
            futures = {pool.submit(fetch_lender_payload, lender): lender for lender in lenders}
            for future in as_completed(futures):
                lender = futures[future]
                try:
                    fetched[lender.id] = future.result()
                except Exception as exc:
                    fetch_errors[lender.id] = exc

        for lender in lenders:
            exchange = exchanges[lender.id]
            try:
                if lender.id in fetch_errors:
                    raise fetch_errors[lender.id]
                payload = fields_for_destination(fetched[lender.id], "lender")
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
            "borrower": CompactUnifiedBorrowerSerializer(borrower).data,
            "pulled_from": successful,
            "failed": failed,
            "pull_reference": str(batch_reference),
            "status": batch_status,
            "total_lenders": total,
            "successful_lenders": len(successful),
            "failed_lenders": len(failed),
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
        unauthorized = _check_lender_key(request.headers, lender)
        if unauthorized is not None:
            return unauthorized
        profile = merge_vendor_borrower_data(
            lender=lender,
            borrower_reference=borrower_reference,
            payload=payload,
            account_reference=request.data.get("account_reference") or payload.get("account_reference"),
        )
        return Response(CompactUnifiedBorrowerSerializer(profile.borrower).data, status=status.HTTP_200_OK)

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
        """Broadcast the combined AI + blockchain results to every linked lender.

        Every broadcast carries both stored results when they exist
        (``results.ai`` / ``results.blockchain``); ``result`` mirrors the most
        recent one for consumers that read a single object. A custom ``payload``
        is still honored verbatim for exceptional, caller-defined broadcasts.
        """
        borrower = self.get_object()
        result_type = request.data.get("result_type") or "CREDIT_RESULT"
        result_payload = request.data.get("payload")
        if isinstance(result_payload, dict):
            # Caller-defined broadcast: keep the classic single-result envelope.
            result_payload = {"borrower_reference": borrower.borrower_reference,
                              "result_type": result_type, "result": result_payload}
        else:
            requested_reference = str(request.data.get("assessment_reference") or "").strip()
            assessments = Assessment.objects.filter(borrower=borrower)
            if requested_reference:
                latest_assessment = assessments.filter(assessment_reference=requested_reference).first()
                if latest_assessment is None:
                    return Response(
                        {"detail": f"Assessment '{requested_reference}' does not belong to borrower '{borrower.borrower_reference}'."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
            else:
                latest_assessment = assessments.order_by("-created_at").first()
            # Both engine results must come from the same assessment. This is
            # important when a borrower has been assessed more than once.
            ai = (AIReputationResult.objects.filter(assessment=latest_assessment)
                  .select_related("assessment").first()) if latest_assessment else None
            blockchain = (SmartContractResult.objects.filter(assessment=latest_assessment)
                          .select_related("assessment").first()) if latest_assessment else None
            if ai is None and blockchain is None:
                return Response(
                    {"detail": "No AI or blockchain result exists for this borrower. Score first, then broadcast."},
                    status=status.HTTP_409_CONFLICT,
                )
            latest = max((r for r in (ai, blockchain) if r is not None), key=lambda r: r.created_at)
            latest_is_ai = latest is ai
            result_payload = {
                "borrower_reference": borrower.borrower_reference,
                "result_type": result_type,
                "assessment_reference": latest_assessment.assessment_reference if latest_assessment else None,
                # Backwards-compatible single result: the most recently generated score.
                "result": {
                    "kind": "AI_REPUTATION" if latest_is_ai else "BLOCKCHAIN_SCORE",
                    "generated_at": latest.created_at.isoformat(),
                    **(AIReputationResultSerializer(ai).data if latest_is_ai else SmartContractResultSerializer(blockchain).data),
                },
                # Combined payload: both engines, whichever exist.
                "results": {
                    "ai": AIReputationResultSerializer(ai).data if ai else None,
                    "blockchain": SmartContractResultSerializer(blockchain).data if blockchain else None,
                },
            }
        results = []
        sent_to = set()
        for account in borrower.accounts.select_related("lender").all():
            lender = account.lender
            if lender.id in sent_to:
                continue
            sent_to.add(lender.id)
            # Per-lender payload: lenders match results to their own customer by
            # the id recorded on the account (e.g. 002), so it becomes
            # borrower_reference; the central reference rides along for audit.
            if account.customer_id:
                per_lender_payload = {
                    **result_payload,
                    "borrower_reference": account.customer_id,
                    "central_borrower_reference": borrower.borrower_reference,
                }
            else:
                per_lender_payload = result_payload
            # The logged payload is exactly what goes on the wire to the lender.
            exchange = record_exchange(system=DataExchange.System.LENDER, direction=DataExchange.Direction.PUSH,
                                       operation="broadcast_credit_result", borrower=borrower, lender=lender,
                                       fields_sent=list(per_lender_payload.keys()),
                                       payload=per_lender_payload)
            try:
                response = _post_json(
                    request.data.get("target_url") or lender_broadcast_url(lender.api_base_url),
                    exchange.payload,
                    # Keys are only sent when REQUIRE_API_KEYS=true — same
                    # network by default means no credentials on the wire.
                    headers={"X-API-Key": lender.broadcast_api_key} if api_keys_required() and lender.broadcast_api_key else None,
                )
                exchange.status, exchange.response = DataExchange.Status.COMPLETED, response
                exchange.save(update_fields=("status", "response", "updated_at"))
                results.append({"lender": lender.institution_name, "status": "COMPLETED", "response": response})
            except ExternalServiceUnavailable as exc:
                exchange.status, exchange.error_message = DataExchange.Status.FAILED, str(exc)
                exchange.save(update_fields=("status", "error_message", "updated_at"))
                results.append({"lender": lender.institution_name, "status": "FAILED", "detail": str(exc)})
        return Response({"borrower_reference": borrower.borrower_reference, "result_type": result_type, "broadcasts": results})


class LenderDataReceiveView(APIView):
    """Primary LENDER -> Central push endpoint.

    POST /api/lender-data/receive/
    Body (wrapped)::

        {
          "lender_id": "LDR-NMB-02",
          "borrower_reference": 1001,
          "account_reference": 3001,
          "payload": { ...full lender contract (LENDER_SUBSYSTEM_README.md)... }
        }

    A flat contract (lender fields at top level + ``lender_id``) is also
    accepted. The payload is validated, merged into the unified borrower
    (Borrower + Account + Loans + Repayments + FinancialProfile), audited as a
    ``DataExchange`` (system=LENDER, direction=PUSH, operation=receive_lender_data)
    and the merged borrower is returned with ``201``.

    Transaction volume stays small: lenders should send aggregates
    (``transaction_count`` / ``transaction_total_amount`` / ``income_count`` /
    ``income_total_amount``, optionally nested under ``transaction_summary``)
    instead of full ``transactions`` rows — see services.summarize_transactions.
    """

    serializer_class = LenderDataReceiveSerializer

    def post(self, request):
        return _receive_lender_push(request.data, headers=request.headers)


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


class AssessmentViewSet(
    mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin,
    ImmutableDeleteGuardMixin, viewsets.ReadOnlyModelViewSet,
):
    queryset = Assessment.objects.select_related("borrower")
    serializer_class = AssessmentSerializer
    lookup_field = "assessment_reference"
    http_method_names = ("get", "post", "patch", "delete", "head", "options")

    def create(self, request, *args, **kwargs):
        """Open an assessment on merged lender data.

        POST /api/assessments/ {"borrower_reference": "1001"}
        The borrower must already exist (pull or receive lender data first).
        A scoring profile is synthesized from the merged records when the
        borrower has none, so Send-to-AI / Send-to-blockchain work directly.
        """
        reference = str(request.data.get("borrower_reference") or "").strip()
        if not reference:
            return Response({"detail": "borrower_reference is required."}, status=status.HTTP_400_BAD_REQUEST)
        borrower = Borrower.objects.filter(borrower_reference=reference).first()
        if borrower is None:
            return Response(
                {"detail": f"Borrower '{reference}' not found. Pull or receive lender data first."},
                status=status.HTTP_404_NOT_FOUND,
            )
        assessment = Assessment.objects.create(
            borrower=borrower, assessment_reference=f"TMP-{uuid.uuid4().hex}",
        )
        assessment.assessment_reference = f"ASM-{timezone.now():%Y}-{assessment.id:04d}"
        assessment.save(update_fields=("assessment_reference", "updated_at"))
        ensure_credit_profile(borrower)
        return Response(AssessmentSerializer(assessment).data, status=status.HTTP_201_CREATED)

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
    def ai_result(self, request, assessment_reference=None, pk=None):
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
        try:
            profile = ensure_credit_profile(assessment.borrower)
        except Exception as exc:
            raise ExternalServiceUnavailable("Credit profile is unavailable.") from exc
        features = {feature.name: float(feature.value) for feature in profile.features.all()}
        return fields_for_destination(features, destination)

    def _blockchain_dimensions(self, assessment):
        try:
            profile = ensure_credit_profile(assessment.borrower)
        except Exception as exc:
            raise ExternalServiceUnavailable("Credit profile is unavailable.") from exc
        features = {feature.name: float(feature.value) for feature in profile.features.all()}
        return blockchain_dimensions(features=features, borrower=assessment.borrower)

    @action(detail=True, methods=["post"], url_path="ai-reputation")
    def ai_reputation(self, request, assessment_reference=None, pk=None):
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
    def blockchain_score(self, request, assessment_reference=None, pk=None):
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


class DataExchangeViewSet(
    mixins.UpdateModelMixin, mixins.DestroyModelMixin, ImmutableDeleteGuardMixin,
    viewsets.ReadOnlyModelViewSet,
):
    queryset = DataExchange.objects.select_related("borrower", "lender", "assessment", "policy").all()
    serializer_class = DataExchangeSerializer
    http_method_names = ("get", "patch", "delete", "head", "options")

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


import random


def _numeric_id(value, digits=6) -> int:
    """Deterministic numeric id (no letter prefixes) from any seed string."""
    return abs(hash(str(value))) % (10 ** digits)


def _zero_padded_customer_id(borrower_reference: str) -> str:
    """Customer id shown as 001, 002, 003 — plain digits, zero-padded."""
    digits = "".join(ch for ch in str(borrower_reference) if ch.isdigit())
    return f"{int(digits[-3:] or '0'):03d}"


class MockLenderDataView(APIView):
    """Development stand-in for a real lender Open-Banking API.

    GET /api/mock-lender/borrowers?borrower_reference=1001
    Returns a normalized borrower payload so "Pull from all lenders" has a
    live target. Data varies deterministically per lender name + borrower.
    """

    def get(self, request, base=None):
        borrower_reference = str(request.query_params.get("borrower_reference") or "").strip()
        if not borrower_reference:
            return Response({"detail": "borrower_reference is required."}, status=status.HTTP_400_BAD_REQUEST)
        lender_name = request.query_params.get("lender_name") or base or "MOCK"
        seed = f"{lender_name}:{borrower_reference}"
        rng = random.Random(seed)
        rng.seed(seed)
        age = rng.randint(23, 55)
        genders = ["MALE", "FEMALE"]
        employments = ["EMPLOYED", "SELF_EMPLOYED", "BUSINESS_OWNER"]
        income = rng.choice([4_500_000, 7_300_000, 9_400_000, 12_200_000, 14_800_000, 18_500_000])
        transaction_frequency = rng.randint(18, 70)
        income_frequency = max(2, transaction_frequency // rng.choice([8, 10, 12]))
        return Response({
            "borrower_reference": int(borrower_reference) if borrower_reference.isdigit() else borrower_reference,
            "customer_id": _zero_padded_customer_id(borrower_reference),
            "account_reference": _numeric_id(seed + "acc", 7),
            "account_name": f"{lender_name} account {borrower_reference}",
            "age": age,
            "gender": rng.choice(genders),
            "employment_status": rng.choice(employments),
            "income": income,
            "transaction_frequency": transaction_frequency,
            "income_frequency": income_frequency,
            "savings": income * rng.choice([0.05, 0.08, 0.12, 0.18]),
            "loans": [
                {
                    "loan_id": _numeric_id(seed + str(i), 6),
                    "loan_amount": income * rng.choice([0.5, 1.2, 2.0]),
                    "loan_duration_months": rng.choice([6, 12, 24, 36]),
                    "interest_rate": rng.choice([12.5, 15.0, 18.25, 21.0]),
                    "outstanding_balance": income * rng.choice([0, 0.3, 0.7, 1.1]),
                    "status": rng.choices(["ACTIVE", "COMPLETED"], weights=[55, 45])[0],
                    "repayments": [
                        {
                            "repayment_amount": income * 0.08,
                            "days_overdue": rng.choice([0, 0, 0, 2, 5, 30]),
                            "missed_payments": rng.choice([0, 0, 0, 1]),
                            "late_payments": rng.choice([0, 0, 1, 2]),
                            "default_status": "NONE",
                        }
                        for _ in range(rng.randint(3, 10))
                    ],
                }
                for i in range(rng.randint(1, 4))
            ],
        })


class MockLenderBroadcastView(APIView):
    """Development stand-in for a lender system receiving credit results.

    POST /api/mock-lender/<name>/broadcast — acknowledges any JSON payload.
    """

    def post(self, request, base=None):
        return Response({
            "received": True,
            "lender_system": base or "MOCK",
            "result_type": request.data.get("result_type", "UNKNOWN"),
            "score": (request.data.get("result") or {}).get("credit_score"),
            "processed_at": timezone.now().isoformat(),
        })


class AIReputationResultViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AIReputationResult.objects.select_related("assessment").all()
    serializer_class = AIReputationResultSerializer
    http_method_names = ("get", "patch", "head", "options")

    def perform_update(self, serializer):
        instance = serializer.save()
        self._sync_assessment(instance)

    def _sync_assessment(self, result):
        """Mirror editable AI fields onto the parent assessment row."""
        assessment = result.assessment
        updated = False
        for field in ("reputation", "risk_level", "behavior_summary", "model_version"):
            new_value = getattr(result, field)
            if getattr(assessment, field) != new_value:
                setattr(assessment, field, new_value)
                updated = True
        if updated:
            assessment.save(update_fields=("reputation", "risk_level", "behavior_summary", "model_version", "updated_at"))


class SmartContractResultViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SmartContractResult.objects.select_related("assessment").all()
    serializer_class = SmartContractResultSerializer
    http_method_names = ("get", "patch", "head", "options")


class BlockchainTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BlockchainTransaction.objects.select_related("assessment").all()
    serializer_class = BlockchainTransactionSerializer
    http_method_names = ("get", "patch", "head", "options")


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
    # Per-stage record cap for the Overview tabs — the dashboard stays light
    # even when the exchange log grows into the thousands.
    STAGE_LIMIT = 100

    def get(self, request):
        # Pipeline stage records for the Overview inner tabs. Each stage shows
        # the raw records that flowed through that pipeline step.
        exchange_qs = DataExchange.objects.select_related("borrower", "lender", "assessment", "policy")
        lender_exchanges = exchange_qs.filter(
            system=DataExchange.System.LENDER,
        ).order_by("-created_at")[: self.STAGE_LIMIT]
        ai_exchanges = exchange_qs.filter(
            system=DataExchange.System.AI,
        ).order_by("-created_at")[: self.STAGE_LIMIT]
        blockchain_exchanges = exchange_qs.filter(
            system=DataExchange.System.BLOCKCHAIN,
        ).order_by("-created_at")[: self.STAGE_LIMIT]
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
            # Stage 1 — data received from lenders (push + pull exchanges).
            "lender_exchanges": DataExchangeSerializer(lender_exchanges, many=True).data,
            # Stage 2 — data assessed before any engine is called.
            "assessed_data": AssessmentSerializer(
                Assessment.objects.select_related("borrower").order_by("-created_at"), many=True
            ).data,
            # Stage 3 — payload sent to the AI engine / Stage 5 — payload sent
            # to the blockchain engine (exchange request payloads).
            "ai_exchanges": DataExchangeSerializer(ai_exchanges, many=True).data,
            "blockchain_exchanges": DataExchangeSerializer(blockchain_exchanges, many=True).data,
            # Stage 4 — results returned by the AI engine.
            "ai_results": AIReputationResultSerializer(
                AIReputationResult.objects.select_related("assessment").order_by("-created_at")[: self.STAGE_LIMIT], many=True
            ).data,
            # Stage 6 — data received back from the blockchain (scores + txs).
            "smart_contract_results": SmartContractResultSerializer(
                SmartContractResult.objects.select_related("assessment").order_by("-created_at")[: self.STAGE_LIMIT], many=True
            ).data,
            "blockchain_transactions": BlockchainTransactionSerializer(
                BlockchainTransaction.objects.select_related("assessment").order_by("-created_at")[: self.STAGE_LIMIT], many=True
            ).data,
        })

import pandas as pd

class PredictCreditRiskView(APIView):
    """Direct scoring with the trained model on raw CSV-schema loan applications.

    Same model file as the AI reputation engine (see services.get_credit_risk_model),
    but here the caller supplies the 11 model columns directly instead of the
    central borrower record. Response shape is unchanged.
    """
    def post(self, request):
        from .services import CREDIT_RISK_MODEL_FEATURES, get_credit_risk_model
        data = request.data
        try:
            df = pd.DataFrame([{name: data.get(name) for name in CREDIT_RISK_MODEL_FEATURES}])

            # Numeric columns need to be numeric
            numeric_cols = ['person_age', 'person_income', 'person_emp_length', 'loan_amnt', 'loan_int_rate', 'loan_percent_income', 'cb_person_cred_hist_length']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            model = get_credit_risk_model()

            prediction = model.predict(df)
            result = int(prediction[0])

            message = "Approved" if result == 0 else "High Risk of Default"

            return Response({"prediction": result, "message": message}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
