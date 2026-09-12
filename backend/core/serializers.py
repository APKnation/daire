from django.utils import timezone
from rest_framework import serializers
from .models import (
    AIReputationResult, Assessment, BlockchainTransaction, Borrower, BorrowerAccount, BorrowerFinancialProfile,
    BorrowerLoan, Consent, CreditFeature, CreditProfile, IntegrationRequest, Lender,
    RepaymentRecord, SmartContractResult, DataExchange, DataRoutingPolicy,
)


class LenderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lender
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class BorrowerSerializer(serializers.ModelSerializer):
    financial_profile = serializers.SerializerMethodField()
    source_lenders = serializers.SerializerMethodField()

    class Meta:
        model = Borrower
        fields = ("id", "borrower_reference", "customer_id", "age", "gender", "employment_status", "income", "business_information", "account_information", "financial_profile", "source_lenders", "created_at", "updated_at")
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
    class Meta:
        model = AIReputationResult
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class SmartContractResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmartContractResult
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class BlockchainTransactionSerializer(serializers.ModelSerializer):
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
    class Meta:
        model = DataExchange
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "status", "response", "error_message")
