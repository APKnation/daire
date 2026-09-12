from django import forms
from django.contrib import admin

from .models import (
    AIReputationResult,
    Assessment,
    BlockchainTransaction,
    Borrower,
    BorrowerAccount,
    BorrowerFinancialProfile,
    BorrowerLoan,
    Consent,
    CreditFeature,
    CreditProfile,
    IntegrationRequest,
    Lender,
    RepaymentRecord,
    SmartContractResult,
    DataExchange,
    DataRoutingPolicy,
)


class BorrowerAdminForm(forms.ModelForm):
    class Meta:
        model = Borrower
        fields = ("borrower_reference",)
        labels = {"borrower_reference": "Borrower reference"}
        help_texts = {
            "borrower_reference": (
                "A unique ID used by the lender, for example: BORROWER-001. "
                "Do not enter the person's full name or national ID here."
            )
        }


class IntegrationRequestAdminForm(forms.ModelForm):
    class Meta:
        model = IntegrationRequest
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        lender = cleaned.get("lender")
        borrower = cleaned.get("borrower")
        consent = cleaned.get("consent")
        if consent and lender and consent.lender_id != lender.id:
            self.add_error("consent", "Select consent belonging to the selected lender.")
        if consent and borrower and consent.borrower_id != borrower.id:
            self.add_error("consent", "Select consent belonging to the selected borrower.")
        return cleaned


class CreditProfileAdminForm(forms.ModelForm):
    class Meta:
        model = CreditProfile
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        borrower = cleaned.get("borrower")
        integration_request = cleaned.get("integration_request")
        if integration_request and borrower and integration_request.borrower_id != borrower.id:
            self.add_error(
                "integration_request",
                "Select an integration request belonging to the selected borrower.",
            )
        return cleaned


@admin.register(Borrower)
class BorrowerAdmin(admin.ModelAdmin):
    form = BorrowerAdminForm
    list_display = ("borrower_reference", "created_at")
    search_fields = ("borrower_reference",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Lender)
class LenderAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Institution details", {"fields": ("lender_id", "institution_name", "institution_type")}),
        ("Connection settings", {"fields": ("api_base_url", "api_status", "authentication_method")}),
    )
    list_display = ("institution_name", "lender_id", "api_status")
    search_fields = ("lender_id", "institution_name")


@admin.register(BorrowerAccount)
class BorrowerAccountAdmin(admin.ModelAdmin):
    list_display = ("borrower", "lender", "account_reference", "account_name")
    search_fields = ("account_reference", "borrower__borrower_reference", "lender__institution_name")
    list_filter = ("lender",)


@admin.register(BorrowerLoan)
class BorrowerLoanAdmin(admin.ModelAdmin):
    list_display = ("borrower", "lender", "loan_id", "loan_amount", "outstanding_balance", "status")
    search_fields = ("loan_id", "borrower__borrower_reference", "lender__institution_name")
    list_filter = ("lender", "status")


@admin.register(RepaymentRecord)
class RepaymentRecordAdmin(admin.ModelAdmin):
    list_display = ("borrower", "loan", "repayment_amount", "repayment_date", "days_overdue")
    search_fields = ("loan__loan_id", "borrower__borrower_reference")
    list_filter = ("lender",)


@admin.register(BorrowerFinancialProfile)
class BorrowerFinancialProfileAdmin(admin.ModelAdmin):
    list_display = ("borrower", "active_loans", "total_outstanding_debt", "monthly_repayment", "debt_to_income_ratio")
    search_fields = ("borrower__borrower_reference",)


@admin.register(Consent)
class ConsentAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Consent identification", {"fields": ("consent_id", "borrower", "lender")}),
        ("Permission", {"fields": ("purpose", "granted_at", "expires_at", "status")}),
    )
    list_display = ("consent_id", "borrower", "lender", "status", "expires_at")
    list_filter = ("status",)
    search_fields = ("consent_id", "borrower__borrower_reference", "lender__institution_name")


