"""Independent Groups database with SQL Server and local SQLite compatibility."""
import math
import os
from pathlib import Path
from urllib.parse import urlsplit

from .local_secrets import load
load()

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = False
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
UI_ORIGIN = os.environ.get("UI_ORIGIN", "http://localhost:8080")
VERSION = os.environ.get("VERSION", "development")
DISCOVERY_URL = os.environ.get("DISCOVERY_URL", "http://localhost:8000").rstrip("/")
url = urlsplit(DISCOVERY_URL)
if url.scheme not in {"http", "https"} or not url.netloc or url.username or url.password or url.query or url.fragment:
    raise ValueError("DISCOVERY_URL must be an HTTP(S) base URL without credentials/query/fragment.")
DISCOVERY_TIMEOUT_S = float(os.environ.get("DISCOVERY_TIMEOUT_S", "2"))
if not math.isfinite(DISCOVERY_TIMEOUT_S) or DISCOVERY_TIMEOUT_S <= 0:
    raise ValueError("DISCOVERY_TIMEOUT_S must be finite and positive.")
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///" + str(DATA_DIR / "groups.sqlite3"))
from .database import database_config
DATABASES = {"default": database_config(DATABASE_URL, test_file=DATA_DIR / "test_groups.sqlite3")}
DATABASE_CONNECTION_POOLING = False
if os.environ.get("SQLSERVER_TEST_MODE") == "1":
    if DATABASES['default']['ENGINE'] != 'mssql' or DATABASES['default']['HOST'] not in {'sqlserver', 'localhost', '127.0.0.1'}:
        raise ValueError('SQLSERVER_TEST_MODE is restricted to disposable local SQL Server instances.')
    TEST_RUNNER = 'config.testing.LocalSqlServerRunner'

INSTALLED_APPS = ["groups", "notifications"]
AUTH_USER_MODEL = "groups.Person"
MIDDLEWARE = ["config.middleware.RequestMiddleware"]
ROOT_URLCONF = "config.urls"
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
MEDIA_ROOT = DATA_DIR / "media"
LOGGING = {"version": 1, "disable_existing_loggers": False,
    "handlers": {"stdout": {"class": "logging.StreamHandler", "stream": "ext://sys.stdout"}},
    "loggers": {"requests": {"handlers": ["stdout"], "level": "INFO", "propagate": False}}}

SERVICE_NAME = 'groups'
