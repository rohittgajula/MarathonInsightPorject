"""Django bootstrap for tests that import model modules.

The segmentation and metrics modules are deliberately free of Django imports and
need none of this. The log extractor is not — it lives beside the model that stores
its output — so tests touching it initialise the app registry first.
"""

import os

import django


def pytest_configure():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ.setdefault("DATABASE_URL", "postgres://runproject:runproject@db:5432/runproject")
    django.setup()
