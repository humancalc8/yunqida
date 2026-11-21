
from core.models import Product
from core.services.product_lookup import lookup_yunqida_model

# Only these six previously verified models are included.
VERIFIED_MODELS = [
    "YQD-256200-LFO",
    "YQD-512684-LFO",
    "YQD-12K-48V-EU(IP21)",
    "YQD-8K-48V-EU(IP66)",
    "YQD-256100-LFO",
    "YQD-512300B-LFO",
]

print("\n" + "=" * 75)
print("YUNQIDA PRODUCT IMAGE AUDIT - READ ONLY")
print("=" * 75)

for model_number in VERIFIED_MODELS:

    print("\n" + "-" * 75)
    print(f"MODEL: {model_number}")
    print("-" * 75)

    product = Product.objects.filter(
        manufacturer_model__iexact=model_number
    ).first()

    if not product:
        print("DATABASE PRODUCT: NOT FOUND")
        continue

    print(f"PRODUCT: {product.name}")
    print(f"PRODUCT ID: {product.pk}")

    print("\nCURRENT MAIN IMAGE:")
    print(product.image.name if product.image else "NO MAIN IMAGE")
    print("Original source URL: NOT STORED")

    existing_gallery = list(
        product.gallery_images.all()
    )

    print(f"\nCURRENT GALLERY: {len(existing_gallery)} image(s)")

    existing_urls = []

    for index, gallery in enumerate(existing_gallery, start=1):
        print(f"\n  Gallery image {index}")
        print(f"  File: {gallery.image.name}")
        print(f"  Source: {gallery.source_url or 'NOT STORED'}")
        existing_urls.append(gallery.source_url.strip())

    print("\nLOOKING UP OFFICIAL MANUFACTURER DATA...")

    try:
        data = lookup_yunqida_model(model_number)

    except Exception as error:
        print(f"LOOKUP ERROR: {type(error).__name__}: {error}")
        continue

    returned_model = str(
        data.get("model_number", "")
    ).strip()

    verified = (
        data.get("match_verified") is True
        and returned_model.casefold() == model_number.casefold()
    )

    print(f"EXACT MODEL MATCH: {'YES' if verified else 'NO'}")

    if not verified:
        print("SAFETY: SKIPPING IMAGE COMPARISON")
        continue

    proposed_urls = data.get("image_urls") or []

    if not isinstance(proposed_urls, list):
        proposed_urls = []

    proposed_urls = [
        url.strip()
        for url in proposed_urls
        if isinstance(url, str) and url.strip()
    ]

    print(f"\nPROPOSED MANUFACTURER IMAGES: {len(proposed_urls)}")

    for index, url in enumerate(proposed_urls, start=1):
        print(f"  {index}. {url}")

    print("\nGALLERY COMPARISON:")

    for url in proposed_urls:
        if url in existing_urls:
            print(f"  ALREADY PRESENT: {url}")
        else:
            print(f"  NEW IMAGE:       {url}")

    for url in existing_urls:
        if url and url not in proposed_urls:
            print(f"  NOT IN CURRENT MANUFACTURER RESULTS: {url}")

    print("\nPROPOSED MAIN IMAGE:")
    print(proposed_urls[0] if proposed_urls else "NO IMAGE RETURNED")

print("\n" + "=" * 75)
print("AUDIT COMPLETE - NO DATABASE OR IMAGE FILES WERE MODIFIED")
print("=" * 75)
