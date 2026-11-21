import json
from urllib.parse import urlsplit

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import path, reverse
from django.utils.text import slugify

from .models import (
    Enquiry,
    Product,
    ProductImage,
    BuildProject,
    ProductImportDraft,
)

from .services.product_lookup import lookup_yunqida_model
from .services.product_images import download_product_images


# =====================================================
# PRODUCT IMAGE GALLERY
# =====================================================

class ProductImageInline(admin.TabularInline):

    model = ProductImage
    extra = 1

    fields = (
        'image',
        'alt_text',
        'source_url',
        'order',
    )

    ordering = ('order', 'id')


# =====================================================
# PRODUCTS
# =====================================================

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):

    change_list_template = 'core/product/change_list.html'
    inlines = [ProductImageInline]

    list_display = (
        'name',
        'manufacturer_model',
        'category',
        'capacity',
        'power',
        'featured',
        'order',
    )

    list_filter = ('category', 'featured')

    list_editable = ('featured', 'order')

    search_fields = (
        'name',
        'manufacturer_model',
        'tagline',
        'description',
    )

    prepopulated_fields = {'slug': ('name',)}

    fieldsets = (
        ('Product Information', {
            'fields': (
                'name',
                'slug',
                'category',
                'tagline',
                'description',
            )
        }),
        ('Manufacturer Information', {
            'fields': (
                'manufacturer_model',
                'manufacturer_url',
            )
        }),
        ('Technical Specifications', {
            'fields': (
                'capacity',
                'power',
                'warranty',
                'technical_specifications',
            )
        }),
        ('Product Images', {
            'fields': (
                'image',
                'fallback_image',
            )
        }),
        ('Catalogue Settings', {
            'fields': (
                'featured',
                'order',
            )
        }),
    )

    def get_urls(self):

        urls = super().get_urls()

        custom_urls = [
            path(
                'scanner/submit/',
                self.admin_site.admin_view(self.submit_scan),
                name='core_product_scanner_submit',
            ),
            path(
                'scanner/',
                self.admin_site.admin_view(self.product_scanner),
                name='core_product_scanner',
            ),
        ]

        return custom_urls + urls

    def product_scanner(self, request):

        if not self.has_add_permission(request):
            raise PermissionDenied

        request.current_app = self.admin_site.name

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'YUNQIDA Product Scanner',
            'submit_url': reverse(
                f'{self.admin_site.name}:core_product_scanner_submit'
            ),
        }

        return render(
            request,
            'admin/core/product/scanner.html',
            context,
        )

    def submit_scan(self, request):

        if request.method != 'POST':
            return JsonResponse(
                {
                    'ok': False,
                    'error': 'POST requests only.',
                },
                status=405,
            )

        if not self.has_add_permission(request):
            raise PermissionDenied

        if len(request.body) > 8192:
            return JsonResponse(
                {
                    'ok': False,
                    'error': 'Submitted information is too large.',
                },
                status=413,
            )

        try:
            payload = json.loads(
                request.body.decode('utf-8')
            )

        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse(
                {
                    'ok': False,
                    'error': 'Invalid JSON request.',
                },
                status=400,
            )

        if not isinstance(payload, dict):
            return JsonResponse(
                {
                    'ok': False,
                    'error': 'Invalid request format.',
                },
                status=400,
            )

        value = payload.get('value')

        if not isinstance(value, str):
            return JsonResponse(
                {
                    'ok': False,
                    'error': 'A valid product identifier is required.',
                },
                status=400,
            )

        value = value.strip()

        if not value or len(value) > 4096:
            return JsonResponse(
                {
                    'ok': False,
                    'error': 'Invalid or excessively long identifier.',
                },
                status=400,
            )

        source_url = ''

        try:
            parsed_url = urlsplit(value)

            if parsed_url.scheme:

                if (
                    parsed_url.scheme.lower() not in ('http', 'https')
                    or not parsed_url.netloc
                    or parsed_url.username
                    or parsed_url.password
                ):
                    return JsonResponse(
                        {
                            'ok': False,
                            'error': 'Unsupported URL.',
                        },
                        status=400,
                    )

                max_length = (
                    ProductImportDraft._meta
                    .get_field('source_url').max_length
                )

                if len(value) <= max_length:
                    source_url = value

        except ValueError:
            return JsonResponse(
                {
                    'ok': False,
                    'error': 'Invalid URL.',
                },
                status=400,
            )

        draft, created = ProductImportDraft.objects.get_or_create(
            raw_code=value,
            status='pending',
            defaults={
                'source_url': source_url,
                'notes': 'Captured using the YUNQIDA Product Scanner.',
            },
        )

        if source_url:

            return JsonResponse({
                'ok': True,
                'draft_id': draft.pk,
                'draft_url': reverse(
                    f'{self.admin_site.name}:core_productimportdraft_change',
                    args=[draft.pk],
                ),
                'lookup_completed': False,
                'message': (
                    'URL saved. Enter the actual product model number '
                    'to fetch specifications.'
                ),
            })

        try:

            result = lookup_yunqida_model(value)

            if (
                not isinstance(result, dict)
                or not result.get('match_verified')
            ):

                draft.notes = (
                    'No verified exact model match was found. '
                    'Check the identifier and try again.'
                )

                draft.save(
                    update_fields=['notes', 'updated_at']
                )

                return JsonResponse({
                    'ok': False,
                    'draft_id': draft.pk,
                    'draft_url': reverse(
                        f'{self.admin_site.name}:core_productimportdraft_change',
                        args=[draft.pk],
                    ),
                    'error': 'No verified product match was found.',
                }, status=422)

            if not result.get('name') or not result.get('description'):
                raise ValueError(
                    'The manufacturer result is missing product information.'
                )

            draft.extracted_data = result

            if result.get('source_url'):
                draft.source_url = result['source_url']

            draft.notes = (
                'Manufacturer lookup completed successfully. '
                'Review specifications before importing into the catalogue.'
            )

            draft.save(update_fields=[
                'extracted_data',
                'source_url',
                'notes',
                'updated_at',
            ])

            return JsonResponse({
                'ok': True,
                'draft_id': draft.pk,
                'draft_url': reverse(
                    f'{self.admin_site.name}:core_productimportdraft_change',
                    args=[draft.pk],
                ),
                'lookup_completed': True,
                'manufacturer': result.get('manufacturer', ''),
                'product_name': result.get('name', ''),
                'model_number': result.get('model_number', ''),
                'category': result.get('category', ''),
                'tagline': result.get('tagline', ''),
                'description': result.get('description', ''),
                'capacity': result.get('capacity', ''),
                'power': result.get('power', ''),
                'warranty': result.get('warranty', ''),
                'image_url': result.get('image_url', ''),
                'source_url': result.get('source_url', ''),
                'message': 'Product details fetched successfully.',
            })

        except Exception as exc:

            draft.notes = (
                f'Manufacturer lookup failed: {str(exc)[:500]}'
            )

            draft.save(
                update_fields=['notes', 'updated_at']
            )

            return JsonResponse({
                'ok': False,
                'draft_id': draft.pk,
                'draft_url': reverse(
                    f'{self.admin_site.name}:core_productimportdraft_change',
                    args=[draft.pk],
                ),
                'error': (
                    'The identifier was saved, but manufacturer lookup failed: '
                    + str(exc)[:300]
                ),
            }, status=502)


