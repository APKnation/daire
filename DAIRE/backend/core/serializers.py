from django.utils import timezone
from django.contrib.admin.models import LogEntry
from rest_framework import serializers
from .models import (
    AIReputationResult, Assessment, BlockchainTransaction, Borrower, BorrowerAccount, BorrowerFinancialProfile,
    BorrowerLoan, Consent, CreditFeature, CreditProfile, IntegrationRequest, Lender,
    RepaymentRecord, SmartContractResult, DataExchange, DataRoutingPolicy,
)


class LenderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lender
        exclude = ("api_key_hash", "broadcast_api_key")  # secrets never serialize
        read_only_fields = ("created_at", "updated_at", "api_key_prefix")


class BorrowerSerializer(serializers.ModelSerializer):
    financial_profile = serializers.SerializerMethodField()
    source_lenders = serializers.SerializerMethodField()

    class Meta:
        model = Borrower
        fields = ("id", "borrower_reference", "nida_number", "is_active", "customer_id", "age", "gender", "employment_status", "income", "business_information", "account_information", "data_conflicts", "financial_profile", "source_lenders", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")

    def get_financial_profile(self, obj):
        profile = getattr(obj, "financial_profile", None)
        if profile is None:
            return None
        return BorrowerFinancialProfileSerializer(profile).data

    def get_source_lenders(self, obj):
        return list(obj.accounts.values_list("lender__institution_name", flat=True).distinct())


class BorrowerAccountSerializer(serializers.ModelSerializer):
    lender_name = serializers.CharField(source="lender.institution_name", read_only=True)

    class Meta:
        model = BorrowerAccount
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class BorrowerLoanSerializer(serializers.ModelSerializer):
    lender_name = serializers.CharField(source="lender.institution_name", read_only=True)
    repayments = serializers.SerializerMethodField()

    class Meta:
        model = BorrowerLoan
        fields = ("id", "loan_id", "lender", "lender_name", "loan_amount", "loan_date", "loan_duration_months", "interest_rate", "outstanding_balance", "status", "repayments")
        read_only_fields = ("created_at", "updated_at")

    def get_repayments(self, obj):
        return RepaymentRecordSerializer(obj.repayments.all(), many=True).data


class RepaymentRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RepaymentRecord
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class BorrowerFinancialProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = BorrowerFinancialProfile
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class CompactFinancialProfileSerializer(serializers.ModelSerializer):
    """Scoring summary only; omit internal cash-flow detail from pull APIs."""

    class Meta:
        model = BorrowerFinancialProfile
        fields = (
            "transaction_frequency", "income_frequency", "savings",
            "active_loans", "total_outstanding_debt", "monthly_repayment",
            "previous_loans", "debt_to_income_ratio",
        )


class CompactBorrowerAccountSerializer(serializers.ModelSerializer):
    lender_name = serializers.CharField(source="lender.institution_name", read_only=True)

    class Meta:
        model = BorrowerAccount
        fields = ("id", "lender", "lender_name", "account_reference", "account_name", "customer_id")


class CompactRepaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RepaymentRecord
        fields = (
            "id", "repayment_amount", "repayment_date", "due_date",
            "days_overdue", "missed_payments", "late_payments", "default_status",
        )


class CompactBorrowerLoanSerializer(serializers.ModelSerializer):
    lender_name = serializers.CharField(source="lender.institution_name", read_only=True)
    repayments = CompactRepaymentSerializer(many=True, read_only=True)

    class Meta:
        model = BorrowerLoan
        fields = (
            "id", "loan_id", "lender", "lender_name", "loan_amount", "loan_date",
            "loan_duration_months", "interest_rate", "outstanding_balance", "status", "repayments",
        )


class CompactBorrowerSerializer(serializers.ModelSerializer):
    financial_profile = serializers.SerializerMethodField()
    source_lenders = serializers.SerializerMethodField()

    class Meta:
        model = Borrower
        fields = (
            "id", "borrower_reference", "nida_number", "is_active", "customer_id", "age", "gender",
            "employment_status", "income", "source_lenders", "financial_profile",
        )

    def get_financial_profile(self, obj):
        profile = getattr(obj, "financial_profile", None)
        return CompactFinancialProfileSerializer(profile).data if profile else None

    def get_source_lenders(self, obj):
        return list(obj.accounts.values_list("lender__institution_name", flat=True).distinct())


class CompactUnifiedBorrowerSerializer(CompactBorrowerSerializer):
    accounts = CompactBorrowerAccountSerializer(many=True, read_only=True)
    loans = CompactBorrowerLoanSerializer(many=True, read_only=True)

    class Meta(CompactBorrowerSerializer.Meta):
        fields = CompactBorrowerSerializer.Meta.fields + ("accounts", "loans")


class ConsentSerializer(serializers.ModelSerializer):
    borrower_id = serializers.IntegerField(source="borrower.id", read_only=True)
    lender_id = serializers.IntegerField(source="lender.id", read_only=True)
    borrower_reference = serializers.CharField(source="borrower.borrower_reference", read_only=True)
    lender_name = serializers.CharField(source="lender.institution_name", read_only=True)

    class Meta:
        model = Consent
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")

    def validate(self, attrs):
        if attrs.get("expires_at") and attrs.get("granted_at") and attrs["expires_at"] <= attrs["granted_at"]:
            raise serializers.ValidationError("expires_at must be after granted_at.")
        return attrs


class IntegrationRequestSerializer(serializers.ModelSerializer):
    lender_id = serializers.CharField(source="lender.lender_id", read_only=True)
    borrower_reference = serializers.CharField(source="borrower.borrower_reference", read_only=True)

    class Meta:
        model = IntegrationRequest
        fields = ("request_reference", "lender_id", "borrower_reference", "status", "error_message", "raw_payload", "created_at")
        read_only_fields = fields


class AssessmentSerializer(serializers.ModelSerializer):
    borrower_reference = serializers.CharField(source="borrower.borrower_reference", read_only=True)

    class Meta:
        model = Assessment
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "borrower_reference")


