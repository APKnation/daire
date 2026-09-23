from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    AssessmentViewSet, BorrowerAccountViewSet, BorrowerFinancialProfileViewSet,
    BorrowerLoanViewSet, BorrowerViewSet, ConsentViewSet, CreditFeatureViewSet,
    CreditProfileViewSet,
    DashboardView, PredictCreditRiskView, IntegrationRequestViewSet, LenderViewSet, AIReputationResultViewSet,
    RepaymentRecordViewSet, SmartContractResultViewSet, BlockchainTransactionViewSet,
    DataExchangeViewSet, DataRoutingPolicyViewSet,
    AdminLogEntryViewSet, MockLenderDataView, MockLenderBroadcastView, LenderDataReceiveView,
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
urlpatterns += [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("predict_credit_risk/", PredictCreditRiskView.as_view(), name="predict_credit_risk"),
    # LENDER -> Central push: lender submits borrower data (wrapped or flat contract).
    path("lender-data/receive/", LenderDataReceiveView.as_view(), name="lender-data-receive"),
    path("mock-lender/borrowers", MockLenderDataView.as_view(), name="mock-lender-borrowers"),
    path("mock-lender/<str:base>/borrowers", MockLenderDataView.as_view(), name="mock-lender-borrowers-named"),
    path("mock-lender/<str:base>", MockLenderBroadcastView.as_view(), name="mock-lender-base"),
    # The real receive path Central broadcasts to: {base}/api/daire/central/receive/
    path("mock-lender/<str:base>/api/daire/central/receive/", MockLenderBroadcastView.as_view(), name="mock-lender-receive"),
    path("mock-lender/<str:base>/broadcast", MockLenderBroadcastView.as_view(), name="mock-lender-broadcast"),
    path("mock-lender/broadcast", MockLenderBroadcastView.as_view(), name="mock-lender-broadcast-root"),
]