# =====================================================
# PRODUCT IMPORT DRAFTS
# =====================================================

@admin.register(ProductImportDraft)
class ProductImportDraftAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'short_identifier',
        'status',
        'created_at',
        'updated_at',
    )

    list_filter = ('status', 'created_at')

    search_fields = (
        'raw_code',
        'source_url',
        'notes',
    )

    readonly_fields = (
        'raw_code',
        'source_url',
        'product',
        'created_at',
        'updated_at',
    )

    actions = [
        'fetch_product_details',
        'import_selected_products',
    ]

    fieldsets = (
        ('Scanned Information', {
            'fields': ('raw_code', 'source_url')
        }),
        ('Extracted Product Information', {
            'fields': ('extracted_data', 'notes')
        }),
        ('Import Status', {
            'fields': (
                'status',
                'product',
                'created_at',
                'updated_at',
            )
        }),
    )

    ordering = ('-created_at',)

    @admin.display(description='Scanned identifier')
    def short_identifier(self, obj):
        return obj.raw_code[:65]

    def has_add_permission(self, request):
        return False

    @admin.action(description='1. Fetch product details from Yunqida')
    def fetch_product_details(self, request, queryset):

        fetched = 0
        skipped = 0
        failed = 0

        selected = list(queryset[:5])

        for draft in selected:

            if draft.status != 'pending':
                skipped += 1
                continue

            model_number = draft.raw_code.strip()

            if model_number.lower().startswith(
                ('http://', 'https://')
            ):

                draft.notes = (
                    'Lookup not performed: this draft contains a URL. '
                    'Enter the product model number to perform the lookup.'
                )

                draft.save(
                    update_fields=['notes', 'updated_at']
                )

                failed += 1
                continue

            try:

                result = lookup_yunqida_model(model_number)

                if not isinstance(result, dict):
                    raise ValueError(
                        'The lookup returned an invalid result.'
                    )

                if not result.get('match_verified'):

                    draft.notes = (
                        'No verified exact model match was returned. '
                        'Review the model number and try again.'
                    )

                    draft.save(
                        update_fields=['notes', 'updated_at']
                    )

                    failed += 1
                    continue

                if not result.get('name') or not result.get('description'):

                    draft.notes = (
                        'A model match was found, but the product name '
                        'or description is missing.'
                    )

                    draft.save(
                        update_fields=['notes', 'updated_at']
                    )

                    failed += 1
                    continue

                draft.extracted_data = result

                if result.get('source_url'):
                    draft.source_url = result['source_url']

                warnings = result.get('warnings') or []

                draft.notes = (
                    'Manufacturer lookup completed. '
                    'Exact model match verified. '
                    'Review the extracted specifications before importing.'
                )

                if warnings:
                    draft.notes += ' Warnings: ' + '; '.join(
                        str(item) for item in warnings
                    )

                draft.save(update_fields=[
                    'extracted_data',
                    'source_url',
                    'notes',
                    'updated_at',
                ])

                fetched += 1

            except Exception as exc:

                draft.notes = (
                    f'Manufacturer lookup failed: {str(exc)[:500]}'
                )

                draft.save(
                    update_fields=['notes', 'updated_at']
                )

                failed += 1

        if fetched:
            self.message_user(
                request,
                f'{fetched} product detail lookup(s) completed. '
                'Open the drafts to review the results.',
                messages.SUCCESS,
            )

        if skipped:
            self.message_user(
                request,
                f'{skipped} draft(s) skipped because they were not pending.',
                messages.WARNING,
            )

        if failed:
            self.message_user(
                request,
                f'{failed} lookup(s) failed or need attention. '
                'Open the affected drafts to see the reason.',
                messages.ERROR,
            )

        if len(queryset) > 5:
            self.message_user(
                request,
                'Only the first five selected drafts were processed. '
                'Run the action again for the remaining drafts.',
                messages.WARNING,
            )

    @admin.action(description='2. Import reviewed products into catalogue')
    def import_selected_products(self, request, queryset):

        imported = 0
        skipped = 0
        failed = 0

        valid_categories = dict(Product.CATEGORY_CHOICES)

        for draft in queryset:

            if draft.status != 'pending':
                skipped += 1
                continue

            data = draft.extracted_data or {}

            if not isinstance(data, dict):
                failed += 1
                continue

            if not data.get('match_verified'):
                failed += 1
                continue

            name = str(data.get('name') or '').strip()
            description = str(data.get('description') or '').strip()
            tagline = str(data.get('tagline') or '').strip()
            category = str(data.get('category') or '').strip()
            model_number = str(data.get('model_number') or '').strip()

            if not name or not description:
                failed += 1
                continue

            if category not in valid_categories:
                failed += 1
                continue

            # Prevent duplicate products.
            if (
                Product.objects.filter(name__iexact=name).exists()
                or (
                    model_number
                    and Product.objects.filter(
                        manufacturer_model__iexact=model_number
                    ).exists()
                )
            ):
                skipped += 1
                continue

            # Generate a unique slug.
            base_slug = slugify(name)[:45] or 'product'
            slug = base_slug
            counter = 1

            while Product.objects.filter(slug=slug).exists():
                counter += 1
                slug = f'{base_slug}-{counter}'

            # -------------------------------------------------
            # PREPARE MANUFACTURER IMAGE URLS
            # -------------------------------------------------

            image_urls = data.get('image_urls') or []

            if not isinstance(image_urls, list):
                image_urls = []

            else:
                # Work on a copy; do not modify the draft JSON data.
                image_urls = list(image_urls)

            primary_url = data.get('image_url')

            if (
                isinstance(primary_url, str)
                and primary_url.strip()
                and primary_url.strip() not in image_urls
            ):
                image_urls.insert(0, primary_url.strip())

            # -------------------------------------------------
            # DOWNLOAD PRODUCT IMAGES
            # -------------------------------------------------

            try:
                downloaded_images, image_errors = (
                    download_product_images(image_urls)
                )

            except Exception as exc:

                downloaded_images = []
                image_errors = [
                    f'Image downloader error: {str(exc)[:300]}'
                ]

            # -------------------------------------------------
            # CREATE PRODUCT AND SAVE ITS IMAGES
            # -------------------------------------------------

            try:

                with transaction.atomic():

                    product = Product.objects.create(
                        name=name[:120],
                        slug=slug,
                        category=category,
                        tagline=(tagline or name)[:200],
                        description=description,
                        capacity=str(
                            data.get('capacity') or ''
                        )[:60],
                        power=str(
                            data.get('power') or ''
                        )[:60],
                        warranty=str(
                            data.get('warranty') or ''
                        )[:60],
                        technical_specifications=(
                            data.get('technical_specifications')
                            if isinstance(
                                data.get('technical_specifications'),
                                list,
                            )
                            else []
                        ),
                        manufacturer_model=model_number[:120],
                        manufacturer_url=str(
                            data.get('source_url') or draft.source_url
                        )[:200],
                    )

                    # First downloaded image becomes the main image.
                    if downloaded_images:

                        main_image = downloaded_images[0]

                        product.image.save(
                            main_image['filename'],
                            ContentFile(main_image['content']),
                            save=True,
                        )

                    # Remaining downloaded images become gallery images.
                    for index, image_data in enumerate(
                        downloaded_images[1:],
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
                            save=True,
                        )

                    # Update import draft.
                    draft.product = product
                    draft.status = 'imported'

                    notes = (
                        f'Imported successfully as Product #{product.pk}. '
                        f'{len(downloaded_images)} manufacturer image(s) '
                        'downloaded and saved. '
                    )

                    if downloaded_images:

                        notes += (
                            'The first successfully downloaded image '
                            'is the main product image. '
                            'The remaining images are in the gallery. '
                        )

                    else:

                        notes += (
                            'No manufacturer images could be downloaded. '
                            'You can upload images manually. '
                        )

                    if image_errors:

                        notes += (
                            f'{len(image_errors)} image download(s) failed. '
                            + ' '.join(image_errors[:3])
                        )

                    notes += (
                        f' Source: {draft.source_url or "Not provided"}.'
                    )

                    draft.notes = notes[:5000]

                    draft.save(update_fields=[
                        'product',
                        'status',
                        'notes',
                        'updated_at',
                    ])

                imported += 1

            except Exception as exc:

                failed += 1

                draft.notes = (
                    f'Import failed: {str(exc)[:500]}'
                )

                draft.save(
                    update_fields=['notes', 'updated_at']
                )

        # -------------------------------------------------
        # ADMIN RESULTS
        # -------------------------------------------------

        if imported:
            self.message_user(
                request,
                f'{imported} product(s) imported successfully, '
                'including their available manufacturer images.',
                messages.SUCCESS,
            )

        if skipped:
            self.message_user(
                request,
                f'{skipped} product(s) skipped because they were already '
                'processed or a matching product exists.',
                messages.WARNING,
            )

        if failed:
            self.message_user(
                request,
                f'{failed} product(s) could not be imported. '
                'Check their draft notes.',
                messages.ERROR,
            )


