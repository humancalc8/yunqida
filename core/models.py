from django.db import models
from django.urls import reverse


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
    capacity = models.CharField(max_length=60, blank=True, help_text='e.g. 5.12 kWh')
    power = models.CharField(max_length=60, blank=True, help_text='e.g. 5 kW')
    warranty = models.CharField(max_length=60, blank=True)
    image = models.ImageField(upload_to='products/', blank=True)
    fallback_image = models.CharField(
        max_length=120, blank=True, default='img/product-battery.svg',
        help_text='Static image path used when no photo is uploaded')
    featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('product_detail', args=[self.slug])


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
    interest = models.CharField(max_length=20, choices=INTEREST_CHOICES)
    message = models.TextField()
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created']
        verbose_name_plural = 'enquiries'

    def __str__(self):
        return f'{self.name} – {self.get_interest_display()}'
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

    short_description = models.CharField(
        max_length=250
    )

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