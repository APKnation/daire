from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Borrower, BorrowerAccount, Lender


class Command(BaseCommand):
    help = "Seeds NIDA-identity-keyed borrowers and reconciles lender accounts"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.NOTICE(
                "Seeding NIDA-identity-keyed borrowers and reconciling lender accounts"
            )
        )

        seed_root = Path(__file__).resolve().parent.parent.parent.parent
        seed_file = seed_root / "seed_data.txt"
        seed_data = seed_file.read_text(encoding="utf-8") if seed_file.exists() else ""

        borrowers = []
        for line in seed_data.splitlines():
            line = line.strip()
            if not line or line.lower().startswith(("borrower", "nida", "customer", "#")):
                continue
            if ":" not in line or "\t" not in line:
                continue
            reference, rest = line.split(":", 1)
            reference = reference.strip().lstrip("0") or "0"
            nida = rest.split("\t", 1)[0].strip()
            if not nida.isdigit():
                continue
            borrowers.append({"borrower_reference": reference, "nida_number": nida})

        created = 0
        for borrower in borrowers:
            obj, was_created = Borrower.objects.update_or_create(
                borrower_reference=borrower["borrower_reference"],
                defaults={
                    "nida_number": borrower["nida_number"],
                    "name": f"Borrower-{borrower['nida_number']}",
                    "is_active": True,
                    "customer_id": f"NMB-{borrower['nida_number'][-6:]}",
                    "income": None,
                },
            )
            if was_created:
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created NIDA-keyed borrower {obj.borrower_reference} (NIDA={obj.nida_number})"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Updated existing borrower {obj.borrower_reference} (NIDA={obj.nida_number})"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {created} NIDA-identity-keyed borrower(s) from {seed_file.name}"
            )
        )