@admin.register(IntegrationRequest)
class IntegrationRequestAdmin(admin.ModelAdmin):
    form = IntegrationRequestAdminForm
    fields = ("lender", "borrower", "consent", "status", "error_message", "raw_payload")
    readonly_fields = ("request_reference", "created_at", "updated_at")
    list_display = ("request_reference", "lender", "borrower", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("request_reference", "borrower__borrower_reference", "lender__institution_name")


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Assessment setup", {"fields": ("assessment_reference", "borrower")}),
        ("Assessment results", {
            "fields": (
                "reputation",
                "reputation_score",
                "risk_level",
                "behavior_summary",
                "credit_score",
                "ruleset_version",
                "model_version",
            )
        }),
        ("Blockchain verification", {
            "fields": ("verification_status", "blockchain_transaction_hash", "blockchain_block_number")
        }),
    )
    list_display = ("assessment_reference", "borrower", "risk_level", "credit_score", "verification_status")
    list_filter = ("risk_level", "verification_status")
    search_fields = ("assessment_reference", "borrower__borrower_reference")


@admin.register(CreditProfile)
class CreditProfileAdmin(admin.ModelAdmin):
    form = CreditProfileAdminForm
    list_display = ("id", "borrower", "integration_request", "source_version", "created_at")
    search_fields = ("borrower__borrower_reference", "source_version")
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("borrower", "integration_request")


@admin.register(CreditFeature)
class CreditFeatureAdmin(admin.ModelAdmin):
    list_display = ("name", "profile", "value", "feature_version", "created_at")
    list_filter = ("feature_version", "name")
    search_fields = ("name", "profile__borrower__borrower_reference")
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("profile__borrower")


@admin.register(AIReputationResult)
class AIReputationResultAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Assessment", {"fields": ("assessment",)}),
        ("AI result", {"fields": ("reputation", "score", "risk_level", "behavior_summary", "model_version")}),
        ("Provider response", {"fields": ("raw_result",)}),
    )
    list_display = ("assessment", "reputation", "score", "risk_level", "model_version")
    list_filter = ("reputation", "risk_level", "model_version")
    search_fields = ("assessment__assessment_reference", "assessment__borrower__borrower_reference")
    readonly_fields = ("created_at", "updated_at")


@admin.register(SmartContractResult)
class SmartContractResultAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Assessment", {"fields": ("assessment",)}),
        ("Authoritative score", {"fields": ("credit_score", "ruleset_version", "contract_address")}),
        ("Contract response", {"fields": ("raw_result",)}),
    )
    list_display = ("assessment", "credit_score", "ruleset_version", "contract_address")
    list_filter = ("ruleset_version",)
    search_fields = ("assessment__assessment_reference", "contract_address")
    readonly_fields = ("created_at", "updated_at")


@admin.register(BlockchainTransaction)
class BlockchainTransactionAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Assessment", {"fields": ("assessment",)}),
        ("Transaction", {"fields": ("transaction_hash", "network", "block_number", "status")}),
        ("Verification", {"fields": ("verification_data",)}),
    )
    list_display = ("transaction_hash", "assessment", "network", "status", "block_number", "created_at")
    list_filter = ("network", "status")
    search_fields = ("transaction_hash", "assessment__assessment_reference")
    readonly_fields = ("created_at", "updated_at")


@admin.register(DataRoutingPolicy)
class DataRoutingPolicyAdmin(admin.ModelAdmin):
    list_display = ("policy_id", "name", "active", "version", "updated_at")
    list_filter = ("active",)
    search_fields = ("policy_id", "name")


@admin.register(DataExchange)
class DataExchangeAdmin(admin.ModelAdmin):
    list_display = ("system", "direction", "operation", "status", "borrower", "created_at")
    list_filter = ("system", "direction", "status")
    search_fields = ("operation", "borrower__borrower_reference", "error_message")
    readonly_fields = ("created_at", "updated_at")
