from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import EnquiryForm
from .models import Product, BuildProject
from .google_reviews import get_google_reviews


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
    category = request.GET.get('category', '')
    items = Product.objects.all()

    if category in dict(Product.CATEGORY_CHOICES):
        items = items.filter(category=category)
    else:
        category = ''

    return render(request, 'core/products.html', {
        'products': items,
        'categories': Product.CATEGORY_CHOICES,
        'active_category': category,
    })


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    related = Product.objects.filter(
        category=product.category
    ).exclude(pk=product.pk)[:3]

    return render(request, 'core/product_detail.html', {
        'product': product,
        'related': related,
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

  