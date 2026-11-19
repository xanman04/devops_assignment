"""Independent Discovery runtime with SQL Server and local SQLite compatibility."""
import os
from pathlib import Path

from .local_secrets import load
load()

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = False
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
UI_ORIGIN = os.environ.get("UI_ORIGIN", "http://localhost:8080")
VERSION = os.environ.get("VERSION", "development")
TOKEN_TTL_S = 900
TRUST_CONTAINER_APPS_INGRESS = os.environ.get('TRUST_CONTAINER_APPS_INGRESS', '0') == '1'
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///" + str(DATA_DIR / "discovery.sqlite3"))
from .database import database_config
DATABASES = {"default": database_config(DATABASE_URL, test_file=DATA_DIR / "test_discovery.sqlite3")}
DATABASE_CONNECTION_POOLING = False
if os.environ.get("SQLSERVER_TEST_MODE") == "1":
    if DATABASES['default']['ENGINE'] != 'mssql' or DATABASES['default']['HOST'] not in {'sqlserver', 'localhost', '127.0.0.1'}:
        raise ValueError('SQLSERVER_TEST_MODE is restricted to disposable local SQL Server instances.')
    TEST_RUNNER = 'config.testing.LocalSqlServerRunner'

INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "accounts", "discovery", "notifications"]
MIDDLEWARE = ["config.middleware.RequestMiddleware"]
ROOT_URLCONF = "config.urls"
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
MEDIA_ROOT = DATA_DIR / "media"
LOGGING = {"version": 1, "disable_existing_loggers": False,
    "handlers": {"stdout": {"class": "logging.StreamHandler", "stream": "ext://sys.stdout"}},
    "loggers": {"requests": {"handlers": ["stdout"], "level": "INFO", "propagate": False}}}

SERVICE_NAME = 'discovery'
