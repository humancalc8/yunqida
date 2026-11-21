
from core.models import Product
from core.services.product_lookup import (
    _fetch_page,
    _page_model_matches,
    normalize_model,
    clean_text,
)
import requests

VERIFIED_MODELS = [
    "YQD-256200-LFO",
    "YQD-512684-LFO",
    "YQD-12K-48V-EU(IP21)",
    "YQD-8K-48V-EU(IP66)",
    "YQD-256100-LFO",
    "YQD-512300B-LFO",
]

session = requests.Session()

print("\n" + "=" * 75)
print("YUNQIDA DIRECT PRODUCT URL VERIFICATION")
print("=" * 75)

try:
    for model_number in VERIFIED_MODELS:

        print("\n" + "-" * 75)
        print("MODEL:", model_number)
        print("-" * 75)

        product = Product.objects.filter(
            manufacturer_model__iexact=model_number
        ).first()

        if not product:
            print("DATABASE PRODUCT: NOT FOUND")
            continue

        url = product.manufacturer_url

        if not url:
            print("MANUFACTURER URL: NOT STORED")
            continue

        print("SAVED URL:", url)

        try:
            page = _fetch_page(session, url)

            matched = _page_model_matches(page, model_number)

            if not matched:
                print("RESULT: MODEL DOES NOT MATCH PAGE")
                continue

            model_rows = []

            for row in page.find_all("tr"):
                cells = [
                    clean_text(cell.get_text(" ", strip=True))
                    for cell in row.find_all(["th", "td"])
                ]

                normalized = [
                    normalize_model(cell)
                    for cell in cells
                ]

                if "MODEL" in normalized:
                    model_rows.append((cells, normalized))

            target = normalize_model(model_number)
            matched_row = None

            for cells, normalized in model_rows:
                for index, value in enumerate(normalized):
                    if (
                        value == target
                        and "MODEL" in normalized[:index]
                    ):
                        matched_row = cells
                        break

                if matched_row:
                    break

            if matched_row:
                print("RESULT: STRICT MODEL MATCH PASSED")
                print("MATCHED SPECIFICATION:", matched_row)
            elif model_rows:
                print("RESULT: REVIEW REQUIRED")
                print("MODEL SPECIFICATION EXISTS BUT MATCH NOT IDENTIFIED")
            else:
                print("RESULT: PAGE TEXT FALLBACK MATCH")
                print("REVIEW REQUIRED: NOT A STRICT SPECIFICATION MATCH")

        except Exception as error:
            print(
                "PAGE ERROR:",
                type(error).__name__,
                str(error),
            )

finally:
    session.close()

print("\n" + "=" * 75)
print("VERIFICATION COMPLETE - NO DATABASE OR IMAGE FILES MODIFIED")
print("=" * 75)
