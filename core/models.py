
from django.db import models
from django.urls import reverse


# =====================================================
# PRODUCTS
# =====================================================

class Product(models.Model):

    CATEGORY_CHOICES = [
        ('residential', 'Home energy storage'),
        ('commercial', 'Commercial & industrial'),
        ('battery', 'Lithium batteries'),
        ('solar', 'Solar systems'),
    ]

    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)

    tagline = models.CharField(max_length=200)
    description = models.TextField()

    capacity = models.CharField(
        max_length=60,
        blank=True,
        help_text='e.g. 5.12 kWh'
    )

    power = models.CharField(
        max_length=60,
        blank=True,
        help_text='e.g. 5 kW'
    )

    warranty = models.CharField(max_length=60, blank=True)
    technical_specifications = models.JSONField(
    default=list,
    blank=True,
    help_text='Structured technical specifications supplied by the manufacturer.'
)

    # Manufacturer identification
    manufacturer_model = models.CharField(
        max_length=120,
        blank=True,
        db_index=True,
        help_text='Official manufacturer model number.'
    )

    manufacturer_url = models.URLField(
        blank=True,
        help_text='Original manufacturer product page.'
    )

    # Main product image
    image = models.ImageField(
        upload_to='products/',
        blank=True
    )

    fallback_image = models.CharField(
        max_length=120,
        blank=True,
        default='img/product-battery.svg',
        help_text='Static image path used when no photo is uploaded.'
    )

    featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('product_detail', args=[self.slug])


# =====================================================
# PRODUCT GALLERY IMAGES
# =====================================================

class ProductImage(models.Model):

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='gallery_images'
    )

    image = models.ImageField(
        upload_to='products/gallery/'
    )

    alt_text = models.CharField(
        max_length=200,
        blank=True
    )

    source_url = models.URLField(
        blank=True,
        help_text='Original image URL from the manufacturer.'
    )

    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Product Gallery Image'
        verbose_name_plural = 'Product Gallery Images'

    def __str__(self):
        return f'{self.product.name} - Image {self.pk}'



class ProductImportDraft(models.Model):

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('imported', 'Imported'),
        ('failed', 'Needs Attention'),
    ]

    LOOKUP_STATUS_CHOICES = [
        ('idle', 'Not Started'),
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    raw_code = models.TextField(
        help_text="Scanned QR content or manually entered model number."
    )

    source_url = models.URLField(
        blank=True,
        help_text="Official manufacturer product page."
    )

    extracted_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Verified product information extracted from the manufacturer."
    )

    # Existing product import status. Keep separate from lookup status.
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
    )

    # Manufacturer lookup tracking.
    lookup_status = models.CharField(
        max_length=20,
        choices=LOOKUP_STATUS_CHOICES,
        default='idle',
        db_index=True,
    )

    lookup_started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    lookup_finished_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    lookup_error = models.TextField(
        blank=True,
    )

    notes = models.TextField(
        blank=True,
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='import_drafts',
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Product Import Draft'
        verbose_name_plural = 'Product Import Drafts'

    def __str__(self):
        return f"Draft #{self.pk} - {self.raw_code[:80]}"

# =====================================================
# CUSTOMER ENQUIRIES
# =====================================================

class Enquiry(models.Model):

    INTEREST_CHOICES = [
        ('home', 'Home solar & storage'),
        ('business', 'Business / commercial'),
        ('industrial', 'Industrial / large scale'),
        ('distributor', 'Distribution / partnership'),
        ('other', 'Something else'),
    ]

    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30)

    interest = models.CharField(
        max_length=20,
        choices=INTEREST_CHOICES
    )

    message = models.TextField()

    product = models.ForeignKey(
        Product,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    created = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created']
        verbose_name_plural = 'enquiries'

    def __str__(self):
        return f'{self.name} – {self.get_interest_display()}'


# =====================================================
# COMPLETED PROJECTS
# =====================================================

class BuildProject(models.Model):

    PROJECT_TYPES = [
        ('residential', 'Residential Installation'),
        ('commercial', 'Commercial Installation'),
        ('industrial', 'Industrial Installation'),
        ('solar', 'Solar Power System'),
        ('energy_storage', 'Energy Storage System'),
        ('hybrid', 'Hybrid Energy System'),
    ]

    title = models.CharField(max_length=150)

    project_type = models.CharField(
        max_length=30,
        choices=PROJECT_TYPES
    )

    location = models.CharField(
        max_length=150,
        blank=True
    )

    short_description = models.CharField(max_length=250)

    description = models.TextField()

    image = models.ImageField(
        upload_to='build_projects/'
    )

    system_capacity = models.CharField(
        max_length=100,
        blank=True,
        help_text='e.g. 50 kW'
    )

    battery_capacity = models.CharField(
        max_length=100,
        blank=True,
        help_text='e.g. 100 kWh'
    )

    solar_capacity = models.CharField(
        max_length=100,
        blank=True,
        help_text='e.g. 80 kWp'
    )

    inverter_specification = models.CharField(
        max_length=150,
        blank=True,
        help_text='e.g. 50 kW Hybrid Inverter'
    )

    application = models.CharField(
        max_length=150,
        blank=True,
        help_text='e.g. Factory, residential home, commercial building'
    )

    specifications = models.TextField(
        blank=True,
        help_text='Additional technical specifications and project details.'
    )

    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = 'Build Project'
        verbose_name_plural = 'Build Projects'

    def __str__(self):
        return self.title
