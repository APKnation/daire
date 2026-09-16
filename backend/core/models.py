import uuid
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
    is_active = models.BooleanField(default=True)
    customer_id = models.CharField(max_length=64, blank=True, default="")
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    employment_status = models.CharField(max_length=50, blank=True)
    income = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)
    business_information = models.JSONField(default=dict, blank=True)
    account_information = models.JSONField(default=dict, blank=True)


class BorrowerAccount(TimestampedModel):
    borrower = models.ForeignKey(Borrower, on_delete=models.PROTECT, related_name="accounts")
    lender = models.ForeignKey(Lender, on_delete=models.PROTECT, related_name="borrower_accounts")
    account_reference = models.CharField(max_length=128, blank=True, default="")
    account_name = models.CharField(max_length=255, blank=True, default="")
    customer_id = models.CharField(max_length=64, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("borrower", "lender", "account_reference"), name="unique_borrower_account_per_lender"),
        ]


class BorrowerLoan(TimestampedModel):
    borrower = models.ForeignKey(Borrower, on_delete=models.PROTECT, related_name="loans")
    lender = models.ForeignKey(Lender, on_delete=models.PROTECT, related_name="borrower_loans")
    source_account = models.ForeignKey(BorrowerAccount, on_delete=models.PROTECT, related_name="loans", null=True, blank=True)
    loan_id = models.CharField(max_length=128)
    loan_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    loan_date = models.DateField(null=True, blank=True)
    loan_duration_months = models.PositiveIntegerField(default=0)
    interest_rate = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    outstanding_balance = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    status = models.CharField(max_length=30, default="ACTIVE")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("borrower", "lender", "loan_id"), name="unique_borrower_loan_per_lender"),
        ]


class RepaymentRecord(TimestampedModel):
    borrower = models.ForeignKey(Borrower, on_delete=models.PROTECT, related_name="repayment_records")
    lender = models.ForeignKey(Lender, on_delete=models.PROTECT, related_name="repayment_records")
    loan = models.ForeignKey(BorrowerLoan, on_delete=models.CASCADE, related_name="repayments")
    repayment_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    repayment_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    days_overdue = models.PositiveIntegerField(default=0)
    missed_payments = models.PositiveIntegerField(default=0)
    late_payments = models.PositiveIntegerField(default=0)
    default_status = models.CharField(max_length=20, blank=True, default="")


class BorrowerFinancialProfile(TimestampedModel):
    borrower = models.OneToOneField(Borrower, on_delete=models.CASCADE, related_name="financial_profile")
    transaction_frequency = models.PositiveIntegerField(default=0)
    income_frequency = models.PositiveIntegerField(default=0)
    cash_flow_patterns = models.JSONField(default=dict, blank=True)
    savings = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    account_activity = models.JSONField(default=dict, blank=True)
    active_loans = models.PositiveIntegerField(default=0)
    total_outstanding_debt = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    monthly_repayment = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    previous_loans = models.PositiveIntegerField(default=0)
    debt_to_income_ratio = models.DecimalField(max_digits=9, decimal_places=4, default=0)


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
    value = models.DecimalField(max_digits=20, decimal_places=4)
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


class DataRoutingPolicy(TimestampedModel):
    """Controls which normalized fields may leave the central system."""

    policy_id = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    lender_fields = models.JSONField(default=list, blank=True)
    ai_fields = models.JSONField(default=list, blank=True)
    blockchain_fields = models.JSONField(default=list, blank=True)
    active = models.BooleanField(default=True)
    version = models.CharField(max_length=64, default="1")


class DataExchange(TimestampedModel):
    class System(models.TextChoices):
        LENDER = "LENDER"
        AI = "AI"
        BLOCKCHAIN = "BLOCKCHAIN"

    class Direction(models.TextChoices):
        PUSH = "PUSH"
        PULL = "PULL"

    class Status(models.TextChoices):
        STARTED = "STARTED"
        COMPLETED = "COMPLETED"
        FAILED = "FAILED"

    system = models.CharField(max_length=20, choices=System.choices)
    direction = models.CharField(max_length=10, choices=Direction.choices)
    operation = models.CharField(max_length=100)
    borrower = models.ForeignKey(Borrower, on_delete=models.PROTECT, null=True, blank=True, related_name="data_exchanges")
    lender = models.ForeignKey(Lender, on_delete=models.PROTECT, null=True, blank=True, related_name="data_exchanges")
    assessment = models.ForeignKey(Assessment, on_delete=models.PROTECT, null=True, blank=True, related_name="data_exchanges")
    policy = models.ForeignKey(DataRoutingPolicy, on_delete=models.PROTECT, null=True, blank=True, related_name="data_exchanges")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.STARTED)
    fields_sent = models.JSONField(default=list, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    response = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
