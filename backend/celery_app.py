"""
Bootstraps the Celery app. Deliberately NOT named celery.py: since this
project keeps settings.py/urls.py/etc. flat at backend/ root (no config/
subfolder), that directory ends up on sys.path when Django runs — a local
module literally named celery.py would shadow the real `celery` package
and break every `import celery` in this same file. Naming it celery_app.py
avoids that trap entirely.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

app = Celery("gallery")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(["gallery"])