# =====================================================
# COMPLETED PROJECTS
# =====================================================

@admin.register(BuildProject)
class BuildProjectAdmin(admin.ModelAdmin):

    list_display = (
        'title',
        'project_type',
        'location',
        'order',
        'is_published',
        'created_at',
    )

    list_filter = (
        'project_type',
        'is_published',
        'created_at',
    )

    list_editable = ('order', 'is_published')

    search_fields = (
        'title',
        'location',
        'short_description',
        'description',
    )

    readonly_fields = ('created_at',)

    fieldsets = (
        ('Project Information', {
            'fields': (
                'title',
                'project_type',
                'location',
                'short_description',
                'description',
                'image',
            )
        }),
        ('Technical Specifications', {
            'fields': (
                'system_capacity',
                'battery_capacity',
                'solar_capacity',
                'inverter_specification',
                'application',
                'specifications',
            )
        }),
        ('Publishing', {
            'fields': (
                'order',
                'is_published',
                'created_at',
            )
        }),
    )


# =====================================================
# CUSTOMER ENQUIRIES
# =====================================================

@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):

    list_display = (
        'name',
        'phone',
        'interest',
        'product',
        'created',
        'handled',
    )

    list_filter = (
        'interest',
        'handled',
        'created',
    )

    list_editable = ('handled',)

    search_fields = (
        'name',
        'email',
        'phone',
        'message',
    )

    readonly_fields = ('created',)