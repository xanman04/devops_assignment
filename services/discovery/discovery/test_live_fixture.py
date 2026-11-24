"""Tests for the explicit, idempotent production live-check fixture command."""
import json
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase
from django.utils import timezone

from discovery import services
from discovery.management.commands.prepare_live_check import (
    EVENT_TITLE, GUEST_USERNAME, MARKER, OWNER_USERNAME, VENUE_NAME,
)
from discovery.models import Event, GenreCategory, Venue


PASSWORD = "controlled-release-test-password-123456789"


class PrepareLiveCheckTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = services.save_category(
            actor=get_user_model().objects.create_superuser("moderator", password="test-password"),
            data={"name": "House", "color": "#123456", "description": "House music"},
        )

    def run_command(self, password=PASSWORD):
        output = StringIO()
        with patch.dict("os.environ", {"LIVE_CHECK_PASSWORD": password}):
            call_command("prepare_live_check", stdout=output)
        return json.loads(output.getvalue())

    def test_rerun_is_stable_and_creates_unprivileged_accounts(self):
        first = self.run_command()
        second = self.run_command()
        self.assertEqual(first["event_id"], second["event_id"])
        self.assertEqual(first["owner_username"], OWNER_USERNAME)
        self.assertEqual(first["guest_username"], GUEST_USERNAME)
        self.assertEqual(first["event_title"], EVENT_TITLE)
        self.assertNotIn("password", first)
        User = get_user_model()
        for username in (OWNER_USERNAME, GUEST_USERNAME):
            user = User.objects.get(username=username)
            self.assertEqual(user.bio, MARKER)
            self.assertFalse(user.is_staff)
            self.assertFalse(user.is_superuser)
            self.assertFalse(user.groups.exists())
            self.assertFalse(user.user_permissions.exists())
            self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(Venue.objects.filter(name=VENUE_NAME).count(), 1)
        self.assertEqual(Event.objects.filter(title=EVENT_TITLE).count(), 1)

    def test_rejects_unrelated_account_name_without_overwriting_it(self):
        User = get_user_model()
        unrelated = User.objects.create_user(OWNER_USERNAME, password="keep-this-password", bio="not ours")
        with self.assertRaises(CommandError):
            self.run_command()
        unrelated.refresh_from_db()
        self.assertEqual(unrelated.bio, "not ours")
        self.assertTrue(unrelated.check_password("keep-this-password"))
        self.assertFalse(User.objects.filter(username=GUEST_USERNAME).exists())

    def test_rejects_fixture_password_mismatch(self):
        self.run_command()
        with self.assertRaises(CommandError):
            self.run_command("different-controlled-release-password-123456")
        self.assertTrue(get_user_model().objects.get(username=OWNER_USERNAME).check_password(PASSWORD))

    def test_rejects_venue_name_owned_by_another_account(self):
        User = get_user_model()
        unrelated = User.objects.create_user("venue-owner")
        Venue.objects.create(name=VENUE_NAME, address="", latitude=40, longitude=-3,
            timezone="Europe/Madrid", submitted_by=unrelated,
            review_status=Venue.ReviewStatus.APPROVED)
        with self.assertRaises(CommandError):
            self.run_command()
        self.assertFalse(User.objects.filter(username=OWNER_USERNAME).exists())
        self.assertFalse(User.objects.filter(username=GUEST_USERNAME).exists())

    def test_rejects_event_name_owned_by_another_account(self):
        User = get_user_model()
        unrelated = User.objects.create_user("event-owner")
        venue = Venue.objects.create(name="Other venue", address="", latitude=40, longitude=-3,
            timezone="Europe/Madrid", submitted_by=unrelated,
            review_status=Venue.ReviewStatus.APPROVED)
        starts_at = timezone.now() + timedelta(days=7)
        Event.objects.create(creator=unrelated, venue=venue, title=EVENT_TITLE,
            description="Unrelated", starts_at=starts_at, ends_at=starts_at + timedelta(hours=4))
        with self.assertRaises(CommandError):
            self.run_command()
        self.assertFalse(User.objects.filter(username=OWNER_USERNAME).exists())
        self.assertFalse(User.objects.filter(username=GUEST_USERNAME).exists())

    def test_fixture_setup_rolls_back_if_event_creation_fails(self):
        with patch("discovery.management.commands.prepare_live_check.services.save_event",
                   side_effect=RuntimeError("synthetic rollback check")):
            with self.assertRaises(RuntimeError):
                self.run_command()
        self.assertFalse(get_user_model().objects.filter(
            username__in=(OWNER_USERNAME, GUEST_USERNAME)).exists())
        self.assertFalse(Venue.objects.filter(name=VENUE_NAME).exists())
        self.assertFalse(Event.objects.filter(title=EVENT_TITLE).exists())
