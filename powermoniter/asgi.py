"""
ASGI config for powermoniter project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.conf import settings
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'powermoniter.settings')

django_asgi_app = get_asgi_application()

if settings.DEBUG:
    application = ASGIStaticFilesHandler(django_asgi_app)
else:
    application = django_asgi_app
