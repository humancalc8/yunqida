from django.core.management.base import BaseCommand
from core.models import Product

# Sample catalogue. Replace specs with the real figures from Yunqida's datasheets.
DATA = [
    dict(name='All-in-One Home ESS', slug='all-in-one-home-ess', category='residential', featured=True,
         tagline='Inverter, battery and controller in a single wall or floor unit.',
         description='A compact home energy storage system that keeps lights, fridge, Wi-Fi and TVs running through Kenya Power outages and shifts your solar to the evening.\n\nOne cabinet means a cleaner install, fewer cables and a single point of support.',
         capacity='5–15 kWh', power='3–10 kW', warranty='5 years', fallback_image='img/product-cabinet.svg', order=1),
    dict(name='Wall-Mounted Lithium Battery', slug='wall-mounted-lithium-battery', category='battery', featured=True,
         tagline='LiFePO4 modules that stack as your needs grow.',
         description='Safe, long-life lithium iron phosphate batteries for home and small business. Start with one module and add more later.\n\nBuilt-in battery management protects against over-charge, deep discharge and overheating.',
         capacity='5.12 kWh per module', power='up to 5 kW', warranty='5 years', fallback_image='img/product-battery.svg', order=2),
    dict(name='Commercial Storage Cabinet', slug='commercial-storage-cabinet', category='commercial', featured=True,
         tagline='Cut diesel use and demand charges for shops, clinics and factories.',
         description='Floor-standing storage cabinets for businesses that cannot afford downtime. Pair with rooftop solar to cut your electricity bill and run quietly through outages.',
         capacity='30–215 kWh', power='15–100 kW', warranty='5 years', fallback_image='img/product-cabinet.svg', order=3),
    dict(name='Hybrid Solar Inverter', slug='hybrid-solar-inverter', category='solar',
         tagline='One inverter for solar, battery and grid.',
         description='Manages solar panels, battery and the grid together, and switches to backup power in milliseconds when the grid drops.',
         capacity='-', power='3–12 kW', warranty='5 years', fallback_image='img/product-inverter.svg', order=4),
    dict(name='Rack-Mount Battery', slug='rack-mount-battery', category='battery',
         tagline='19-inch rack batteries for server rooms and telecom sites.',
         description='Standard rack-mount lithium batteries for telecom towers, server rooms and clinics that need dependable, scalable backup.',
         capacity='5–10 kWh per rack', power='up to 5 kW', warranty='5 years', fallback_image='img/product-battery.svg', order=5),
    dict(name='Complete Solar Kit', slug='complete-solar-kit', category='solar',
         tagline='Panels, inverter and battery sized for your home.',
         description='A ready-to-install package matched to your household consumption, delivered and commissioned by our trained installers.',
         capacity='5–20 kWh', power='3–10 kW', warranty='5 years', fallback_image='img/product-inverter.svg', order=6),
]


class Command(BaseCommand):
    help = 'Load sample products'

    def handle(self, *args, **opts):
        for d in DATA:
            Product.objects.update_or_create(slug=d['slug'], defaults=d)
        self.stdout.write(self.style.SUCCESS(f'{len(DATA)} products loaded.'))
