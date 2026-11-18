"""Parse DATABASE_URL without putting credentials in diagnostics."""
import re
from urllib.parse import parse_qs, unquote, urlsplit


def database_config(value, *, test_file):
    if value.startswith("sqlite:///"):
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": value[len("sqlite:///"):],
                "TEST": {"NAME": str(test_file)},
                "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE"}}
    try:
        url = urlsplit(value)
        options = parse_qs(url.query, strict_parsing=True)
        name = unquote(url.path.lstrip("/"))
        if (url.scheme != "mssql" or not url.hostname or not url.username or not url.password
                or not re.fullmatch(r"[A-Za-z0-9.-]+", url.hostname)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", name)
                or url.fragment or set(options) - {"trust_server_certificate"}
                or options.get("trust_server_certificate", ["no"]) not in (["yes"], ["no"])):
            raise ValueError()
        port = str(url.port or 1433)
    except (ValueError, TypeError):
        raise ValueError("DATABASE_URL must be sqlite:///path or a valid mssql:// connection URL.") from None
    trust = options.get("trust_server_certificate", ["no"])[0]
    return {"ENGINE": "mssql", "NAME": name, "HOST": url.hostname, "PORT": port,
            "USER": unquote(url.username), "PASSWORD": unquote(url.password),
            "CONN_MAX_AGE": 0, "OPTIONS": {
                "driver": "ODBC Driver 18 for SQL Server",
                "extra_params": f"Encrypt=yes;TrustServerCertificate={trust}",
                "connection_timeout": 5, "connection_retries": 10,
                "connection_retry_backoff_time": 5, "query_timeout": 30}}
