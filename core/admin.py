
import json
from urllib.parse import urlsplit
from django.utils.html import format_html
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import (
    get_object_or_404,
    render,
    redirect,
)
from django.urls import path, reverse
from django.utils.text import slugify

from .models import (
    Enquiry,
    Product,
    ProductImage,
    BuildProject,
    ProductImportDraft,
    ImportedCatalogueProduct,
    BlogPost,
    BlogImage,
)

from .services.product_images import download_product_images

from .services.blog_writer import (
    generate_blog_article,
    save_generated_blog_article,
)

from .services.groq_ai import GroqAIError


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

    # -------------------------------------------------
    # CUSTOM ADMIN URLS
    # -------------------------------------------------

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path(
                'scanner/submit/',
                self.admin_site.admin_view(self.submit_scan),
                name='core_product_scanner_submit',
            ),
            path(
                'scanner/status/<int:draft_id>/',
                self.admin_site.admin_view(self.scan_status),
                name='core_product_scanner_status',
            ),
            path(
                'scanner/',
                self.admin_site.admin_view(self.product_scanner),
                name='core_product_scanner',
            ),
        ]

        return custom_urls + urls

    # -------------------------------------------------
    # SCANNER PAGE
    # -------------------------------------------------

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
            'status_url_template': reverse(
                f'{self.admin_site.name}:core_product_scanner_status',
                args=[0],
            ),
        }

        return render(
            request,
            'admin/core/product/scanner.html',
            context,
        )

    # -------------------------------------------------
    # SUBMIT SCANNER LOOKUP
    # -------------------------------------------------

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

        # Detect URL input.
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

        # Create or retrieve draft.
        draft, created = ProductImportDraft.objects.get_or_create(
            raw_code=value,
            status='pending',
            defaults={
                'source_url': source_url,
                'notes': 'Captured using the YUNQIDA Product Scanner.',
            },
        )

        # URL input: save without lookup.
        if source_url:
            if not draft.source_url:
                draft.source_url = source_url
                draft.save(
                    update_fields=['source_url', 'updated_at']
                )

            return JsonResponse({
                'ok': True,
                'draft_id': draft.pk,
                'draft_url': reverse(
                    f'{self.admin_site.name}:core_productimportdraft_change',
                    args=[draft.pk],
                ),
                'lookup_completed': False,
                'lookup_status': draft.lookup_status,
                'message': (
                    'URL saved. Enter the actual product model number '
                    'to fetch specifications.'
                ),
            })

        # Queue model lookup.
        if draft.status != 'pending':
            return JsonResponse({
                'ok': False,
                'error': (
                    'This draft has already been imported or marked '
                    'for attention. Open the draft in the admin.'
                ),
            }, status=409)

        draft.lookup_status = 'queued'
        draft.lookup_started_at = None
        draft.lookup_finished_at = None
        draft.lookup_error = ''
        draft.extracted_data = {}

        draft.notes = (
            'Manufacturer lookup queued. '
            'Waiting for the background worker.'
        )

        draft.save(update_fields=[
            'lookup_status',
            'lookup_started_at',
            'lookup_finished_at',
            'lookup_error',
            'extracted_data',
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
            'status_url': reverse(
                f'{self.admin_site.name}:core_product_scanner_status',
                args=[draft.pk],
            ),
            'lookup_completed': False,
            'lookup_status': 'queued',
            'message': (
                'Product model saved. Manufacturer lookup has been '
                'queued and will begin shortly.'
            ),
        }, status=202)

    # -------------------------------------------------
    # SCANNER STATUS ENDPOINT
    # -------------------------------------------------

    def scan_status(self, request, draft_id):
        if request.method != 'GET':
            return JsonResponse(
                {
                    'ok': False,
                    'error': 'GET requests only.',
                },
                status=405,
            )

        if not self.has_view_permission(request):
            raise PermissionDenied

        draft = get_object_or_404(
            ProductImportDraft,
            pk=draft_id,
        )

        if not self.has_view_permission(request, draft):
            raise PermissionDenied

        data = draft.extracted_data or {}

        response_data = {
            'ok': True,
            'draft_id': draft.pk,
            'lookup_status': draft.lookup_status,
            'lookup_completed': draft.lookup_status == 'completed',
            'error': draft.lookup_error,
            'message': '',
            'draft_url': reverse(
                f'{self.admin_site.name}:core_productimportdraft_change',
                args=[draft.pk],
            ),
        }

        if draft.lookup_status == 'queued':
            response_data['message'] = (
                'Your product lookup is queued and waiting for the worker.'
            )

        elif draft.lookup_status == 'processing':
            response_data['message'] = (
                'Searching the official YUNQIDA manufacturer catalogue...'
            )

        elif draft.lookup_status == 'failed':
            response_data['message'] = (
                draft.lookup_error or 'Manufacturer lookup failed.'
            )

        elif draft.lookup_status == 'completed':
            response_data.update({
                'manufacturer': data.get('manufacturer', ''),
                'product_name': data.get('name', ''),
                'model_number': data.get('model_number', ''),
                'category': data.get('category', ''),
                'tagline': data.get('tagline', ''),
                'description': data.get('description', ''),
                'capacity': data.get('capacity', ''),
                'power': data.get('power', ''),
                'warranty': data.get('warranty', ''),
                'image_url': data.get('image_url', ''),
                'source_url': data.get('source_url') or draft.source_url,
                'message': 'Product details fetched successfully.',
            })

        else:
            response_data['message'] = (
                'No manufacturer lookup has been started for this draft.'
            )

        return JsonResponse(response_data)


