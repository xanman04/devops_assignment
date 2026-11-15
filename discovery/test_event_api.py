# Copyright © 2026 Xander Chen. All rights reserved.
"""Visibility and stable response checks at the future service boundary."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import services
from .models import Event


class EventDetailsApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_superuser(
            "event-owner", password="test-only-password"
        )
        category = services.save_category(actor=cls.owner, data={
            "name": "House", "color": "#123456", "description": "Music",
        })
        cls.venue = services.save_venue(actor=cls.owner, review_status="approved", data={
            "name": "Test venue", "latitude": 48, "longitude": 2,
            "timezone": "Europe/Paris",
        })
        start = timezone.now() + timedelta(days=1)
        cls.event = services.save_event(actor=cls.owner, category_ids=[category.pk], data={
            "venue": cls.venue, "title": "Test event", "description": "Music",
            "starts_at": start, "ends_at": start + timedelta(hours=3),
        })

    def url(self, event_id=None):
        return reverse("api-event-details", args=[event_id or self.event.pk])

    def test_anonymous_get_returns_only_contract_fields(self):
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "id": self.event.pk, "title": "Test event",
            "starts_at": self.event.starts_at.isoformat(),
            "ends_at": self.event.ends_at.isoformat(), "cancelled": False,
            "venue": {"id": self.venue.pk, "name": "Test venue",
                      "timezone": "Europe/Paris"},
        })

    def test_cancelled_and_past_events_keep_their_public_details(self):
        Event.objects.filter(pk=self.event.pk).update(
            cancelled_at=timezone.now(), starts_at=timezone.now() - timedelta(days=2),
            ends_at=timezone.now() - timedelta(days=1),
        )
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["cancelled"])

    def test_hidden_and_missing_events_are_indistinguishable_even_for_owner(self):
        self.client.force_login(self.owner)
        Event.objects.filter(pk=self.event.pk).update(moderation_hidden=True)
        hidden = self.client.get(self.url())
        missing = self.client.get(self.url(self.event.pk + 1000))
        self.assertEqual(hidden.status_code, 404)
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(hidden.json(), missing.json())

    def test_unapproved_venue_and_missing_category_are_not_public(self):
        self.venue.review_status = "pending"
        self.venue.save(update_fields=["review_status"])
        self.assertEqual(self.client.get(self.url()).status_code, 404)
        self.venue.review_status = "approved"
        self.venue.save(update_fields=["review_status"])
        self.event.categories.clear()
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_write_methods_are_rejected(self):
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)(self.url()).status_code, 405)
