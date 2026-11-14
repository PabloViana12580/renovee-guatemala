from django.conf import settings

from config.modules import MODULE_APPS


def site(request):
    """Site identity, contact details, and installed modules for every template."""
    phone = settings.SITE_PHONE
    whatsapp_digits = ''.join(ch for ch in settings.SITE_WHATSAPP if ch.isdigit())
    return {
        # Not called `site`: Django's auth views put their own `site` in the context.
        'site_info': {
            'name': settings.SITE_NAME,
            'tagline': settings.SITE_TAGLINE,
            'url': settings.SITE_URL,
            'email': settings.SITE_EMAIL,
            'phone': phone,
            'phone_href': 'tel:' + ''.join(ch for ch in phone if ch.isdigit() or ch == '+') if phone else '',
            'address': settings.SITE_ADDRESS,
            'hours': settings.SITE_HOURS,
            'whatsapp': settings.SITE_WHATSAPP,
            'whatsapp_href': f'https://wa.me/{whatsapp_digits}' if whatsapp_digits else '',
            'modules': frozenset(MODULE_APPS),
        },
    }
