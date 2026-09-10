from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    AssessmentViewSet, AuditLogViewSet, BorrowerViewSet, ConsentViewSet, CreditFeatureViewSet,
    CreditProfileViewSet,
    DashboardView, IntegrationRequestViewSet, LenderViewSet, AIReputationResultViewSet,
    SmartContractResultViewSet, BlockchainTransactionViewSet,
)

router = DefaultRouter()
router.register("lenders", LenderViewSet)
router.register("borrowers", BorrowerViewSet)
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
router.register("audit-logs", AuditLogViewSet)

urlpatterns = router.urls
urlpatterns += [path("dashboard/", DashboardView.as_view(), name="dashboard")]
