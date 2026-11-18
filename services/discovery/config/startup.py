"""Serialize startup schema changes within this service's own database."""
from contextlib import contextmanager
import os

from django.core.management import call_command
from django.db import connection, OperationalError


@contextmanager
def migration_lock():
    locked = False
    if connection.vendor == "microsoft":
        with connection.cursor() as cursor:
            cursor.execute("""
                DECLARE @result int;
                EXEC @result = sys.sp_getapplock @Resource = %s,
                    @LockMode = 'Exclusive', @LockOwner = 'Session', @LockTimeout = 25000;
                SELECT @result;
            """, ["bassline-schema-migrations"])
            if cursor.fetchone()[0] < 0:
                raise OperationalError("Another instance is migrating this database; retry startup.")
            locked = True
    try:
        yield
    finally:
        if locked:
            with connection.cursor() as cursor:
                cursor.execute("EXEC sys.sp_releaseapplock @Resource = %s, @LockOwner = 'Session';",
                               ["bassline-schema-migrations"])


def initialize():
    with migration_lock():
        call_command("migrate", interactive=False)
        if os.environ.get("IMPORT_SPLIT_DATA"):
            call_command("import_split_data", os.environ["IMPORT_SPLIT_DATA"])
