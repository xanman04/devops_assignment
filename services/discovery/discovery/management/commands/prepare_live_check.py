"""Create the controlled accounts and records used by a production live check."""
import json
import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone

from discovery import services
from discovery.models import Event, GenreCategory, Venue


MARKER = "Bassline controlled release verification fixture"
OWNER_USERNAME = "a2-release-owner"
GUEST_USERNAME = "a2-release-guest"
VENUE_NAME = "Bassline release verification venue"
EVENT_TITLE = "Bassline release verification event"


def _fixture_user(username, password):
    User = get_user_model()
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        user = User(username=username, bio=MARKER, is_active=True)
        user.set_password(password)
        user.save()
        return user

    if user.bio != MARKER:
        raise CommandError(f"Refusing to reuse unrelated account {username}.")
    if user.is_staff or user.is_superuser or user.groups.exists() or user.user_permissions.exists():
        raise CommandError(f"Refusing privileged fixture account {username}.")
    if not user.check_password(password):
        raise CommandError(f"LIVE_CHECK_PASSWORD does not match fixture account {username}.")
    return user


class Command(BaseCommand):
    help = "Prepare reserved accounts, venue, and event for a controlled production check."

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.environ.get("LIVE_CHECK_PASSWORD", "")
        if len(password) < 32:
            raise CommandError("LIVE_CHECK_PASSWORD must contain at least 32 characters.")

        owner = _fixture_user(OWNER_USERNAME, password)
        guest = _fixture_user(GUEST_USERNAME, password)

        venues = list(Venue.objects.filter(name=VENUE_NAME).order_by("pk"))
        if venues:
            if len(venues) != 1 or venues[0].submitted_by_id != owner.pk:
                raise CommandError("Refusing the reserved venue name because another account owns it.")
            venue = venues[0]
            if venue.review_status != Venue.ReviewStatus.APPROVED:
                raise CommandError("The reserved fixture venue exists but is not approved.")
        else:
            venue = Venue(submitted_by=owner, review_status=Venue.ReviewStatus.APPROVED,
                name=VENUE_NAME, address="", latitude="40.416775",
                longitude="-3.703790", timezone="Europe/Madrid")
            venue.full_clean()
            venue.save()

        category = GenreCategory.objects.order_by("pk").first()
        if category is None:
            raise CommandError("No seeded genre category exists for the release verification event.")

        matching_events = list(Event.objects.filter(title=EVENT_TITLE).order_by("pk"))
        if matching_events:
            if len(matching_events) != 1:
                raise CommandError("Refusing duplicate records with the reserved event title.")
            existing = matching_events[0]
            if existing.creator_id != owner.pk or existing.venue_id != venue.pk:
                raise CommandError("Refusing the reserved event title because another account or venue owns it.")
            event_id = existing.pk
        else:
            event_id = None

        starts_at = timezone.now() + timedelta(days=7)
        event = services.save_event(actor=owner, event_id=event_id,
            data={"venue": venue, "title": EVENT_TITLE,
                  "description": "Controlled production verification fixture.",
                  "starts_at": starts_at, "ends_at": starts_at + timedelta(hours=4),
                  "ticket_url": ""}, category_ids=[category.pk], tag_ids=[])

        migration_names = {
            "0014_genrecategory_slug",
            "0015_genrecategory_slug_unique",
        }
        migrations = [
            {"name": row.name, "applied_at": row.applied.isoformat()}
            for row in MigrationRecorder.Migration.objects.filter(
                app="discovery", name__in=migration_names
            ).order_by("name")
        ]

        self.stdout.write(json.dumps({
            "owner_username": owner.username,
            "guest_username": guest.username,
            "event_id": event.pk,
            "event_title": event.title,
            "migrations": migrations,
        }, separators=(",", ":")))
