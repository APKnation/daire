"""
prune_lenders.py — remove every lender except NMB and CRDB from the database.

The lender network is NMB + CRDB only. Lenders cannot simply be deleted:
BorrowerAccount, BorrowerLoan, RepaymentRecord, Consent, IntegrationRequest,
LoanApplication and DataExchange rows PROTECT their lender, so this command
removes the dependent data for the retired lenders first (in safe order),
then deletes the lenders.

Usage:
    python manage.py prune_lenders            # dry run: shows what would go
    python manage.py prune_lenders --yes      # actually delete
    python manage.py prune_lenders --keep LDR-FOO --yes   # custom keep-list
"""
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError

from core.models import (
    BorrowerAccount, BorrowerLoan, Consent, DataExchange, IntegrationRequest,
    Lender, LoanApplication, RepaymentRecord,
)

KEEP_DEFAULT = ("NMB", "CRDB")


class Command(BaseCommand):
    help = (
        "Delete every lender whose lender_id/institution_name does NOT match the "
        "keep-list (default: anything containing 'NMB' or 'CRDB'), together with "
        "that lender's accounts, loans, repayments, consents, integration requests "
        "and loan applications."
    )

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="Actually delete (default is a dry run).")
        parser.add_argument(
            "--keep", action="append", default=[],
            help="Additional case-insensitive substring to keep, e.g. --keep EQUITY. Repeatable.",
        )

    def handle(self, *args, **options):
        keep_tokens = list(KEEP_DEFAULT) + [k.upper() for k in options["keep"]]
        execute = bool(options["yes"])

        retirees = [
            lender for lender in Lender.objects.all()
            if not any(token in lender.lender_id.upper() or token in lender.institution_name.upper()
                       for token in keep_tokens)
        ]

        if not retirees:
            self.stdout.write(self.style.SUCCESS("Nothing to prune — only keep-list lenders exist."))
            return

        self.stdout.write(self.style.NOTICE(f"Keep tokens: {keep_tokens}"))
        mode = "DELETE" if execute else "DRY RUN (pass --yes to delete)"
        self.stdout.write(self.style.WARNING(f"Mode: {mode}\n"))

        total_rows = 0
        for lender in retirees:
            accounts = BorrowerAccount.objects.filter(lender=lender)
            loans = BorrowerLoan.objects.filter(lender=lender)
            repayments = RepaymentRecord.objects.filter(lender=lender)
            consents = Consent.objects.filter(lender=lender)
            integrations = IntegrationRequest.objects.filter(lender=lender)
            applications = LoanApplication.objects.filter(lender=lender)
            exchanges = DataExchange.objects.filter(lender=lender)

            counts = {
                "borrower accounts": accounts.count(),
                "borrower loans": loans.count(),
                "repayment records": repayments.count(),
                "consents": consents.count(),
                "integration requests": integrations.count(),
                "loan applications": applications.count(),
                "data exchanges (audit)": exchanges.count(),
            }
            row_total = sum(counts.values())
            total_rows += row_total

            self.stdout.write(f"\n► {lender.lender_id} — {lender.institution_name}")
            for label, count in counts.items():
                self.stdout.write(f"    {label:<26} {count}")

            if not execute:
                continue

            # Safe order: leaves first, then the protected relations, then the lender.
            # IntegrationRequests PROTECT their Consent, so integrations (and their
            # credit profiles) go BEFORE consents.
            repayments.delete()
            for loan in loans:
                loan.delete()          # cascades its repayments if any were missed
            applications.delete()
            from core.models import CreditProfile
            CreditProfile.objects.filter(integration_request__in=integrations).delete()
            for request in integrations:
                request.delete()
            consents.delete()
            accounts.delete()
            exchanges.delete()
            lender.delete()
            self.stdout.write(self.style.SUCCESS("    deleted ✓"))

        if not execute:
            self.stdout.write(self.style.NOTICE(
                f"\nDry run complete: {len(retirees)} lender(s) and {total_rows} dependent rows "
                f"would be removed. Re-run with --yes to delete."
            ))
            return

        content_type = ContentType.objects.get_for_model(Lender)
        self.stdout.write(self.style.SUCCESS(
            f"\nPruned {len(retirees)} lender(s) and {total_rows} dependent rows. "
            f"Remaining lenders: {', '.join(l.lender_id for l in Lender.objects.all())} "
            f"(content_type id {content_type.id} retains admin log history)."
        ))
