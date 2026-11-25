from django.conf import settings
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from .models import Product, BuildProject, BlogPost
from .forms import EnquiryForm
from .models import Product, BuildProject
from .google_reviews import get_google_reviews

from django.db.models import TextField
from django.db.models.functions import Cast
def home(request):
    featured = Product.objects.filter(featured=True)[:3]

    # Latest six products for the What We Manufacture homepage section
    manufacture_products = Product.objects.order_by('-id')[:6]

    # Published projects for the What We Build homepage section
    build_projects = BuildProject.objects.filter(
        is_published=True
    )

    context = {
        'featured': featured,
        'manufacture_products': manufacture_products,
        'build_projects': build_projects,
    }

    # Fetch Google Business Profile rating and reviews
    context.update(get_google_reviews())

    return render(request, 'core/home.html', context)


def about(request):
    return render(request, 'core/about.html')


def solutions(request):
    return render(request, 'core/solutions.html')



def products(request):
    category = request.GET.get('category', '').strip()
    capacity = request.GET.get('capacity', '').strip()
    power = request.GET.get('power', '').strip()
    voltage = request.GET.get('voltage', '').strip()

    items = Product.objects.all().annotate(
        specifications_text=Cast(
            'technical_specifications',
            output_field=TextField()
        )
    )

    # Category filter
    if category in dict(Product.CATEGORY_CHOICES):
        items = items.filter(category=category)
    else:
        category = ''

    # Capacity filter
    if capacity:
        items = items.filter(capacity__icontains=capacity)

    # Power filter
    if power:
        items = items.filter(power__icontains=power)

    # Voltage filter (stored in technical specifications)
    if voltage:
        items = items.filter(
            specifications_text__icontains=voltage
        )

    # Pagination: maximum 17 products per page
    paginator = Paginator(items, 17)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Preserve active filters when navigating pages
    query_params = request.GET.copy()
    query_params.pop('page', None)
    pagination_query = query_params.urlencode()

    return render(request, 'core/products.html', {
        'products': page_obj.object_list,
        'page_obj': page_obj,
        'categories': Product.CATEGORY_CHOICES,
        'active_category': category,
        'active_capacity': capacity,
        'active_power': power,
        'active_voltage': voltage,
        'pagination_query': pagination_query,
        'result_count': paginator.count,
    })

def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.prefetch_related('gallery_images'),
        slug=slug
    )

    related = Product.objects.filter(
        category=product.category
    ).exclude(pk=product.pk)[:3]

    return render(request, 'core/product_detail.html', {
        'product': product,
        'related': related,
        'gallery_images': product.gallery_images.all(),
    })