class CreditProfileSerializer(serializers.ModelSerializer):
    borrower_reference = serializers.CharField(source="borrower.borrower_reference", read_only=True)

    class Meta:
        model = CreditProfile
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class CreditFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditFeature
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class AIReputationResultSerializer(serializers.ModelSerializer):
    assessment_reference = serializers.CharField(source="assessment.assessment_reference", read_only=True)
    borrower_name = serializers.SerializerMethodField()
    borrower_reference = serializers.CharField(source="assessment.borrower.borrower_reference", read_only=True)
    score_explanation = serializers.SerializerMethodField()
    # Pre-flattened key fields for quick frontend rendering without raw_result traversal
    decision = serializers.SerializerMethodField()
    credit_grade = serializers.SerializerMethodField()
    credit_tier = serializers.SerializerMethodField()
    nmb_credit_score = serializers.SerializerMethodField()
    concordance = serializers.SerializerMethodField()
    ensemble_pd = serializers.SerializerMethodField()
    ml_pd = serializers.SerializerMethodField()
    nmb_pd = serializers.SerializerMethodField()
    recommended_credit_limit = serializers.SerializerMethodField()
    recommended_apr = serializers.SerializerMethodField()
    expected_loss = serializers.SerializerMethodField()
    actionable_guidance = serializers.SerializerMethodField()
    strengths = serializers.SerializerMethodField()
    risk_factors = serializers.SerializerMethodField()
    ml_weight = serializers.SerializerMethodField()
    nmb_weight = serializers.SerializerMethodField()
    history_band = serializers.SerializerMethodField()

    class Meta:
        model = AIReputationResult
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")

    def _raw(self, obj):
        return obj.raw_result if isinstance(obj.raw_result, dict) else {}

    def get_borrower_name(self, obj):
        try:
            return obj.assessment.borrower.name or obj.assessment.borrower.borrower_reference
        except Exception:
            return None

    def get_score_explanation(self, obj):
        try:
            return obj.assessment.score_explanation or []
        except Exception:
            return []

    def get_decision(self, obj):
        return self._raw(obj).get("decision")

    def get_credit_grade(self, obj):
        return self._raw(obj).get("credit_grade")

    def get_credit_tier(self, obj):
        return self._raw(obj).get("credit_tier")

    def get_nmb_credit_score(self, obj):
        return (self._raw(obj).get("nmb_metrics") or {}).get("credit_score")

    def get_concordance(self, obj):
        return (self._raw(obj).get("consensus_metrics") or {}).get("concordance")

    def get_ensemble_pd(self, obj):
        return self._raw(obj).get("default_probability")

    def get_ml_pd(self, obj):
        return (self._raw(obj).get("sklearn_metrics") or {}).get("default_probability")

    def get_nmb_pd(self, obj):
        return (self._raw(obj).get("nmb_metrics") or {}).get("default_probability")

    def get_recommended_credit_limit(self, obj):
        return (self._raw(obj).get("pricing_capacity") or {}).get("recommended_credit_limit")

    def get_recommended_apr(self, obj):
        return (self._raw(obj).get("pricing_capacity") or {}).get("recommended_apr")

    def get_expected_loss(self, obj):
        return (self._raw(obj).get("basel_metrics") or {}).get("expected_loss")

    def get_actionable_guidance(self, obj):
        return self._raw(obj).get("actionable_guidance", [])

    def get_strengths(self, obj):
        return self._raw(obj).get("strengths", [])

    def get_risk_factors(self, obj):
        return self._raw(obj).get("risk_factors", [])

    def get_ml_weight(self, obj):
        return (self._raw(obj).get("consensus_metrics") or {}).get("ml_weight")

    def get_nmb_weight(self, obj):
        return (self._raw(obj).get("consensus_metrics") or {}).get("nmb_weight")

    def get_history_band(self, obj):
        return (self._raw(obj).get("consensus_metrics") or {}).get("history_band")


