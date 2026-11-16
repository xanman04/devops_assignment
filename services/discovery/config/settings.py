"""Independent Discovery runtime. SQLite is transitional until the SQL Server milestone."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = False
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
UI_ORIGIN = os.environ.get("UI_ORIGIN", "http://localhost:8080")
VERSION = os.environ.get("VERSION", "development")
TOKEN_TTL_S = 900
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///" + str(DATA_DIR / "discovery.sqlite3"))
if not DATABASE_URL.startswith("sqlite:///"):
    raise ValueError("This extraction milestone supports sqlite:/// only; SQL Server is pending.")
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3",
    "NAME": DATABASE_URL[len("sqlite:///"):], "OPTIONS": {"timeout": 20}}}
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "accounts", "discovery", "notifications"]
MIDDLEWARE = ["config.middleware.RequestMiddleware"]
ROOT_URLCONF = "config.urls"
AUTH_USER_MODEL = "accounts.User"
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
MEDIA_ROOT = DATA_DIR / "media"
LOGGING = {"version": 1, "disable_existing_loggers": False,
    "handlers": {"stdout": {"class": "logging.StreamHandler", "stream": "ext://sys.stdout"}},
    "loggers": {"requests": {"handlers": ["stdout"], "level": "INFO", "propagate": False}}}
