import uuid
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Lender(TimestampedModel):
    class Status(models.TextChoices):
        CONNECTED = "CONNECTED"
        DEGRADED = "DEGRADED"
        DISCONNECTED = "DISCONNECTED"

    lender_id = models.CharField(max_length=64, unique=True)
    institution_name = models.CharField(max_length=255)
    institution_type = models.CharField(max_length=100)
    api_base_url = models.URLField()
    api_status = models.CharField(max_length=20, choices=Status.choices, default=Status.DISCONNECTED)
    authentication_method = models.CharField(max_length=50, default="API_KEY")


class Borrower(TimestampedModel):
    borrower_reference = models.CharField(max_length=64, unique=True)


class Consent(TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE"
        EXPIRED = "EXPIRED"
        REVOKED = "REVOKED"

    consent_id = models.CharField(max_length=64, unique=True)
    borrower = models.ForeignKey(Borrower, on_delete=models.PROTECT, related_name="consents")
    lender = models.ForeignKey(Lender, on_delete=models.PROTECT, related_name="consents")
    purpose = models.CharField(max_length=255)
    granted_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    def is_valid(self):
        return self.status == self.Status.ACTIVE and self.expires_at > timezone.now()


class IntegrationRequest(TimestampedModel):
    class Status(models.TextChoices):
        RECEIVED = "RECEIVED"
        VALIDATED = "VALIDATED"
        REJECTED = "REJECTED"
        COMPLETED = "COMPLETED"

    request_reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    lender = models.ForeignKey(Lender, on_delete=models.PROTECT)
    borrower = models.ForeignKey(Borrower, on_delete=models.PROTECT)
    consent = models.ForeignKey(Consent, on_delete=models.PROTECT)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RECEIVED)
    error_message = models.TextField(blank=True)
    raw_payload = models.JSONField(default=dict)


class AuditLog(TimestampedModel):
    event_type = models.CharField(max_length=80)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    request_reference = models.UUIDField(null=True, blank=True)
    details = models.JSONField(default=dict)


class Assessment(TimestampedModel):
    assessment_reference = models.CharField(max_length=64, unique=True)
    borrower = models.ForeignKey(Borrower, on_delete=models.PROTECT)
    reputation = models.CharField(max_length=30, blank=True)
    reputation_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, validators=[MinValueValidator(0)])
    risk_level = models.CharField(max_length=20, blank=True)
    behavior_summary = models.TextField(blank=True)
    credit_score = models.PositiveSmallIntegerField(null=True)
    ruleset_version = models.CharField(max_length=64, blank=True)
    model_version = models.CharField(max_length=64, blank=True)
    blockchain_transaction_hash = models.CharField(max_length=255, blank=True)
    blockchain_block_number = models.PositiveBigIntegerField(null=True)
    verification_status = models.CharField(max_length=30, default="PENDING")


class CreditProfile(TimestampedModel):
    """Normalized, immutable input used by the scoring pipeline."""
    borrower = models.ForeignKey(Borrower, on_delete=models.PROTECT, related_name="credit_profiles")
    integration_request = models.OneToOneField(
        IntegrationRequest, on_delete=models.PROTECT, related_name="credit_profile",
        null=True, blank=True,
    )
    profile_data = models.JSONField(default=dict)
    source_version = models.CharField(max_length=64, default="1")


class CreditFeature(TimestampedModel):
    profile = models.ForeignKey(CreditProfile, on_delete=models.CASCADE, related_name="features")
    name = models.CharField(max_length=100)
    value = models.DecimalField(max_digits=20, decimal_places=8)
    feature_version = models.CharField(max_length=64, default="1")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("profile", "name"), name="unique_credit_feature"),
        ]


class AIReputationResult(TimestampedModel):
    assessment = models.OneToOneField(Assessment, on_delete=models.CASCADE, related_name="ai_reputation_result")
    reputation = models.CharField(max_length=30)
    score = models.DecimalField(max_digits=7, decimal_places=4, validators=[MinValueValidator(0)])
    risk_level = models.CharField(max_length=30, blank=True)
    behavior_summary = models.TextField(blank=True)
    model_version = models.CharField(max_length=64)
    raw_result = models.JSONField(default=dict)


class SmartContractResult(TimestampedModel):
    assessment = models.OneToOneField(Assessment, on_delete=models.CASCADE, related_name="smart_contract_result")
    credit_score = models.PositiveSmallIntegerField()
    ruleset_version = models.CharField(max_length=64)
    contract_address = models.CharField(max_length=255)
    raw_result = models.JSONField(default=dict)


class BlockchainTransaction(TimestampedModel):
    assessment = models.ForeignKey(Assessment, on_delete=models.PROTECT, related_name="blockchain_transactions")
    transaction_hash = models.CharField(max_length=255, unique=True)
    network = models.CharField(max_length=100)
    block_number = models.PositiveBigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=30, default="PENDING")
    verification_data = models.JSONField(default=dict)
