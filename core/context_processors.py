def site_info(request):
    """Company details available in every template. Edit once, updates everywhere."""
    return {
        'SITE': {
            'name': 'Yunqida Energy Kenya',
            'phone': '+254 700 000 000',
            'email': 'sales@yunqida.co.ke',
            'address': 'Nairobi, Kenya',
            'hours': 'Mon–Fri 8:00–17:00, Sat 9:00–13:00',
            'whatsapp': '254700000000',
        }
    }
