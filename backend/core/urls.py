from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    AssessmentViewSet, BorrowerAccountViewSet, BorrowerFinancialProfileViewSet,
    BorrowerLoanViewSet, BorrowerViewSet, ConsentViewSet, CreditFeatureViewSet,
    CreditProfileViewSet,
    DashboardView, IntegrationRequestViewSet, LenderViewSet, AIReputationResultViewSet,
    RepaymentRecordViewSet, SmartContractResultViewSet, BlockchainTransactionViewSet,
    DataExchangeViewSet, DataRoutingPolicyViewSet,
    AdminLogEntryViewSet,
)

router = DefaultRouter()
router.register("lenders", LenderViewSet)
router.register("borrowers", BorrowerViewSet)
router.register("borrower-accounts", BorrowerAccountViewSet, basename="borrower-account")
router.register("borrower-loans", BorrowerLoanViewSet, basename="borrower-loan")
router.register("repayments", RepaymentRecordViewSet, basename="repayment-record")
router.register("borrower-financial-profiles", BorrowerFinancialProfileViewSet, basename="borrower-financial-profile")
router.register("routing-policies", DataRoutingPolicyViewSet, basename="routing-policy")
router.register("data-exchanges", DataExchangeViewSet, basename="data-exchange")
router.register("audit-logs", AdminLogEntryViewSet, basename="audit-log")
router.register("consents", ConsentViewSet)
router.register("assessments", AssessmentViewSet)
router.register("credit-profiles", CreditProfileViewSet)
router.register("features", CreditFeatureViewSet)
router.register("ai-reputation", AIReputationResultViewSet, basename="ai-reputation")
router.register("smart-contract", SmartContractResultViewSet, basename="smart-contract")
router.register("blockchain", BlockchainTransactionViewSet, basename="blockchain")
# Backwards-compatible resource-specific names.
router.register("ai-reputation-results", AIReputationResultViewSet, basename="ai-reputation-result")
router.register("smart-contract-results", SmartContractResultViewSet, basename="smart-contract-result")
router.register("blockchain-transactions", BlockchainTransactionViewSet, basename="blockchain-transaction")
router.register("integrations/request-credit-data", IntegrationRequestViewSet, basename="integration-request")

urlpatterns = router.urls
urlpatterns += [path("dashboard/", DashboardView.as_view(), name="dashboard")]