@require_http_methods(['GET', 'POST'])
def contact(request):
    product = None
    slug = request.GET.get('product')

    if slug:
        product = Product.objects.filter(slug=slug).first()

    if request.method == 'POST':
        form = EnquiryForm(request.POST)

        if form.is_valid():
            enquiry = form.save(commit=False)

            if product:
                enquiry.product = product

            enquiry.save()

            try:
                send_mail(
                    subject=f'New website enquiry from {enquiry.name}',
                    message=(
                        f'Name: {enquiry.name}\n'
                        f'Phone: {enquiry.phone}\n'
                        f'Email: {enquiry.email}\n'
                        f'Interest: {enquiry.get_interest_display()}\n'
                        f'Product: {enquiry.product or "-"}\n\n'
                        f'{enquiry.message}'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=settings.ENQUIRY_NOTIFY_TO,
                )
            except Exception:
                pass

            messages.success(
                request,
                'Thank you. We have received your message and will call you within one working day.'
            )

            return redirect('contact')

    else:
        initial = {}

        if product:
            initial['message'] = (
                f'I would like a quote for the {product.name}.'
            )

        form = EnquiryForm(initial=initial)

    return render(request, 'core/contact.html', {
        'form': form,
        'product': product,
    })

# ---------- views.py ----------
from django.shortcuts import render

# Replace these with Yunqida's real services.
# Later you can swap this list for a Service model: Service.objects.all()
SERVICES = [
    {
        "slug": "consulting",
        "title": "Consulting",
        "summary": "We look at how your business runs today and show you where time and money are leaking.",
        "points": ["Process review", "Cost analysis", "Written action plan"],
    },
    {
        "slug": "sourcing",
        "title": "Sourcing and procurement",
        "summary": "We find reliable suppliers, check them, and handle negotiation so you buy at fair prices.",
        "points": ["Supplier vetting", "Price negotiation", "Quality checks before shipping"],
    },
    {
        "slug": "logistics",
        "title": "Logistics and delivery",
        "summary": "From pickup to your door, we plan the route, handle paperwork, and keep you updated.",
        "points": ["Freight booking", "Customs paperwork", "Shipment tracking"],
    },
    {
        "slug": "support",
        "title": "After-sales support",
        "summary": "When something goes wrong, you talk to one person who owns the problem until it is fixed.",
        "points": ["Single point of contact", "Replacement handling", "Monthly check-ins"],
    },
]


def services(request):
    return render(request, "core/services.html", {"services": SERVICES})

# ---------- views.py ----------
from django.shortcuts import render


def works_done(request):
    return render(request, "works_done.html")


def blog_list(request):
    """
    Public blog homepage.
    Only published articles are displayed.
    """

    articles = BlogPost.objects.filter(
        status='published'
    ).order_by('-published_at', '-created_at')

    active_category = request.GET.get('category', '').strip()

    if active_category:
        articles = articles.filter(category=active_category)

    categories = (
        BlogPost.objects.filter(status='published')
        .values_list('category', flat=True)
        .distinct()
    )

    paginator = Paginator(articles, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    posts = page_obj.object_list

    featured_post = posts[0] if posts else None

    context = {
        'posts': posts,
        'articles': posts,
        'featured_post': featured_post,
        'categories': categories,
        'active_category': active_category,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
    }

    return render(request, 'core/blog/blog_list.html', context)



def blog_detail(request, slug):
    """
    Individual published blog article.
    """
    article = get_object_or_404(
        BlogPost.objects.filter(status='published'),
        slug=slug
    )

    related_articles = (
        BlogPost.objects.filter(
            status='published',
            category=article.category
        )
        .exclude(pk=article.pk)
        .order_by('-published_at', '-created_at')[:3]
    )

    return render(request, 'core/blog/blog_detail.html', {
        'article': article,
        'related_articles': related_articles,
    })

@require_GET
def product_search(request):
    query = request.GET.get('q', '').strip()

    # Do not search for empty or extremely short queries.
    if len(query) < 1:
        return JsonResponse({
            'query': query,
            'results': [],
            'count': 0,
        })

    # Normalise common capacity and power formats.
    normalised_query = (
        query.lower()
        .replace(' ', '')
        .replace('kilowatt', 'kw')
        .replace('kilowatt-hour', 'kwh')
        .replace('kilowatt hour', 'kwh')
    )

    products = Product.objects.all()

    # Search all important product fields.
    filters = (
        Q(name__icontains=query)
        | Q(manufacturer_model__icontains=query)
        | Q(category__icontains=query)
        | Q(tagline__icontains=query)
        | Q(description__icontains=query)
        | Q(capacity__icontains=query)
        | Q(power__icontains=query)
        | Q(warranty__icontains=query)
        | Q(technical_specifications__icontains=query)
    )

    if normalised_query != query.lower():
        filters |= (
            Q(name__icontains=normalised_query)
            | Q(capacity__icontains=normalised_query)
            | Q(power__icontains=normalised_query)
            | Q(technical_specifications__icontains=normalised_query)
        )

    matches = products.filter(filters).distinct().order_by(
        'order', 'name'
    )

    results = []

    for product in matches[:8]:
        image_url = ''

        if product.image:
            image_url = product.image.url
        elif product.fallback_image:
            image_url = (
                '/static/' + product.fallback_image
            )

        results.append({
            'name': product.name,
            'category': product.get_category_display(),
            'capacity': product.capacity,
            'power': product.power,
            'image': image_url,
            'url': reverse(
                'product_detail',
                kwargs={'slug': product.slug}
            ),
        })

    return JsonResponse({
        'query': query,
        'results': results,
        'count': len(results),
    })


def search_results(request):
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    capacity = request.GET.get('capacity', '').strip()
    power = request.GET.get('power', '').strip()
    voltage = request.GET.get('voltage', '').strip()

    # Start with products and make JSON specifications searchable.
    searchable_products = Product.objects.annotate(
        specifications_text=Cast(
            'technical_specifications',
            output_field=TextField()
        )
    )

    # Only show results when the visitor has entered a search
    # term or selected at least one filter.
    has_filters = any([
        query,
        category,
        capacity,
        power,
        voltage,
    ])

    if has_filters:
        products = searchable_products

        # Main keyword search.
        if query:
            filters = (
                Q(name__icontains=query)
                | Q(manufacturer_model__icontains=query)
                | Q(category__icontains=query)
                | Q(tagline__icontains=query)
                | Q(description__icontains=query)
                | Q(capacity__icontains=query)
                | Q(power__icontains=query)
                | Q(warranty__icontains=query)
                | Q(specifications_text__icontains=query)
            )

            # Match human-readable category names.
            for value, label in Product.CATEGORY_CHOICES:
                if query.lower() in label.lower():
                    filters |= Q(category=value)

            # Common category search terms.
            category_aliases = {
                'lithium': 'battery',
                'batteries': 'battery',
                'battery': 'battery',
                'solar': 'solar',
                'residential': 'residential',
                'home': 'residential',
                'commercial': 'commercial',
                'industrial': 'commercial',
            }

            alias = category_aliases.get(query.lower())

            if alias:
                filters |= Q(category=alias)

            products = products.filter(filters)

        # Category filter.
        if category in dict(Product.CATEGORY_CHOICES):
            products = products.filter(category=category)
        else:
            category = ''

        # Capacity filter.
        if capacity:
            products = products.filter(
                capacity__icontains=capacity
            )

        # Power filter.
        if power:
            products = products.filter(
                power__icontains=power
            )

        # Voltage filter: voltage is stored in the technical
        # specifications JSON field, not a separate model field.
        if voltage:
            products = products.filter(
                specifications_text__icontains=voltage
            )

        products = products.distinct().order_by('order', 'name')

    else:
        products = Product.objects.none()

    # Display a maximum of 17 products per page.
    paginator = Paginator(products, 17)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Preserve all active search terms and filters during pagination.
    query_params = request.GET.copy()
    query_params.pop('page', None)
    pagination_query = query_params.urlencode()

    return render(request, 'core/search_results.html', {
        'query': query,
        'page_obj': page_obj,
        'products': page_obj.object_list,
        'result_count': paginator.count,
        'categories': Product.CATEGORY_CHOICES,
        'active_category': category,
        'active_capacity': capacity,
        'active_power': power,
        'active_voltage': voltage,
        'pagination_query': pagination_query,
    })
# ---------------------------------------------------------------
# views.py  (add to your core app)
# ---------------------------------------------------------------
import json

from django.shortcuts import render
from django.utils.safestring import mark_safe
from django.utils.text import slugify

FAQ_DATA = [
    {
        "slug": "general",
        "title": "About Yunqida",
        "intro": "Who we are and how we work.",
        "items": [
            ("Who is Yunqida Energy Technology Kenya?",
             "Yunqida Energy Technology Kenya makes solar energy products, LiFePO4 lithium batteries and hybrid inverters available to Kenyan homes, businesses and institutions. We are associated with Guangdong Yunqida New Energy Technology Co., Ltd."),
            ("Who do you serve?",
             "We serve households, shops, offices, schools, clinics, farms, factories and project partners such as installers and distributors."),
            ("Do you only sell products?",
             "No. We also help you understand your energy needs, size a system, compare options and choose suitable equipment before you buy."),
            ("How do I contact Yunqida Energy Kenya?",
             "Use the contact page or call 0114542427. Tell us about your site and what you want to power so we can respond with relevant options."),
        ],
    },
    {
        "slug": "solar",
        "title": "Solar systems",
        "intro": "Panels, generation and how a system fits together.",
        "items": [
            ("What does a solar power system include?",
             "A typical system includes solar panels, an inverter, mounting equipment and cabling. Many systems also add lithium battery storage so you can use solar energy at night and during outages."),
            ("Will solar keep my power on during a blackout?",
             "It depends on the design. A basic grid tied system usually switches off when the grid fails. A hybrid system with battery storage can keep selected loads running."),
            ("How many solar panels do I need?",
             "That depends on your daily energy use, the roof or ground space available and your goals. We size the system from your appliances and consumption."),
            ("Can solar run my whole home or business?",
             "It can, if the system is sized for your total load and storage needs. Many customers start with essential loads and expand later."),
            ("How long do solar panels last?",
             "Quality panels are designed to work for many years, and manufacturers usually give performance warranties. Check the warranty terms of the specific product in your quotation."),
        ],
    },
    {
        "slug": "lithium-batteries",
        "title": "Lithium batteries",
        "intro": "LiFePO4 storage explained in plain language.",
        "items": [
            ("What is a LiFePO4 lithium battery?",
             "LiFePO4 means lithium iron phosphate. It is a rechargeable battery chemistry widely used for solar storage and power backups, available in many voltages and capacities."),
            ("Why choose lithium batteries over lead acid batteries?",
             "Lithium batteries are generally lighter, allow deeper usable discharge and are built for frequent cycling. Compare usable capacity, cycle life and warranty on the datasheet."),
            ("How do I choose the right battery capacity?",
             "Add up the power of the appliances you want to run, multiply by the hours you need, and compare that with the usable capacity of the battery. We can do this calculation with you."),
            ("Can I add more batteries later?",
             "Often yes, if the battery and inverter support expansion. Plan for this from the start so the equipment you buy today stays compatible."),
            ("What is the difference between wall mounted and rack mounted batteries?",
             "Wall mounted units suit homes and small sites. Rack mounted units suit larger systems and are installed in cabinets or racks for easier scaling."),
            ("Do lithium batteries need maintenance?",
             "They need little routine maintenance. Keep them in the recommended temperature range, ventilated as advised and connected to a compatible inverter or battery management system."),
        ],
    },
    {
        "slug": "inverters",
        "title": "Hybrid inverters",
        "intro": "The brain that connects solar, batteries and the grid.",
        "items": [
            ("What is a hybrid inverter?",
             "A hybrid inverter manages solar panels, battery storage and the grid in one unit, depending on the model. It decides where your power comes from at any moment."),
            ("How is a hybrid inverter different from a standard inverter?",
             "A standard inverter usually handles one source and has limited energy management. A hybrid inverter coordinates several sources and can charge and discharge batteries."),
            ("Do I need a single phase or three phase inverter?",
             "It depends on your electrical supply and loads. Homes usually use single phase, while larger commercial and industrial sites often need three phase."),
            ("Will any battery work with any inverter?",
             "No. Voltage, communication protocol and capacity must match. Always confirm battery and inverter compatibility before you buy."),
            ("What inverter size do I need?",
             "Size it to the total power of the loads that run at the same time, with room for startup surges from motors and compressors."),
        ],
    },
    {
        "slug": "power-backups",
        "title": "Power backups",
        "intro": "Keeping the lights, fridge and work running.",
        "items": [
            ("How long will a power backup last?",
             "A rough guide is usable battery energy divided by the power you draw. A larger battery or fewer loads means longer backup time."),
            ("Which appliances can a power backup run?",
             "Lights, phones, internet routers, televisions, fridges and many other devices, as long as the inverter and battery are sized for them. Heavy loads such as water heaters need more capacity."),
            ("Does the system switch on automatically when the grid goes off?",
             "Many hybrid systems transfer to battery power automatically, but the speed and behaviour depend on the model. Confirm this in the product specification."),
            ("Can a power backup work with a generator?",
             "Some hybrid inverters accept a generator as an extra source. Check that the specific model supports it."),
            ("Can I back up only essential loads?",
             "Yes. A common approach is to connect lights, internet, fridge and selected sockets to the backup, and leave heavy loads on the grid."),
        ],
    },
    {
        "slug": "business",
        "title": "Business and industry",
        "intro": "Energy for shops, schools, clinics, farms and factories.",
        "items": [
            ("Do you provide commercial energy storage?",
             "Yes. We provide storage products and guidance for shops, offices, hotels, schools, clinics and other businesses."),
            ("Can systems scale for industrial use?",
             "Rack and cabinet battery configurations let capacity grow as your needs grow. Share your load profile and we can discuss suitable options."),
            ("Can solar and lithium storage reduce my electricity costs?",
             "They can reduce how much you buy from the grid and keep operations running during outages. Savings depend on your tariff, usage and system size."),
            ("Do you work with installers and project developers?",
             "Yes. We supply products and discuss specifications and quantities with installers, distributors and project partners."),
        ],
    },
    {
        "slug": "oem",
        "title": "OEM and ODM",
        "intro": "Your brand, our manufacturing experience.",
        "items": [
            ("What are OEM and ODM services?",
             "OEM means we manufacture a product to your specification. ODM means we also help develop the design. Both let you sell energy storage products under your own brand."),
            ("What can be customised?",
             "Specifications, branding, capacity and design requirements can be discussed. Contact us with your target market and volumes."),
            ("How do I start an OEM or ODM enquiry?",
             "Call 0114542427 or use the contact page with your product idea, expected quantities and timeline."),
        ],
    },
    {
        "slug": "orders",
        "title": "Quotes, orders and support",
        "intro": "From first enquiry to ongoing support.",
        "items": [
            ("How do I get a quotation?",
             "Send us your location, the appliances or loads you want to power, how long you need backup and any products you are considering. We will respond with relevant options and pricing."),
            ("What information should I prepare before asking for a quote?",
             "Have your monthly electricity usage or appliance list, your supply type (single or three phase), available installation space and your budget range."),
            ("Do you offer guidance on installation?",
             "We provide product guidance and can discuss installation requirements. Use a qualified installer for electrical work and confirm details when you enquire."),
            ("What warranty do products carry?",
             "Warranty terms depend on the product. They are stated in your quotation, so ask about them before you decide."),
            ("Can I visit or speak to someone before buying?",
             "Yes. Call 0114542427 or send an enquiry and our team will respond."),
        ],
    },
]


def faq(request):
    categories, schema_items, total = [], [], 0

    for cat in FAQ_DATA:
        items = []
        for q, a in cat["items"]:
            items.append({"q": q, "a": a, "slug": "q-" + slugify(q)[:60]})
            schema_items.append({
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            })
        total += len(items)
        categories.append({**cat, "items": items})

    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": schema_items,
    }
    # "<" is escaped so the JSON can never close the script tag
    schema_json = json.dumps(schema, ensure_ascii=False).replace("<", "\\u003c")

    return render(request, "core/faq.html", {
        "categories": categories,
        "total": total,
        "faq_schema": mark_safe(schema_json),
    })


