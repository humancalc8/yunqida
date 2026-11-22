
import time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import ProductImportDraft
from core.services.product_lookup import lookup_yunqida_model


class Command(BaseCommand):
    help = "Process queued YUNQIDA manufacturer product lookups."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process one queued lookup and exit.",
        )
        parser.add_argument(
            "--poll",
            type=float,
            default=5,
            help="Seconds to wait when there are no queued lookups.",
        )

    def claim_next_draft(self):
        """
        Claim one queued draft.

        The database transaction is deliberately short.
        The manufacturer search runs after the transaction closes.
        """
        with transaction.atomic():
            draft = (
                ProductImportDraft.objects
                .select_for_update()
                .filter(lookup_status="queued")
                .order_by("created_at")
                .first()
            )

            if draft is None:
                return None

            draft.lookup_status = "processing"
            draft.lookup_started_at = timezone.now()
            draft.lookup_finished_at = None
            draft.lookup_error = ""

            draft.save(
                update_fields=[
                    "lookup_status",
                    "lookup_started_at",
                    "lookup_finished_at",
                    "lookup_error",
                    "updated_at",
                ]
            )

            return draft.pk

    def process_draft(self, draft_id):
        try:
            draft = ProductImportDraft.objects.get(pk=draft_id)

            model_number = draft.raw_code.strip()

            self.stdout.write(
                f"Looking up draft #{draft.pk}: {model_number}"
            )

            result = lookup_yunqida_model(model_number)

            if not isinstance(result, dict):
                raise ValueError(
                    "The manufacturer lookup returned an invalid result."
                )

            if not result.get("match_verified"):
                raise ValueError(
                    "The manufacturer result did not pass exact model verification."
                )

            draft.extracted_data = result

            source_url = result.get("source_url")
            if source_url:
                draft.source_url = source_url

            draft.lookup_status = "completed"
            draft.lookup_finished_at = timezone.now()
            draft.lookup_error = ""

            draft.save(
                update_fields=[
                    "extracted_data",
                    "source_url",
                    "lookup_status",
                    "lookup_finished_at",
                    "lookup_error",
                    "updated_at",
                ]
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Completed manufacturer lookup for draft #{draft.pk}."
                )
            )

        except Exception as exc:
            error_message = str(exc)[:4000]

            ProductImportDraft.objects.filter(pk=draft_id).update(
                lookup_status="failed",
                lookup_finished_at=timezone.now(),
                lookup_error=error_message,
                updated_at=timezone.now(),
            )

            self.stderr.write(
                self.style.ERROR(
                    f"Lookup failed for draft #{draft_id}: {error_message}"
                )
            )

    def handle(self, *args, **options):
        once = options["once"]
        poll_seconds = max(1, options["poll"])

        self.stdout.write(
            self.style.SUCCESS("YUNQIDA product lookup worker started.")
        )

        while True:
            draft_id = self.claim_next_draft()

            if draft_id is None:
                if once:
                    self.stdout.write("No queued lookups found.")
                    break

                time.sleep(poll_seconds)
                continue

            self.process_draft(draft_id)

            if once:
                break
