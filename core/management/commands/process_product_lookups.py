
import time
from datetime import timedelta

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

        parser.add_argument(
            "--recover-stale-minutes",
            type=int,
            default=30,
            help="Mark processing jobs older than this as failed.",
        )

    def recover_stale_drafts(self, minutes):
        """
        Mark abandoned processing jobs as failed.

        This allows the admin Fix action to retry them.
        Active jobs younger than the configured threshold are untouched.
        """
        cutoff = timezone.now() - timedelta(minutes=minutes)

        error_message = (
            "This lookup appears to have been interrupted. "
            "The worker did not finish processing this draft within "
            f"{minutes} minutes. Use Fix to retry the lookup."
        )

        stale_drafts = ProductImportDraft.objects.filter(
            lookup_status="processing",
            lookup_started_at__isnull=False,
            lookup_started_at__lt=cutoff,
        )

        recovered_count = stale_drafts.update(
            lookup_status="failed",
            lookup_finished_at=timezone.now(),
            lookup_error=error_message,
            updated_at=timezone.now(),
        )

        if recovered_count:
            self.stdout.write(
                self.style.WARNING(
                    f"Recovered {recovered_count} stale lookup(s)."
                )
            )

        return recovered_count

    def claim_next_draft(self):
        """
        Claim one queued draft.

        The transaction stays short. The manufacturer lookup runs
        after the transaction has closed.
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

            if draft.lookup_status != "processing":
                return

            model_number = (draft.raw_code or "").strip()

            if not model_number:
                raise ValueError(
                    "The product model number is empty. "
                    "Enter a valid manufacturer model number and retry."
                )

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
                    "The manufacturer result did not pass exact model "
                    "verification. The result cannot be imported."
                )

            source_url = result.get("source_url") or ""

            updated = ProductImportDraft.objects.filter(
                pk=draft_id,
                lookup_status="processing",
            ).update(
                extracted_data=result,
                source_url=source_url or draft.source_url,
                lookup_status="completed",
                lookup_finished_at=timezone.now(),
                lookup_error="",
                updated_at=timezone.now(),
            )

            if not updated:
                self.stdout.write(
                    self.style.WARNING(
                        f"Draft #{draft_id} was no longer processing. "
                        "Its current status was preserved."
                    )
                )
                return

            self.stdout.write(
                self.style.SUCCESS(
                    f"Completed manufacturer lookup for draft #{draft_id}."
                )
            )

            diagnostics = result.get("lookup_diagnostics", {})

            if diagnostics:
                self.stdout.write(
                    "Pages checked: "
                    f"{diagnostics.get('pages_checked', 0)} | "
                    "Pages failed: "
                    f"{diagnostics.get('pages_failed', 0)}"
                )

        except Exception as exc:
            error_message = (
                f"{type(exc).__name__}: {str(exc)}"
            )[:4000]

            updated = ProductImportDraft.objects.filter(
                pk=draft_id,
                lookup_status="processing",
            ).update(
                lookup_status="failed",
                lookup_finished_at=timezone.now(),
                lookup_error=error_message,
                updated_at=timezone.now(),
            )

            if updated:
                self.stderr.write(
                    self.style.ERROR(
                        f"Lookup failed for draft #{draft_id}: "
                        f"{error_message}"
                    )
                )
            else:
                self.stderr.write(
                    self.style.WARNING(
                        f"Draft #{draft_id} could not be marked failed "
                        "because its status had already changed."
                    )
                )

    def handle(self, *args, **options):
        once = options["once"]
        poll_seconds = max(1, options["poll"])
        stale_minutes = max(1, options["recover_stale_minutes"])

        self.stdout.write(
            self.style.SUCCESS(
                "YUNQIDA product lookup worker started."
            )
        )

        self.stdout.write(
            f"Stale lookup recovery threshold: {stale_minutes} minutes."
        )

        while True:
            self.recover_stale_drafts(stale_minutes)

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
