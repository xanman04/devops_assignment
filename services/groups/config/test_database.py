"""Portable URL parsing and owned-data import verification."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, TransactionTestCase

from config.database import database_config
from notifications.models import DataImport


class SqlServerOwnershipTests(TransactionTestCase):
    def test_service_login_cannot_read_the_other_database(self):
        from django.db import connection, DatabaseError
        if connection.vendor != "microsoft":
            self.skipTest("Database isolation is exercised in the SQL Server stack.")
        other = "groups" if settings.SERVICE_NAME == "discovery" else "discovery"
        with self.assertRaises(DatabaseError):
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM [{other}].sys.tables")


class DatabaseUrlTests(SimpleTestCase):
    def test_sql_credentials_are_decoded_and_tls_is_explicit(self):
        config = database_config("mssql://app:p%40ss%3Bword@sqlserver:1433/own_db?trust_server_certificate=yes", test_file="unused")
        self.assertEqual(config["PASSWORD"], "p@ss;word")
        self.assertEqual(config["ENGINE"], "mssql")
        self.assertEqual(config["OPTIONS"]["extra_params"], "Encrypt=yes;TrustServerCertificate=yes")
        secure = database_config("mssql://app:private@server.database.windows.net/own_db", test_file="unused")
        self.assertEqual(secure["OPTIONS"]["extra_params"], "Encrypt=yes;TrustServerCertificate=no")

    def test_invalid_urls_do_not_echo_secrets(self):
        for value in ("postgres://app:private@host/db", "mssql://app:private@host/", "mssql://app:private@host/db?extra=bad"):
            with self.assertRaisesRegex(ValueError, "^DATABASE_URL"):
                database_config(value, test_file="unused")


class OwnedImportTests(TransactionTestCase):
    def test_ids_and_credentials_are_preserved_only_by_their_owner(self):
        if settings.SERVICE_NAME == "discovery":
            from django.contrib.auth import get_user_model
            from django.contrib.auth.hashers import make_password
            password = make_password("import-test-password")
            rows = [{"model": "accounts.user", "pk": 77, "fields": {
                "username": "import-owner", "password": password, "display_name": "Imported"}}]
        else:
            rows = [{"model": "groups.person", "pk": 77, "fields": {"display_name": "Imported"}}]
        with TemporaryDirectory() as directory:
            path = Path(directory)/"split.json"
            path.write_text(json.dumps({"format": 1, settings.SERVICE_NAME: rows}))
            call_command("import_split_data", str(path))
            call_command("import_split_data", str(path))
            self.assertEqual(DataImport.objects.count(), 1)
            if settings.SERVICE_NAME == "discovery":
                user = get_user_model().objects.get(pk=77)
                self.assertTrue(user.check_password("import-test-password"))
                self.assertGreater(get_user_model().objects.create_user("new-owner").pk, 77)
            else:
                from groups.models import Person
                self.assertEqual(Person.objects.get(pk=77).display_name, "Imported")
                self.assertNotIn("password", {field.name for field in Person._meta.fields})
            path.write_text(json.dumps({"format": 1, settings.SERVICE_NAME: rows, "changed": True}))
            with self.assertRaises(CommandError):
                call_command("import_split_data", str(path))

    def test_import_refuses_foreign_owned_models(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)/"bad.json"
            path.write_text(json.dumps({"format": 1, settings.SERVICE_NAME: [
                {"model": "sessions.session", "pk": 1, "fields": {}}]}))
            with self.assertRaises(CommandError):
                call_command("import_split_data", str(path))