@admin.register(ProductImportDraft)
class ProductImportDraftAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'short_identifier',
        'status',
        'lookup_status',
        'error_reason',
        'fix_link',
        'created_at',
        'updated_at',
    )

    list_filter = (
        'status',
        'lookup_status',
        'created_at',
    )

    search_fields = (
        'raw_code',
        'source_url',
        'notes',
        'lookup_error',
    )

    readonly_fields = (
        'raw_code',
        'source_url',
        'product',
        'lookup_status',
        'lookup_started_at',
        'lookup_finished_at',
        'lookup_error',
        'created_at',
        'updated_at',
    )

    actions = [
        'fetch_product_details',
        'import_selected_products',
        'fix_selected_drafts',
    ]

    fieldsets = (
        ('Scanned Information', {
            'fields': (
                'raw_code',
                'source_url',
            )
        }),
        ('Manufacturer Lookup', {
            'fields': (
                'lookup_status',
                'lookup_started_at',
                'lookup_finished_at',
                'lookup_error',
            )
        }),
        ('Extracted Product Information', {
            'fields': (
                'extracted_data',
                'notes',
            )
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

    # -------------------------------------------------
    # CUSTOM URLS
    # -------------------------------------------------

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path(
                '<int:draft_id>/fix/',
                self.admin_site.admin_view(self.fix_draft),
                name='core_productimportdraft_fix',
            ),
        ]

        return custom_urls + urls

    # -------------------------------------------------
    # LIST DISPLAY
    # -------------------------------------------------

    @admin.display(description='Scanned identifier')
    def short_identifier(self, obj):
        return obj.raw_code[:65]

    @admin.display(description='Reason / Error')
    def error_reason(self, obj):
        if obj.status == 'imported':
            return 'Imported successfully'

        if obj.lookup_status == 'failed' and obj.lookup_error:
            return obj.lookup_error[:180]

        if obj.notes:
            return obj.notes[:180]

        if obj.lookup_status == 'processing':
            return 'Manufacturer lookup is currently processing.'

        if obj.lookup_status == 'queued':
            return 'Waiting for the manufacturer lookup worker.'

        if obj.lookup_status == 'completed':
            return 'Details fetched. Ready for import.'

        return 'No error information recorded.'

    @admin.display(description='Action')
    def fix_link(self, obj):
        if obj.status == 'imported':
            return 'Imported'

        url = reverse(
            f'{self.admin_site.name}:core_productimportdraft_fix',
            args=[obj.pk],
        )

        return format_html(
            '<a class="button" href="{}">Fix</a>',
            url,
        )

    # -------------------------------------------------
    # PERMISSIONS
    # -------------------------------------------------

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.exclude(status='imported')

    # -------------------------------------------------
    # SAVE FAILURE REASONS
    # -------------------------------------------------

    def save_import_error(self, draft, message):
        draft.notes = f'IMPORT FAILED: {message}'[:5000]

        draft.save(update_fields=[
            'notes',
            'updated_at',
        ])

    # -------------------------------------------------
    # QUEUE A MANUFACTURER LOOKUP
    # -------------------------------------------------

    def queue_lookup(self, draft):
        model_number = draft.raw_code.strip()

        if model_number.lower().startswith(
            ('http://', 'https://')
        ):
            raise ValueError(
                'This draft contains a URL instead of a product model '
                'number. Enter the actual manufacturer model number '
                'in the scanned identifier before retrying.'
            )

        if not model_number:
            raise ValueError(
                'The product model number is empty.'
            )

        draft.lookup_status = 'queued'
        draft.lookup_started_at = None
        draft.lookup_finished_at = None
        draft.lookup_error = ''
        draft.extracted_data = {}

        draft.notes = (
            'Manufacturer lookup queued for retry. '
            'Waiting for the background worker.'
        )

        draft.save(update_fields=[
            'lookup_status',
            'lookup_started_at',
            'lookup_finished_at',
            'lookup_error',
            'extracted_data',
            'notes',
            'updated_at',
        ])

    # -------------------------------------------------
    # IMPORT ONE DRAFT
    # -------------------------------------------------

    def import_one_draft(self, draft):
        if draft.status == 'imported':
            return 'skipped', 'This draft has already been imported.'

        if draft.lookup_status != 'completed':
            return (
                'failed',
                'Manufacturer lookup has not completed. '
                'Retry the manufacturer lookup first.',
            )

        data = draft.extracted_data

        if not isinstance(data, dict):
            message = (
                'The extracted manufacturer information is invalid. '
                'Run the manufacturer lookup again.'
            )
            self.save_import_error(draft, message)
            return 'failed', message

        if not data.get('match_verified'):
            message = (
                'The manufacturer result has not passed exact model '
                'verification. Run the lookup again.'
            )
            self.save_import_error(draft, message)
            return 'failed', message

        name = str(data.get('name') or '').strip()
        description = str(data.get('description') or '').strip()
        tagline = str(data.get('tagline') or '').strip()
        category = str(data.get('category') or '').strip()
        model_number = str(data.get('model_number') or '').strip()

        if not name:
            message = (
                'The extracted product name is missing. '
                'Correct the extracted product information and click Fix.'
            )
            self.save_import_error(draft, message)
            return 'failed', message

        if not description:
            message = (
                'The product description is missing. '
                'Correct the extracted product information and click Fix.'
            )
            self.save_import_error(draft, message)
            return 'failed', message

        valid_categories = dict(Product.CATEGORY_CHOICES)

        if category not in valid_categories:
            message = (
                f'Invalid product category: "{category}". '
                f'Allowed categories are: {", ".join(valid_categories.keys())}. '
                'Correct the category in extracted product information.'
            )
            self.save_import_error(draft, message)
            return 'failed', message

        # -------------------------------------------------
        # DUPLICATE DETECTION
        # -------------------------------------------------

        existing_product = None

        if model_number:
            existing_product = Product.objects.filter(
                manufacturer_model__iexact=model_number
            ).first()

        if existing_product is None:
            existing_product = Product.objects.filter(
                name__iexact=name
            ).first()

        if existing_product:
            draft.product = existing_product
            draft.status = 'imported'

            draft.notes = (
                f'DUPLICATE DETECTED. This product already exists in the '
                f'catalogue as Product #{existing_product.pk} '
                f'({existing_product.name}). '
                f'The draft has been linked to the existing product '
                f'instead of creating a duplicate.'
            )

            draft.save(update_fields=[
                'product',
                'status',
                'notes',
                'updated_at',
            ])

            return (
                'skipped',
                f'Already exists as Product #{existing_product.pk}. '
                'Draft linked to the existing product.',
            )

        # -------------------------------------------------
        # GENERATE UNIQUE SLUG
        # -------------------------------------------------

        base_slug = slugify(name)[:45] or 'product'
        slug = base_slug
        counter = 1

        while Product.objects.filter(slug=slug).exists():
            counter += 1
            slug = f'{base_slug}-{counter}'

        # -------------------------------------------------
        # PREPARE IMAGE URLS
        # -------------------------------------------------

        image_urls = data.get('image_urls') or []

        if not isinstance(image_urls, list):
            image_urls = []

        image_urls = list(image_urls)

        primary_url = data.get('image_url')

        if (
            isinstance(primary_url, str)
            and primary_url.strip()
            and primary_url.strip() not in image_urls
        ):
            image_urls.insert(0, primary_url.strip())

        # -------------------------------------------------
        # DOWNLOAD IMAGES
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
        # CREATE PRODUCT
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

                # Main product image.
                if downloaded_images:
                    main_image = downloaded_images[0]

                    product.image.save(
                        main_image['filename'],
                        ContentFile(main_image['content']),
                        save=True,
                    )

                # Additional gallery images.
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

                # Mark the draft as imported.
                draft.product = product
                draft.status = 'imported'

                notes = (
                    f'Imported successfully as Product #{product.pk}. '
                    f'{len(downloaded_images)} manufacturer image(s) '
                    'downloaded and saved. '
                )

                if downloaded_images:
                    notes += (
                        'The first downloaded image is the main product '
                        'image. Remaining images are in the gallery. '
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

            return (
                'imported',
                f'Successfully imported as Product #{product.pk}.',
            )

        except Exception as exc:
            message = (
                f'{type(exc).__name__}: {str(exc)}'
            )[:4000]

            self.save_import_error(draft, message)

            return 'failed', message

    # -------------------------------------------------
    # INDIVIDUAL FIX BUTTON
    # -------------------------------------------------

    def fix_draft(self, request, draft_id):
        draft = get_object_or_404(
            ProductImportDraft,
            pk=draft_id,
        )

        if not self.has_change_permission(request, draft):
            raise PermissionDenied

        if draft.status == 'imported':
            self.message_user(
                request,
                'This draft has already been imported.',
                messages.INFO,
            )

            return redirect(
                reverse(
                    f'{self.admin_site.name}:core_productimportdraft_changelist'
                )
            )

        # If lookup is complete, retry the import.
        if draft.lookup_status == 'completed':
            result, message = self.import_one_draft(draft)

            if result == 'imported':
                self.message_user(
                    request,
                    message,
                    messages.SUCCESS,
                )

            elif result == 'skipped':
                self.message_user(
                    request,
                    message,
                    messages.WARNING,
                )

            else:
                self.message_user(
                    request,
                    message,
                    messages.ERROR,
                )

        # Do not queue another lookup while one is already running.
        elif draft.lookup_status in ('queued', 'processing'):
            self.message_user(
                request,
                (
                    'This manufacturer lookup is already '
                    f'{draft.lookup_status}. Wait for it to finish.'
                ),
                messages.WARNING,
            )

        # Otherwise retry the manufacturer lookup.
        else:
            try:
                self.queue_lookup(draft)

                self.message_user(
                    request,
                    (
                        'Manufacturer lookup queued again. '
                        'The background worker must be running.'
                    ),
                    messages.SUCCESS,
                )

            except ValueError as exc:
                draft.lookup_status = 'failed'
                draft.lookup_error = str(exc)

                draft.save(update_fields=[
                    'lookup_status',
                    'lookup_error',
                    'updated_at',
                ])

                self.message_user(
                    request,
                    str(exc),
                    messages.ERROR,
                )

        return redirect(
            reverse(
                f'{self.admin_site.name}:core_productimportdraft_change',
                args=[draft.pk],
            )
        )

    # -------------------------------------------------
    # QUEUE PRODUCT LOOKUPS
    # -------------------------------------------------

    @admin.action(description='1. Fetch product details from Yunqida')
    def fetch_product_details(self, request, queryset):
        queued = 0
        skipped = 0
        errors = 0

        for draft in queryset[:5]:

            if draft.status != 'pending':
                skipped += 1
                continue

            try:
                self.queue_lookup(draft)
                queued += 1

            except ValueError as exc:
                draft.lookup_status = 'failed'
                draft.lookup_error = str(exc)

                draft.save(update_fields=[
                    'lookup_status',
                    'lookup_error',
                    'updated_at',
                ])

                errors += 1

        if queued:
            self.message_user(
                request,
                (
                    f'{queued} manufacturer lookup(s) queued. '
                    'The background worker must be running.'
                ),
                messages.SUCCESS,
            )

        if skipped:
            self.message_user(
                request,
                f'{skipped} draft(s) skipped because they are not pending.',
                messages.WARNING,
            )

        if errors:
            self.message_user(
                request,
                f'{errors} draft(s) could not be queued. Check their error reasons.',
                messages.ERROR,
            )

        if queryset.count() > 5:
            self.message_user(
                request,
                'Only the first five selected drafts were queued.',
                messages.WARNING,
            )

    # -------------------------------------------------
    # IMPORT SELECTED PRODUCTS
    # -------------------------------------------------

    @admin.action(description='2. Import reviewed products into catalogue')
    def import_selected_products(self, request, queryset):
        imported = 0
        skipped = 0
        failed = 0

        for draft in queryset:
            result, message = self.import_one_draft(draft)

            if result == 'imported':
                imported += 1
            elif result == 'skipped':
                skipped += 1
            else:
                failed += 1

        if imported:
            self.message_user(
                request,
                f'{imported} product(s) imported successfully.',
                messages.SUCCESS,
            )

        if skipped:
            self.message_user(
                request,
                (
                    f'{skipped} draft(s) were already processed or '
                    'matched existing catalogue products.'
                ),
                messages.WARNING,
            )

        if failed:
            self.message_user(
                request,
                (
                    f'{failed} product(s) could not be imported. '
                    'Open each draft to see its recorded reason and use Fix '
                    'after correcting the information.'
                ),
                messages.ERROR,
            )

    # -------------------------------------------------
    # FIX SELECTED DRAFTS
    # -------------------------------------------------

    @admin.action(description='3. Fix selected failed or incomplete drafts')
    def fix_selected_drafts(self, request, queryset):
        queued = 0
        imported = 0
        skipped = 0
        failed = 0

        for draft in queryset:

            if draft.status == 'imported':
                skipped += 1
                continue

            if draft.lookup_status == 'completed':
                result, message = self.import_one_draft(draft)

                if result == 'imported':
                    imported += 1
                elif result == 'skipped':
                    skipped += 1
                else:
                    failed += 1

            elif draft.lookup_status in ('queued', 'processing'):
                skipped += 1

            else:
                try:
                    self.queue_lookup(draft)
                    queued += 1

                except ValueError as exc:
                    draft.lookup_status = 'failed'
                    draft.lookup_error = str(exc)

                    draft.save(update_fields=[
                        'lookup_status',
                        'lookup_error',
                        'updated_at',
                    ])

                    failed += 1

        if queued:
            self.message_user(
                request,
                f'{queued} manufacturer lookup(s) queued for retry.',
                messages.SUCCESS,
            )

        if imported:
            self.message_user(
                request,
                f'{imported} product(s) imported successfully.',
                messages.SUCCESS,
            )

        if skipped:
            self.message_user(
                request,
                f'{skipped} draft(s) skipped because they are already processing or matched existing products.',
                messages.WARNING,
            )

        if failed:
            self.message_user(
                request,
                (
                    f'{failed} draft(s) still need attention. '
                    'Check the individual error reasons.'
                ),
                messages.ERROR,
            )


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


# =====================================================
# BLOG IMAGE GALLERY
# =====================================================

class BlogImageInline(admin.TabularInline):

    model = BlogImage
    extra = 1

    fields = (
        'image',
        'alt_text',
        'caption',
        'order',
    )

    ordering = ('order', 'id')


# =====================================================
# BLOG POSTS
# =====================================================

@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):

    change_list_template = 'admin/core/blogpost/change_list.html'

    inlines = [BlogImageInline]

    list_display = (
        'title',
        'category',
        'status',
        'ai_generated',
        'published_at',
        'updated_at',
    )

    list_filter = (
        'status',
        'category',
        'ai_generated',
        'created_at',
    )

    search_fields = (
        'title',
        'excerpt',
        'content',
        'focus_keyword',
    )

    readonly_fields = (
        'created_at',
        'updated_at',
        'published_at',
    )

    fieldsets = (
        ('Article Information', {
            'fields': (
                'title',
                'slug',
                'category',
                'excerpt',
                'content',
            )
        }),
        ('Featured Image', {
            'fields': (
                'featured_image',
                'featured_image_alt',
            )
        }),
        ('Search Engine Optimisation', {
            'fields': (
                'seo_title',
                'meta_description',
                'focus_keyword',
                'secondary_keywords',
                'seo_analysis',
            )
        }),
        ('AI Generation Information', {
            'fields': (
                'ai_generated',
                'original_prompt',
            )
        }),
        ('Publishing', {
            'fields': (
                'status',
                'published_at',
                'created_at',
                'updated_at',
            )
        }),
    )

    ordering = ('-created_at',)

    # -------------------------------------------------
    # CUSTOM ADMIN URLS
    # -------------------------------------------------

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path(
                'ai-writer/',
                self.admin_site.admin_view(self.ai_writer),
                name='core_blogpost_ai_writer',
            ),
        ]

        return custom_urls + urls

    # -------------------------------------------------
    # AI BLOG WRITER
    # -------------------------------------------------

    def ai_writer(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied

        request.current_app = self.admin_site.name

        if request.method == 'POST':
            topic = request.POST.get('topic', '').strip()

            try:
                article_data = generate_blog_article(
                    topic=topic,
                )

                post = save_generated_blog_article(article_data)

                messages.success(
                    request,
                    'Your AI-generated article has been saved as a draft. '
                    'Review the article, SEO information and images before '
                    'publishing.',
                )

                return redirect(
                    reverse(
                        f'{self.admin_site.name}:core_blogpost_change',
                        args=[post.pk],
                    )
                )

            except GroqAIError as exc:
                messages.error(request, str(exc))

            except Exception:
                messages.error(
                    request,
                    'The article could not be generated or saved. '
                    'Please try again. If the problem continues, '
                    'check the application logs.',
                )

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'YUNQIDA AI Blog Writer',
        }

        return render(
            request,
            'admin/core/blogpost/ai_writer.html',
            context,
        )

@admin.register(ImportedCatalogueProduct)
class ImportedCatalogueProductAdmin(ProductAdmin):

    # Use the standard admin list page, without the product scanner button.
    change_list_template = 'admin/change_list.html'

    # Do not inherit the scanner URLs from ProductAdmin.
    def get_urls(self):
        return admin.ModelAdmin.get_urls(self)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(import_drafts__status='imported')
            .distinct()
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
