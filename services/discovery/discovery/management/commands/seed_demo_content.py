# Copyright © 2026 Xander Chen. All rights reserved.
"""Load the Assignment 1 demo accounts, venues, events, follows and event cards with upcoming dates.

An explicit operator command, never run at startup. It adds what is missing and leaves existing rows alone;
--refresh-dates also moves existing demo events forward again (followers get the normal change notice). All listings
are fictional. The accounts share the password in DEMO_ACCOUNT_PASSWORD, which is never printed or stored here.
"""
import json
import os
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from discovery import services
from discovery.models import DJProfile, Event, EventCard, GenreCategory, GenreTag, Venue

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "demo_content.json"
NOTE = "Fictional demo listing."
VENUE_NOTE = "Demo fixture: no organizer affiliation or safety verification is implied."
MARKER_DOMAIN = "@example.invalid"
# Days ahead for the events, in fixture order. Events with demo groups sit further out so the groups stay open.
OFFSETS = (1, 2, 3, 5, 6, 8, 10, 12, 14, 16, 19, 22, 25, 28, 31, 34, 37, 41, 45, 49, 53, 57, 61, 64)
FEATURED = {"Blue Hour Circuit": 40, "Pickle Rick's Portal Rave": 52}


def schedule(events, today):
    """Date for each event title: featured ones fixed, the rest in order through the offsets."""
    remaining = iter(OFFSETS)
    return {e["title"]: today + timedelta(days=FEATURED[e["title"]] if e["title"] in FEATURED else next(remaining))
            for e in events}


class Command(BaseCommand):
    help = "Add the fictional demo accounts, venues and upcoming events carried over from Assignment 1."

    def add_arguments(self, parser):
        parser.add_argument("--refresh-dates", action="store_true", help="Move existing demo events forward from today.")

    def handle(self, *args, refresh_dates=False, **options):
        password = os.environ.get("DEMO_ACCOUNT_PASSWORD", "")
        if len(password) < 12:
            raise CommandError("DEMO_ACCOUNT_PASSWORD must contain at least 12 characters.")
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with transaction.atomic():
            users = self._users(data["users"], password)
            venues = self._venues(data["venues"], users["demo_organizer"])
            categories = {c.name: c for c in GenreCategory.objects.all()}
            tags = {(t.category.name, t.name): t for t in GenreTag.objects.select_related("category")}
            artists = self._artists(data["artists"], categories)
            events, created, moved = self._events(data["events"], users, venues, categories, tags, artists, refresh_dates)
            for username, titles in data["follows"].items():
                for title in titles:
                    if events[title].cancelled_at is None:
                        services.follow_event(actor=users[username], event_id=events[title].pk)
            for username, titles in data["cards"].items():
                for title in titles:
                    EventCard.objects.get_or_create(user=users[username], event=events[title])
        # The last line is machine readable for the operator workflow. It carries no credentials.
        self.stdout.write(json.dumps({"accounts": sorted(users), "events": len(events), "events_created": created,
                                      "events_moved": moved, "venues": len(venues),
                                      "cards": EventCard.objects.filter(user__in=users.values()).count()}))

    def _users(self, records, password):
        User = get_user_model()
        users = {}
        for record in records:
            username = record["username"]
            user = User.objects.filter(username=username).first()
            if user is None:
                user = User(email=username + MARKER_DOMAIN, **record)
                try:
                    validate_password(password, user)
                except ValidationError as error:
                    raise CommandError("DEMO_ACCOUNT_PASSWORD was rejected: " + " ".join(error.messages)) from None
                user.set_password(password)
                user.full_clean()
                user.save()
            elif user.email != username + MARKER_DOMAIN or user.is_staff or user.is_superuser:
                raise CommandError(f"Refusing to adopt the existing account {username}.")
            elif not user.check_password(password):
                raise CommandError(f"DEMO_ACCOUNT_PASSWORD does not match the existing account {username}; it was not reset.")
            users[username] = user
        return users

    def _venues(self, records, organizer):
        venues = {}
        for record in records:
            venue = Venue.objects.filter(name=record["name"], address=record["address"]).first()
            if venue is None:
                venue = Venue(submitted_by=organizer, review_note=VENUE_NOTE, **record)
                venue.full_clean()
                venue.save()
            venues[record["name"]] = venue
        return venues

    def _artists(self, records, categories):
        for record in records:
            fields = {k: v for k, v in record.items() if k not in ("name", "categories")}
            artist, created = DJProfile.objects.get_or_create(name=record["name"], defaults=fields)
            if created:
                artist.categories.set(categories[name] for name in record["categories"])
        return {a.name: a for a in DJProfile.objects.all()}

    def _events(self, records, users, venues, categories, tags, artists, refresh_dates):
        events, created, moved = {}, 0, 0
        today = timezone.localdate(timezone=ZoneInfo("Europe/Madrid"))
        dates = schedule(records, today)
        for record in records:
            creator, venue = users[record["creator"]], venues[record["venue"]]
            hour, minute = map(int, record["start_time"].split(":"))
            starts = datetime.combine(dates[record["title"]], time(hour, minute), tzinfo=ZoneInfo(venue.timezone))
            ends = starts + timedelta(minutes=record["minutes"])
            category_ids = [categories[name].pk for name in record["categories"]]
            tag_ids = [tags[tuple(pair)].pk for pair in record["tags"]]
            event = Event.objects.filter(title=record["title"], creator=creator).first()
            if event is None:
                event = services.save_event(actor=creator, category_ids=category_ids, tag_ids=tag_ids,
                    performer_ids=[artists[name].pk for name in record["performers"]],
                    data={"venue": venue, "title": record["title"], "ticket_url": record["ticket_url"],
                          "description": f"{record['description']}\n\n{NOTE}", "starts_at": starts, "ends_at": ends})
                event.demo_poster = record["poster"]
                event.save(update_fields=["demo_poster"])
                created += 1
            elif refresh_dates and event.cancelled_at is None and event.starts_at != starts:
                event = services.save_event(actor=creator, event_id=event.pk, data={"starts_at": starts, "ends_at": ends},
                    category_ids=list(event.categories.values_list("pk", flat=True)),
                    tag_ids=list(event.tags.values_list("pk", flat=True)))
                moved += 1
            events[record["title"]] = event
        return events, created, moved
