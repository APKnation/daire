"""Convert prefixed demo IDs to plain numeric ids (001, 002, 003 …).

The convention changed: customer ids are plain zero-padded numbers (no
"NMB-CUST-" style prefixes), and account/loan references are digit-only
strings. JSON string identifiers are kept as strings (JSON has no zero-
padded integer type), but every letter prefix is stripped.
"""
import re

from django.db import migrations

_PREFIX = re.compile(r"^[A-Za-z]+-+")
_NON_DIGITS = re.compile(r"[^0-9]")


def _numeric(value: str) -> str:
    """Strip letter prefixes: 'NMB-CUST-0001' -> '0001', 'CRDB-7712001' -> '7712001'."""
    if not value:
        return value
    return _PREFIX.sub("", str(value))


def _digits(value: str) -> str:
    """Customer ids are digits only: 'CUST-010' -> '010', 'C7' -> '7'."""
    if not value:
        return value
    return _NON_DIGITS.sub("", str(value))


def strip_prefixes(apps, schema_editor):
    Borrower = apps.get_model("core", "Borrower")
    BorrowerAccount = apps.get_model("core", "BorrowerAccount")
    BorrowerLoan = apps.get_model("core", "BorrowerLoan")

    for borrower in Borrower.objects.all():
        new_customer_id = _digits(borrower.customer_id)
        if new_customer_id != borrower.customer_id:
            borrower.customer_id = new_customer_id
            borrower.save(update_fields=("customer_id",))

    for account in BorrowerAccount.objects.all():
        new_ref = _numeric(account.account_reference)
        new_customer_id = _numeric(account.customer_id)
        if new_ref != account.account_reference or new_customer_id != account.customer_id:
            # Same lender may already hold the de-prefixed twin of this
            # account (e.g. re-seeded data); merge metadata instead of
            # violating the unique (borrower, lender, account_reference).
            twin = BorrowerAccount.objects.filter(
                borrower=account.borrower, lender=account.lender, account_reference=new_ref,
            ).exclude(pk=account.pk).first()
            if twin is not None:
                twin.metadata = {**(account.metadata or {}), **(twin.metadata or {})}
                twin.save(update_fields=("metadata", "updated_at"))
                account.delete()
                continue
            account.account_reference = new_ref
            account.customer_id = new_customer_id
            account.save(update_fields=("account_reference", "customer_id", "updated_at"))

    for loan in BorrowerLoan.objects.all():
        new_id = _numeric(loan.loan_id)
        if new_id == loan.loan_id:
            continue
        twin = BorrowerLoan.objects.filter(
            borrower=loan.borrower, lender=loan.lender, loan_id=new_id,
        ).exclude(pk=loan.pk).first()
        if twin is not None:
            loan.delete()
            continue
        loan.loan_id = new_id
        loan.save(update_fields=("loan_id", "updated_at"))


def add_prefixes(apps, schema_editor):
    # One-way data cleanup; nothing to reverse.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_lender_broadcast_api_key"),
    ]

    operations = [
        migrations.RunPython(strip_prefixes, add_prefixes),
    ]
