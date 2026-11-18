"""Apply pending migrations, then serve this service with Waitress."""
import os
import django
from django.core.wsgi import get_wsgi_application
from waitress import serve

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    from config.startup import initialize
    initialize()
    serve(get_wsgi_application(), host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
