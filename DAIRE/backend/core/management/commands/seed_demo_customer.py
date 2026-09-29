"""
seed_demo_customer.py — Seeds ONE complete borrower (Amina Hassan) and runs
the full dual-model scoring pipeline, printing a rich result table.

Usage:
    python manage.py seed_demo_customer
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (
    Assessment, Borrower, BorrowerAccount, BorrowerLoan,
    Consent, Lender, RepaymentRecord,
)
from core.services import (
    AIReputationService, ensure_credit_profile, refresh_borrower_financial_profile,
)

B  = lambda s: f"\033[1m{s}\033[0m"
G  = lambda s: f"\033[92m{s}\033[0m"
Y  = lambda s: f"\033[93m{s}\033[0m"
R  = lambda s: f"\033[91m{s}\033[0m"
C  = lambda s: f"\033[96m{s}\033[0m"
DIM= lambda s: f"\033[2m{s}\033[0m"
D70 = "─" * 70
H70 = "═" * 70


def col_dec(d):
    return {
        "APPROVED": G, "CONDITIONAL_APPROVAL": Y,
        "MANUAL_REVIEW": Y, "DECLINED": R,
    }.get(d, lambda s: s)(d)

def col_risk(r):
    return {"LOW": G, "MEDIUM": Y, "HIGH": R}.get(r, lambda s: s)(r)

def wrap(text, prefix="  │  ", width=64):
    lines, line, n = [], prefix, 0
    for word in text.split():
        if n + len(word) > width:
            lines.append(line)
            line, n = prefix, 0
        line += word + " "; n += len(word) + 1
    if line.strip(): lines.append(line)
    return "\n".join(lines)


class Command(BaseCommand):
    help = "Seed one demo customer and show full dual-model scoring output."

    def handle(self, *args, **options):
        w = self.stdout.write
        w(B(C(f"\n{H70}")))
        w(B(C("  DAIRE Central System — Demo Customer Seed & Scoring")))
        w(B(C(f"{H70}\n")))

        # 0. Admin
        User = get_user_model()
        admin, _ = User.objects.get_or_create(
            username="apk",
            defaults={"is_active": True, "is_staff": True, "is_superuser": True},
        )
        admin.set_password("apk"); admin.save()
        w(DIM("  ✓ Admin user 'apk' ready"))

        # 1. Lender
        lender, _ = Lender.objects.get_or_create(
            lender_id="LDR-NMB-DEMO",
            defaults={
                "institution_name": "NMB Bank Plc (Demo)",
                "institution_type": "Commercial Bank",
                "api_base_url": "http://127.0.0.1:8001",
                "api_status": Lender.Status.CONNECTED,
                "authentication_method": "API_KEY",
            },
        )
        w(DIM(f"  ✓ Lender: {lender.institution_name}"))

        # 2. Borrower
        borrower, created = Borrower.objects.get_or_create(
            borrower_reference="DEMO-AMINA-001",
            defaults={
                "nida_number": "19910322-14081-00001-9",
                "name": "Amina Hassan Mwalimu",
                "customer_id": "CUST-00042",
                "age": 34,
                "gender": "Female",
                "employment_status": "Employed",
                "income": Decimal("18000000"),
                "business_information": {
                    "employer": "Tanzania Revenue Authority",
                    "sector": "Public Service",
                    "years_employed": 7,
                },
                "account_information": {
                    "primary_account": "NMB-TZ-00042",
                    "account_type": "Current",
                    "opened_date": "2016-03-15",
                },
            },
        )
        w(DIM(f"  ✓ Borrower Amina Hassan ({'created' if created else 'already exists'})"))

        # 3. Account
        now = timezone.now()
        account, _ = BorrowerAccount.objects.get_or_create(
            borrower=borrower, lender=lender, account_reference="NMB-TZ-00042",
            defaults={
                "account_name": "NMB Current Account",
                "customer_id": "CUST-00042",
                "metadata": {
                    "transaction_frequency": 240,
                    "income_frequency": 24,
                    "savings": "3200000",
                    "balance_stability": 0.82,
                    "account_activity": {
                        "first_transaction_date": "2016-04-01",
                        "last_transaction_date": str(now.date()),
                    },
                },
            },
        )
        w(DIM("  ✓ Bank account linked"))

        # 4. Active loan
        loan, _ = BorrowerLoan.objects.get_or_create(
            borrower=borrower, lender=lender, loan_id="LN-AMINA-2023-001",
            defaults={
                "source_account": account,
                "loan_amount": Decimal("4500000"),
                "loan_date": date(2023, 6, 1),
                "loan_duration_months": 36,
                "interest_rate": Decimal("12.5"),
                "outstanding_balance": Decimal("2100000"),
                "status": "ACTIVE",
            },
        )
        w(DIM("  ✓ Active loan: TZS 4.5M @ 12.5% / 36 months"))

        # Completed historical loan
        BorrowerLoan.objects.get_or_create(
            borrower=borrower, lender=lender, loan_id="LN-AMINA-2020-001",
            defaults={
                "source_account": account,
                "loan_amount": Decimal("2000000"),
                "loan_date": date(2020, 1, 10),
                "loan_duration_months": 24,
                "interest_rate": Decimal("14.0"),
                "outstanding_balance": Decimal("0"),
                "status": "COMPLETED",
            },
        )
        w(DIM("  ✓ Completed historical loan seeded"))

        # 5. Repayments
        existing_count = RepaymentRecord.objects.filter(borrower=borrower).count()
        if existing_count == 0:
            for i in range(30):
                due = date(2023, 6, 1) + timedelta(days=30 * i)
                RepaymentRecord.objects.create(
                    borrower=borrower, lender=lender, loan=loan,
                    repayment_amount=Decimal("142000"),
                    repayment_date=due, due_date=due,
                    days_overdue=0, missed_payments=0,
                    late_payments=0, default_status="",
                )
            w(DIM("  ✓ 30 on-time repayments seeded"))
        else:
            w(DIM(f"  ✓ {existing_count} repayments already exist"))

        # 6. Consent
        Consent.objects.get_or_create(
            consent_id="CONSENT-AMINA-001",
            defaults={
                "borrower": borrower, "lender": lender,
                "purpose": "Credit assessment for loan application",
                "granted_at": now - timedelta(days=2),
                "expires_at": now + timedelta(days=363),
                "status": Consent.Status.ACTIVE,
            },
        )
        w(DIM("  ✓ Active consent registered"))

        # 7. Refresh financial profile
        financial = refresh_borrower_financial_profile(borrower)
        w(DIM("  ✓ Financial profile refreshed"))

        # 8. Assessment + credit profile
        assessment_ref = f"ASS-AMINA-DEMO-{now.strftime('%Y%m%d')}"
        assessment, _ = Assessment.objects.get_or_create(
            assessment_reference=assessment_ref, defaults={"borrower": borrower},
        )
        ensure_credit_profile(borrower)
        w(DIM("  ✓ Assessment and credit profile ready"))

        # 9. Score
        w(f"\n{B(C('  Running dual-model scoring pipeline…'))}")
        svc = AIReputationService()
        try:
            ai_result = svc.calculate(assessment, {})
        except Exception as exc:
            self.stderr.write(R(f"\n  ✗ Scoring failed: {exc}"))
            raise

        ai_result.refresh_from_db()
        raw = ai_result.raw_result or {}
        self._print_results(borrower, financial, raw, ai_result)

    # ──────────────────────────────────────────────────────────────────
    def _print_results(self, borrower, financial, raw, ai_result):
        w = self.stdout.write

        w(f"\n{B(H70)}")
        w(B(f"  SCORING RESULT  ·  {borrower.name}  ·  {borrower.borrower_reference}"))
        w(B(H70))

        # ── 1. Inputs ───────────────────────────────────────────────
        w(B(C(f"\n  ┌─ BORROWER INPUT DATA {'─'*47}")))
        def row(label, value):
            w(f"  │  {B(label):<28} {value}")
        row("Name",              borrower.name)
        row("Age",               f"{borrower.age} years")
        row("Gender",            borrower.gender)
        row("Employment",        borrower.employment_status)
        row("Annual Income",     f"TZS {float(borrower.income or 0):>14,.0f}")
        row("Active Loans",      str(financial.active_loans))
        row("Previous Loans",    str(financial.previous_loans))
        row("Total Outstanding", f"TZS {float(financial.total_outstanding_debt):>14,.0f}")
        row("Monthly Repayment", f"TZS {float(financial.monthly_repayment):>14,.0f}")
        row("Savings on File",   f"TZS {float(financial.savings or 0):>14,.0f}")
        row("Debt-to-Income",    f"{float(financial.debt_to_income_ratio)*100:.1f}%")
        row("Tx Frequency",      f"{financial.transaction_frequency} transactions/yr")
        w(f"  └{'─'*68}")

        # ── 2. ML Model ─────────────────────────────────────────────
        sk = raw.get("sklearn_metrics", {})
        w(B(C(f"\n  ┌─ MODEL 1 · Scikit-Learn RandomForest {'─'*31}")))
        ml_pd = sk.get("default_probability")
        ml_sp = sk.get("survival_probability")
        ml_rb = sk.get("risk_band", "—")
        w(f"  │  {'Default Probability':<30} {B(f'{float(ml_pd)*100:.1f}%') if ml_pd is not None else '—'}")
        w(f"  │  {'Survival Probability':<30} {f'{float(ml_sp)*100:.1f}%' if ml_sp is not None else '—'}")
        w(f"  │  {'Risk Band':<30} {ml_rb}")
        w(f"  └{'─'*68}")

        # ── 3. NMB Scorecard ────────────────────────────────────────
        nmb = raw.get("nmb_metrics", {})
        w(B(C(f"\n  ┌─ MODEL 2 · NMB Banking Scorecard (WoE / Bureau Scale) {'─'*15}")))
        nmb_score = nmb.get("credit_score")
        nmb_pd    = nmb.get("default_probability")
        nmb_rb    = nmb.get("risk_band", "—")
        w(f"  │  {'Credit Score (300–850)':<30} {B(str(round(float(nmb_score), 0))) if nmb_score is not None else '—'}")
        w(f"  │  {'Default Probability':<30} {B(f'{float(nmb_pd)*100:.1f}%') if nmb_pd is not None else '—'}")
        w(f"  │  {'Risk Band':<30} {nmb_rb}")
        for s in nmb.get("top_strengths", [])[:3]:
            w(f"  │  {G('▲ Strength')} {s.get('feature',''):<22} WoE={s.get('woe', 0):+.3f}")
        for r in nmb.get("top_risk_factors", [])[:3]:
            w(f"  │  {R('▼ Risk    ')} {r.get('feature',''):<22} WoE={r.get('woe', 0):+.3f}")
        w(f"  └{'─'*68}")

        # ── 4. Consensus ────────────────────────────────────────────
        cons = raw.get("consensus_metrics", {})
        w(B(C(f"\n  ┌─ ENSEMBLE CONSENSUS (50% ML + 50% NMB) {'─'*29}")))
        ens_pd = raw.get("default_probability")
        conc   = cons.get("concordance", "—")
        agree  = cons.get("agreement_pct")
        spread = cons.get("model_spread")
        w(f"  │  {'Blended PD':<36} {B(f'{float(ens_pd)*100:.1f}%') if ens_pd is not None else '—'}")
        w(f"  │  {'Model Spread':<36} {f'{float(spread)*100:.1f}%' if spread is not None else '—'}")
        w(f"  │  {'Concordance':<36} {B(conc)}")
        w(f"  │  {'Agreement':<36} {f'{float(agree):.1f}%' if agree is not None else '—'}")
        w(f"  └{'─'*68}")

        # ── 5. Decision ─────────────────────────────────────────────
        decision       = raw.get("decision", ai_result.reputation)
        decision_label = raw.get("decision_label", "—")
        credit_grade   = raw.get("credit_grade", "—")
        credit_tier    = raw.get("credit_tier", "—")
        uw_summary     = raw.get("underwriting_summary", ai_result.behavior_summary)
        w(B(C(f"\n  ┌─ UNDERWRITING DECISION {'─'*46}")))
        w(f"  │  {'Decision':<30} {B(col_dec(decision))}")
        w(f"  │  {'Label':<30} {decision_label}")
        w(f"  │  {'Credit Grade':<30} {B(credit_grade)}")
        w(f"  │  {'Credit Tier':<30} {credit_tier}")
        w(f"  │  {'Reputation':<30} {ai_result.reputation}")
        w(f"  │  {'Risk Level':<30} {col_risk(ai_result.risk_level)}")
        w(f"  │  {'Score (0→1)':<30} {float(ai_result.score):.4f}")
        w(f"  │")
        w(f"  │  {B('Underwriting Summary:')}")
        w(wrap(uw_summary))
        w(f"  └{'─'*68}")

        # ── 6. Basel II ─────────────────────────────────────────────
        basl = raw.get("basel_metrics", {})
        w(B(C(f"\n  ┌─ BASEL II EXPECTED LOSS {'─'*45}")))
        pd_v  = basl.get("pd",  ens_pd or 0)
        lgd_v = basl.get("lgd", 0)
        ead_v = basl.get("ead", 0)
        el_v  = basl.get("expected_loss", 0)
        w(f"  │  {'PD  (Probability of Default)':<36} {float(pd_v)*100:.1f}%")
        w(f"  │  {'LGD (Loss Given Default)':<36} {float(lgd_v)*100:.0f}%")
        w(f"  │  {'EAD (Exposure at Default)':<36} TZS {float(ead_v):>12,.0f}")
        w(f"  │  {'EL  (PD × LGD × EAD)':<36} {B('TZS ' + f'{float(el_v):>10,.2f}')}")
        w(f"  └{'─'*68}")

        # ── 7. Pricing ──────────────────────────────────────────────
        pricing = raw.get("pricing_capacity", {})
        w(B(C(f"\n  ┌─ PRICING & CREDIT CAPACITY {'─'*42}")))
        limit = pricing.get("recommended_credit_limit", 0)
        apr   = pricing.get("recommended_apr", 0)
        coll  = pricing.get("collateral_policy", "—")
        w(f"  │  {'Recommended Credit Limit':<36} {B('TZS ' + f'{float(limit):>10,.0f}')}")
        w(f"  │  {'Recommended APR':<36} {B(f'{float(apr):.2f}%')}")
        w(f"  │  {'Collateral Policy':<36} {coll}")
        w(f"  └{'─'*68}")

        # ── 8. Strengths & Risks ────────────────────────────────────
        strengths = raw.get("strengths", [])
        risks     = raw.get("risk_factors", [])
        if strengths or risks:
            w(B(C(f"\n  ┌─ STRENGTHS & RISK FACTORS {'─'*43}")))
            for s in strengths:
                w(f"  │  {G('✔')} {s}")
            for r in risks:
                w(f"  │  {R('✘')} {r}")
            w(f"  └{'─'*68}")

        # ── 9. Actionable Guidance ──────────────────────────────────
        guidance = raw.get("actionable_guidance", [])
        if guidance:
            w(B(C(f"\n  ┌─ ACTIONABLE GUIDANCE {'─'*48}")))
            for i, g in enumerate(guidance, 1):
                w(wrap(f"{i}. {g}", prefix="  │  "))
                w("  │")
            w(f"  └{'─'*68}")

        # ── 10. Full summary ────────────────────────────────────────
        w(B(C(f"\n  ┌─ FULL BEHAVIOR SUMMARY {'─'*46}")))
        w(wrap(ai_result.behavior_summary))
        w(f"  └{'─'*68}")

        w(B(C(f"\n{H70}")))
        w(B(C(f"  ✅  Scoring complete.  AI Result ID: {ai_result.id}")))
        w(B(C(f"{H70}\n")))
