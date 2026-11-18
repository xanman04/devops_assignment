"""Load generated local Compose credentials without baking them into images."""
import os
from pathlib import Path
from urllib.parse import quote


def load():
    directory = os.environ.get("LOCAL_SECRETS_DIR")
    if not directory:
        return
    root = Path(directory)
    os.environ.setdefault("DJANGO_SECRET_KEY", (root / "django-secret").read_text().strip())
    if "DATABASE_URL" not in os.environ:
        password = (root / "password").read_text().strip()
        user = os.environ["DATABASE_USER"]
        host = os.environ["DATABASE_HOST"]
        name = os.environ["DATABASE_NAME"]
        os.environ["DATABASE_URL"] = (
            f"mssql://{quote(user, safe='')}:{quote(password, safe='')}@{host}:1433/{name}"
            "?trust_server_certificate=yes")
