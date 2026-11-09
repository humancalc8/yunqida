
from django.contrib import admin
from .models import Enquiry, Product, BuildProject


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'category',
        'capacity',
        'power',
        'featured',
        'order',
    )
    list_filter = ('category', 'featured')
    list_editable = ('featured', 'order')
    search_fields = ('name', 'tagline')
    prepopulated_fields = {'slug': ('name',)}


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

    list_editable = (
        'order',
        'is_published',
    )

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

    list_filter = ('interest', 'handled', 'created')
    list_editable = ('handled',)
    search_fields = ('name', 'email', 'phone', 'message')
    readonly_fields = ('created',)
