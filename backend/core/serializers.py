from django.utils import timezone
from rest_framework import serializers
from .models import (
    AIReputationResult, Assessment, AuditLog, BlockchainTransaction, Borrower, Consent,
    CreditFeature, CreditProfile, IntegrationRequest, Lender, SmartContractResult,
)


class LenderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lender
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class BorrowerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Borrower
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


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = "__all__"
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "event_type",
            "actor",
            "request_reference",
            "details",
        )


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
