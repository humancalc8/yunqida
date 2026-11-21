
import requests

from django.core.files.base import ContentFile
from django.db import transaction

from core.models import Product, ProductImage
from core.services.product_lookup import (
    _fetch_page,
    _build_product_data,
    _page_model_matches,
)
from core.services.product_images import download_product_images


# Only these six products are authorised for this repair.
TARGET_MODELS = [
    'YQD-256200-LFO',
    'YQD-512684-LFO',
    'YQD-12K-48V-EU(IP21)',
    'YQD-8K-48V-EU(IP66)',
    'YQD-256100-LFO',
    'YQD-512300B-LFO',
]

EXPECTED_IMAGE_COUNTS = {
    'YQD-256200-LFO': 3,
    'YQD-512684-LFO': 3,
    'YQD-12K-48V-EU(IP21)': 1,
    'YQD-8K-48V-EU(IP66)': 2,
    'YQD-256100-LFO': 3,
    'YQD-512300B-LFO': 3,
}


def main():
    session = requests.Session()

    try:
        # -------------------------------------------------
        # PHASE 1: VERIFY AND DOWNLOAD ALL SIX PRODUCTS
        # No database changes in this phase.
        # -------------------------------------------------

        prepared = []

        for model in TARGET_MODELS:
            print('\n' + '=' * 65)
            print('VERIFYING:', model)

            product = Product.objects.filter(
                manufacturer_model__iexact=model
            ).first()

            if not product:
                raise RuntimeError(
                    f'Product not found: {model}'
                )

            if not product.manufacturer_url:
                raise RuntimeError(
                    f'Missing manufacturer URL: {model}'
                )

            soup = _fetch_page(
                session,
                product.manufacturer_url,
            )

            if not _page_model_matches(soup, model):
                raise RuntimeError(
                    f'MODEL VERIFICATION FAILED: {model}. '
                    'No images have been changed.'
                )

            product_data = _build_product_data(
                soup,
                model,
                product.manufacturer_url,
            )

            image_urls = product_data.get('image_urls') or []

            expected = EXPECTED_IMAGE_COUNTS[model]

            if len(image_urls) != expected:
                raise RuntimeError(
                    f'Unexpected manufacturer image count for {model}: '
                    f'expected {expected}, found {len(image_urls)}. '
                    'No images have been changed.'
                )

            downloaded, errors = download_product_images(
                image_urls
            )

            if errors:
                raise RuntimeError(
                    f'Download errors for {model}: {errors}'
                )

            if len(downloaded) != expected:
                raise RuntimeError(
                    f'Incomplete downloads for {model}: '
                    f'expected {expected}, downloaded {len(downloaded)}.'
                )

            prepared.append({
                'model': model,
                'product': product,
                'images': downloaded,
            })

            print('MODEL CHECK: PASSED')
            print('EXPECTED IMAGES:', expected)
            print('DOWNLOADED IMAGES:', len(downloaded))

        if len(prepared) != len(TARGET_MODELS):
            raise RuntimeError(
                'Not all six products passed verification.'
            )

        # -------------------------------------------------
        # PHASE 2: UPDATE DATABASE RECORDS
        # Existing physical files are deliberately retained.
        # -------------------------------------------------

        print('\n' + '=' * 65)
        print('ALL SIX PRODUCTS VERIFIED.')
        print('STARTING DATABASE REPAIR.')

        with transaction.atomic():

            for item in prepared:
                model = item['model']
                product = Product.objects.select_for_update().get(
                    pk=item['product'].pk
                )
                images = item['images']

                print('\nREPAIRING:', model)

                # First verified image becomes the main image.
                main_image = images[0]

                product.image.save(
                    main_image['filename'],
                    ContentFile(main_image['content']),
                    save=False,
                )

                product.save(update_fields=['image'])

                # Remove old gallery database records only.
                # Their physical files are not deleted.
                ProductImage.objects.filter(
                    product=product
                ).delete()

                # Remaining images become ordered gallery records.
                for index, image_data in enumerate(
                    images[1:],
                    start=1,
                ):
                    gallery_image = ProductImage(
                        product=product,
                        alt_text=(
                            f'{product.name} product image {index + 1}'
                        ),
                        source_url=image_data['source_url'],
                        order=index,
                    )

                    gallery_image.image.save(
                        image_data['filename'],
                        ContentFile(image_data['content']),
                        save=False,
                    )

                    gallery_image.save()

                print('MAIN IMAGE:', product.image.name)
                print(
                    'GALLERY RECORDS:',
                    ProductImage.objects.filter(
                        product=product
                    ).count()
                )

        # -------------------------------------------------
        # PHASE 3: VERIFY SAVED DATABASE RECORDS
        # -------------------------------------------------

        print('\n' + '=' * 65)
        print('FINAL DATABASE VERIFICATION')

        for model in TARGET_MODELS:
            product = Product.objects.get(
                manufacturer_model__iexact=model
            )

            gallery = ProductImage.objects.filter(
                product=product
            ).order_by('order', 'id')

            total = 1 + gallery.count()

            print('\nMODEL:', model)
            print('PRODUCT ID:', product.pk)
            print('MAIN IMAGE:', product.image.name)
            print('GALLERY COUNT:', gallery.count())
            print('TOTAL IMAGES:', total)
            print(
                'EXPECTED TOTAL:',
                EXPECTED_IMAGE_COUNTS[model],
            )

            if total != EXPECTED_IMAGE_COUNTS[model]:
                raise RuntimeError(
                    f'Final count mismatch for {model}.'
                )

        print('\nSUCCESS: ALL SIX PRODUCTS REPAIRED.')

    finally:
        session.close()


if __name__ == '__main__':
    main()
