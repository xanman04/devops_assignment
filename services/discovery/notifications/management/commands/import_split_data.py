"""Import a trusted Assignment 1 split export only into an empty owner database."""
import hashlib
import json
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from notifications.models import DataImport


class Command(BaseCommand):
    help = "Import a trusted private split export, preserving IDs and recording its fingerprint."

    def add_arguments(self, parser):
        parser.add_argument("source", type=Path)

    def handle(self, *args, **options):
        raw = options["source"].read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        try:
            payload = json.loads(raw)
            rows = payload[settings.SERVICE_NAME]
            if payload["format"] != 1 or not isinstance(rows, list):
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise CommandError("Not a supported split export.") from None
        allowed = {model._meta.label_lower for model in apps.get_app_config(settings.SERVICE_NAME).get_models()}
        if settings.SERVICE_NAME == "discovery":
            allowed |= {"accounts.user", "auth.group", "auth.permission", "contenttypes.contenttype"}
        allowed.add("notifications.notification")
        if any(not isinstance(row, dict) or row.get("model") not in allowed for row in rows):
            raise CommandError("Export contains records outside this service's ownership.")
        seeded = {'contenttypes.contenttype', 'auth.permission', 'auth.group'}
        for row in rows:
            if row['model'] in seeded and row.get('pk') is not None:
                raise CommandError('Content types, permissions and roles must use natural primary keys.')
            if row['model'] not in seeded and (type(row.get('pk')) is not int or row['pk'] <= 0):
                raise CommandError('Owned records must carry stable positive integer IDs.')
            if not isinstance(row.get('fields'), dict):
                raise CommandError('Invalid record fields.')
            model = apps.get_model(row['model'])
            for field in model._meta.get_fields():
                if not field.is_relation or field.name not in row['fields']:
                    continue
                target = field.related_model._meta.label_lower
                if target not in seeded:
                    continue
                value = row['fields'][field.name]
                if value is None and field.null and not field.many_to_many:
                    continue
                keys = value if field.many_to_many else [value]
                width = {'auth.group': 1, 'auth.permission': 3, 'contenttypes.contenttype': 2}[target]
                if not isinstance(keys, list) or any(
                    not isinstance(key, list) or len(key) != width
                    or any(not isinstance(part, str) or not part for part in key) for key in keys):
                    raise CommandError('Role, permission and content-type references must use natural foreign keys.')
        with transaction.atomic():
            if DataImport.objects.filter(fingerprint=digest).exists():
                self.stdout.write("This export was already imported; no data changed.")
                return
            owner_models = list(apps.get_app_config(settings.SERVICE_NAME).get_models()) + [apps.get_model("notifications.Notification")]
            if settings.SERVICE_NAME == "discovery":
                owner_models += [apps.get_model("accounts.User"), apps.get_model("auth.Group")]
            if any(model.objects.exists() for model in owner_models) or DataImport.objects.exists():
                raise CommandError("Target must be empty; refusing to overwrite existing service data.")
            # Raw fixture saves bypass model.save(), so derive the new SQL-safe URL key explicitly.
            for row in rows:
                if row["model"] == "discovery.djmedialink":
                    row["fields"]["url_digest"] = hashlib.sha256(row["fields"]["url"].encode("utf-8")).hexdigest()
            if any(row["model"] in ("discovery.genrecategory", "discovery.genretag") for row in rows):
                # Raw saves skip the model save() methods that fill slugs.
                from discovery.models import unique_category_slug, unique_tag_slug
                for model, make_slug in (("discovery.genrecategory", unique_category_slug),
                                         ("discovery.genretag", unique_tag_slug)):
                    taken_slugs = set()
                    for row in rows:
                        if row["model"] == model:
                            row["fields"]["slug"] = row["fields"].get("slug") or make_slug(row["fields"]["name"], taken_slugs)
                            taken_slugs.add(row["fields"]["slug"])
            with connection.constraint_checks_disabled():
                for record in serializers.deserialize("python", rows):
                    record.save()
            connection.check_constraints()
            DataImport.objects.create(fingerprint=digest)
        self.stdout.write(f"Imported {len(rows)} owned records; IDs preserved. Copy owned upload files separately.")