class SmartContractResultSerializer(serializers.ModelSerializer):
    assessment_reference = serializers.CharField(source="assessment.assessment_reference", read_only=True)
    transaction_hash = serializers.CharField(source="assessment.blockchain_transaction_hash", read_only=True)
    block_number = serializers.IntegerField(source="assessment.blockchain_block_number", read_only=True)
    risk_band = serializers.SerializerMethodField()

    class Meta:
        model = SmartContractResult
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")

    def get_risk_band(self, obj):
        raw = obj.raw_result if isinstance(obj.raw_result, dict) else {}
        nested = raw.get("data") if isinstance(raw.get("data"), dict) else {}
        return nested.get("riskBand") or raw.get("risk_band") or ""


class BlockchainTransactionSerializer(serializers.ModelSerializer):
    assessment_reference = serializers.CharField(source="assessment.assessment_reference", read_only=True)

    class Meta:
        model = BlockchainTransaction
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class UnifiedBorrowerSerializer(BorrowerSerializer):
    """The single borrower view assembled from every connected institution."""

    accounts = BorrowerAccountSerializer(many=True, read_only=True)
    loans = BorrowerLoanSerializer(many=True, read_only=True)

    class Meta(BorrowerSerializer.Meta):
        fields = BorrowerSerializer.Meta.fields + ("accounts", "loans")


class DataRoutingPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = DataRoutingPolicy
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class DataExchangeSerializer(serializers.ModelSerializer):
    borrower_reference = serializers.CharField(source="borrower.borrower_reference", read_only=True)
    lender_id = serializers.CharField(source="lender.lender_id", read_only=True)
    lender_name = serializers.CharField(source="lender.institution_name", read_only=True)
    assessment_reference = serializers.CharField(source="assessment.assessment_reference", read_only=True)

    class Meta:
        model = DataExchange
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "status", "response", "error_message")


class LenderDataReceiveSerializer(serializers.Serializer):
    """Payload a lender pushes to Central (LENDER -> Central, direction=PUSH).

    Accepts either a wrapped payload::

        {
          "lender_id": "LDR-NMB-02",
          "borrower_reference": "BRW-TZ-1001",
          "account_reference": "NMB-ACC-0001",   # optional
          "payload": { ...full lender contract... }
        }

    or a flat contract (lender fields at top level + ``lender_id``)::

        {
          "lender_id": "LDR-NMB-02",
          "borrower_reference": "BRW-TZ-1001",
          "customer_id": "NMB-CUST-0001",
          "loans": [...],
          ...
        }
    """

    lender_id = serializers.CharField(max_length=64)
    borrower_reference = serializers.CharField(max_length=64, required=False, allow_blank=True)
    account_reference = serializers.CharField(max_length=128, required=False, allow_blank=True)
    payload = serializers.DictField(required=False)

    def validate(self, attrs):
        payload = attrs.get("payload")
        if payload is not None and not isinstance(payload, dict):
            raise serializers.ValidationError({"payload": "payload must be a JSON object."})
        # borrower_reference may live top-level or inside payload.
        top_ref = (attrs.get("borrower_reference") or "").strip()
        inner_ref = str((payload or {}).get("borrower_reference") or "").strip() if payload else ""
        if not top_ref and not inner_ref:
            raise serializers.ValidationError(
                {"borrower_reference": "borrower_reference is required (top-level or inside payload)."}
            )
        if top_ref and inner_ref and top_ref != inner_ref:
            raise serializers.ValidationError(
                {"borrower_reference": "Top-level borrower_reference does not match payload.borrower_reference."}
            )
        attrs["borrower_reference"] = top_ref or inner_ref
        if payload is not None and "loans" in payload and not isinstance(payload["loans"], list):
            raise serializers.ValidationError({"payload": "payload.loans must be a list."})
        return attrs


class AdminLogEntrySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    model = serializers.CharField(source="content_type.model", read_only=True)
    app_label = serializers.CharField(source="content_type.app_label", read_only=True)

    class Meta:
        model = LogEntry
        fields = (
            "id", "action_time", "username", "app_label", "model", "object_id",
            "object_repr", "action_flag", "change_message",
        )
        read_only_fields = fields
