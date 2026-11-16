# Copyright © 2026 Xander Chen. All rights reserved.
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from notifications.models import Notification
from notifications.services import inbox, mark_read
from . import services as s
from .models import DJProfile, Event, EventChange, EventFollow, EventReport, GenreTag, Venue
from .forms import EventForm


class DiscoveryServicesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser("admin", password="example-password")
        cls.owner = get_user_model().objects.create_user("owner")
        cls.other = get_user_model().objects.create_user("other")
        cls.house = s.save_category(actor=cls.admin, data={
            "name": "House", "color": "#0000FF", "description": "House music", "bpm_min": 110, "bpm_max": 135,
        })
        cls.rock = s.save_category(actor=cls.admin, data={
            "name": "Rock", "color": "#FF0000", "description": "Rock music", "bpm_min": 70, "bpm_max": 180,
        })
        cls.afro = s.save_tag(actor=cls.admin, data={
            "name": "Afrohouse", "category": cls.house, "description": "Afrohouse", "bpm_min": 115, "bpm_max": 125,
        })
        cls.venue = s.save_venue(actor=cls.admin, review_status="approved", data={
            "name": "Main venue", "latitude": "48.850000", "longitude": "2.350000", "timezone": "Europe/Paris",
        })
        cls.start = timezone.now() + timedelta(days=1)

    def make_event(self, **overrides):
        data = dict(venue=self.venue, title="Music tonight", description="Example", starts_at=self.start,
                    ends_at=self.start + timedelta(hours=5), ticket_url="https://example.org/tickets")
        data.update(overrides)
        return s.save_event(actor=self.owner, data=data, category_ids=[self.house.pk], tag_ids=[self.afro.pk])

    def edit(self, event, **kwargs):
        return s.save_event(actor=self.owner, event_id=event.pk, category_ids=[self.house.pk], tag_ids=[self.afro.pk], **kwargs)

    def test_admin_curates_and_normal_users_cannot(self):
        with self.assertRaises(PermissionDenied):
            s.save_category(actor=self.owner, data={"name": "Fake"})
        with self.assertRaises(ValidationError):
            s.save_category(actor=self.admin, data={"name": " house ", "color": "#111111", "description": "Duplicate"})
        with self.assertRaises(ValidationError):
            s.save_category(actor=self.admin, category_id=self.house.pk, data={"color": "red"})

    def test_create_event_with_multiple_tags_and_no_manual_bpm(self):
        tag = s.save_tag(actor=self.admin, data={"category": self.house, "name": "Deep", "description": "Deep"})
        event = self.make_event()
        event = s.save_event(actor=self.owner, event_id=event.pk, data={}, category_ids=[self.house.pk], tag_ids=[self.afro.pk, tag.pk])
        self.assertEqual(event.tags.count(), 2)
        self.assertEqual(s.tempo_estimate(event), (110, 135))
        with self.assertRaises(ValidationError):
            self.edit(event, data={"bpm_min": 120})

    def test_invalid_classification_rolls_back_edit(self):
        event = self.make_event()
        for categories, tags in [([], []), ([self.rock.pk], [self.afro.pk]), ([999999], []), ([self.house.pk], [999999])]:
            with self.subTest(categories=categories, tags=tags), self.assertRaises(ValidationError):
                s.save_event(actor=self.owner, event_id=event.pk, data={"title": "Wrong"}, category_ids=categories, tag_ids=tags)
        event.refresh_from_db()
        self.assertEqual(event.title, "Music tonight")
        self.assertEqual(event.categories.get(), self.house)

    def test_event_edit_permissions_and_protected_fields(self):
        event = self.make_event()
        for actor in [self.other, AnonymousUser()]:
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                s.save_event(actor=actor, event_id=event.pk, data={"title": "Stolen"}, category_ids=[self.house.pk])
        with self.assertRaises(PermissionDenied):
            self.edit(event, data={}, hidden=False)
        with self.assertRaises(ValidationError):
            self.edit(event, data={"creator": self.other})
        self.owner.is_active = False
        with self.assertRaises(PermissionDenied):
            self.edit(event, data={})

    def test_venue_approval_and_edit_permissions(self):
        venue = s.save_venue(actor=self.owner, data={"name": "New", "latitude": 45, "longitude": 3, "timezone": "Europe/Paris"})
        event = self.make_event(venue=venue)
        self.assertFalse(s.search_events().filter(pk=event.pk).exists())
        with self.assertRaises(Event.DoesNotExist):
            s.get_event(event_id=event.pk)
        self.assertEqual(s.get_event(event_id=event.pk, actor=self.owner), event)
        with self.assertRaises(PermissionDenied):
            s.save_venue(actor=self.owner, venue_id=venue.pk, data={"latitude": 46})
        with self.assertRaises(PermissionDenied):
            s.save_venue(actor=self.other, data={"name": "Fake"}, review_status="approved")
        s.save_venue(actor=self.admin, venue_id=venue.pk, data={}, review_status="approved")
        self.assertTrue(s.search_events().filter(pk=event.pk).exists())

    def test_pending_location_cannot_be_claimed_by_another_user(self):
        venue = s.save_venue(actor=self.other, data={"name": "Private", "latitude": 45, "longitude": 3, "timezone": "UTC"})
        with self.assertRaises(PermissionDenied):
            self.make_event(venue=venue)

    def test_naive_invalid_times_and_url_rejected(self):
        with self.assertRaises(ValidationError):
            self.make_event(starts_at=datetime(2026, 10, 1))
        with self.assertRaises(ValidationError):
            self.make_event(ends_at=self.start)
        with self.assertRaises(ValidationError):
            self.make_event(ticket_url="ftp://example.org/tickets")

    def test_followed_multi_field_edit_is_one_history_and_one_notice(self):
        event = self.make_event()
        s.follow_event(actor=self.other, event_id=event.pk)
        self.edit(event, data={"starts_at": self.start + timedelta(hours=1), "ends_at": self.start + timedelta(hours=6)})
        change = EventChange.objects.get(event=event)
        self.assertEqual(set(change.changes), {"starts_at", "ends_at"})
        notice = Notification.objects.get(recipient=self.other)
        self.assertEqual(notice.event_change, change)
        self.assertEqual(change.changes["starts_at"]["before"], self.start.astimezone(dt_timezone.utc).isoformat())
        self.edit(event, data={"title": "Updated title"})
        self.assertEqual(Notification.objects.count(), 1)

    def test_repeated_save_and_cancellation_do_not_duplicate_notices(self):
        event = self.make_event()
        s.follow_event(actor=self.other, event_id=event.pk)
        self.edit(event, data={}, cancelled=True)
        self.edit(event, data={}, cancelled=True)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertFalse(s.search_events().filter(pk=event.pk).exists())
        self.assertIsNotNone(s.get_event(event_id=event.pk).cancelled_at)
        self.edit(event, data={}, cancelled=False)
        self.assertEqual(Notification.objects.count(), 2)

    def test_failed_notification_rolls_back_event_and_history(self):
        event = self.make_event()
        s.follow_event(actor=self.other, event_id=event.pk)
        with patch("discovery.services.Notification.objects.bulk_create", side_effect=RuntimeError("write failed")):
            with self.assertRaises(RuntimeError):
                self.edit(event, data={}, cancelled=True)
        event.refresh_from_db()
        self.assertIsNone(event.cancelled_at)
        self.assertFalse(EventChange.objects.exists())

    def test_move_to_pending_venue_does_not_leak_coordinates(self):
        event = self.make_event()
        other_event = self.make_event(title="Stays put")
        s.follow_event(actor=self.other, event_id=event.pk)
        venue = s.save_venue(actor=self.owner, data={"name": "Secret field", "latitude": "44.123456", "longitude": 3, "timezone": "UTC"})
        self.edit(event, data={"venue": venue})
        other_event.refresh_from_db()
        self.assertEqual(other_event.venue_id, self.venue.pk)
        self.assertFalse(s.search_events().filter(pk=event.pk).exists())
        notice = Notification.objects.get()
        self.assertNotIn("44.123456", notice.summary)
        self.assertNotIn("Secret field", notice.summary)
        self.assertIn("awaiting approval", notice.summary)
        with self.assertRaises(Event.DoesNotExist):
            s.get_event(event_id=event.pk, actor=self.other)

    def test_shared_venue_edit_notifies_each_affected_event(self):
        events = [self.make_event(), self.make_event(title="Second")]
        for event in events:
            s.follow_event(actor=self.other, event_id=event.pk)
        s.save_venue(actor=self.admin, venue_id=self.venue.pk, data={"latitude": "48.860000"})
        self.assertEqual(Notification.objects.count(), 2)
        self.assertEqual(EventChange.objects.filter(kind="venue_details_edit").count(), 2)

    def test_hidden_state_survives_creator_edits(self):
        event = self.make_event()
        s.save_event(actor=self.admin, event_id=event.pk, data={}, category_ids=[self.house.pk], hidden=True)
        self.edit(event, data={"title": "New title"})
        event.refresh_from_db()
        self.assertTrue(event.moderation_hidden)
        self.assertFalse(s.search_events().exists())

    def test_any_all_filters_and_date_overlap(self):
        event = self.make_event()
        mixed = self.make_event(title="Mixed")
        s.save_event(actor=self.owner, event_id=mixed.pk, data={}, category_ids=[self.house.pk, self.rock.pk], tag_ids=[self.afro.pk])
        self.assertEqual(s.search_events(category_ids=[self.house.pk, self.rock.pk], match="any").count(), 2)
        self.assertEqual(list(s.search_events(category_ids=[self.house.pk, self.rock.pk], match="all")), [mixed])
        self.assertEqual(s.search_events(tag_ids=[self.afro.pk]).count(), 2)
        self.assertEqual(s.search_events(starts_at=self.start+timedelta(hours=1), ends_at=self.start+timedelta(hours=2)).count(), 2)
        self.assertFalse(s.search_events(starts_at=self.start+timedelta(hours=5), ends_at=self.start+timedelta(hours=6)).exists())

    def test_map_bounds_including_date_line_and_invalid_values(self):
        event = self.make_event()
        self.assertEqual(list(s.search_events(bounds=(48, 2, 49, 3))), [event])
        self.assertFalse(s.search_events(bounds=(-10, 170, 10, -170)).exists())
        venue = s.save_venue(actor=self.admin, review_status="approved", data={"name": "Date line", "latitude": 0, "longitude": 179, "timezone": "UTC"})
        crossing = self.make_event(venue=venue)
        self.assertEqual(list(s.search_events(bounds=(-10, 170, 10, -170))), [crossing])
        for bounds in [(91, 0, 92, 1), (2, 0, 1, 1), ("NaN", 0, 1, 1), (0, 1)]:
            with self.subTest(bounds=bounds), self.assertRaises(ValidationError):
                s.search_events(bounds=bounds)

    def test_tempo_subtag_override_category_fallback_and_unknown(self):
        event = self.make_event()
        self.assertEqual(s.tempo_estimate(event), (115, 125))
        s.save_event(actor=self.owner, event_id=event.pk, data={}, category_ids=[self.house.pk], tag_ids=[])
        self.assertEqual(s.tempo_estimate(Event.objects.get(pk=event.pk)), (110, 135))
        s.save_event(actor=self.owner, event_id=event.pk, data={}, category_ids=[self.house.pk, self.rock.pk], tag_ids=[self.afro.pk])
        self.assertEqual(s.tempo_estimate(Event.objects.get(pk=event.pk)), (70, 180))
        s.save_category(actor=self.admin, category_id=self.rock.pk, data={"bpm_min": None, "bpm_max": None})
        self.assertIsNone(s.tempo_estimate(Event.objects.get(pk=event.pk)))

    def test_tempo_combines_selected_tag_ranges_and_updates_without_event_edit(self):
        second = s.save_tag(actor=self.admin, data={
            "category": self.house, "name": "Fast house", "description": "Example",
            "bpm_min": 132, "bpm_max": 142,
        })
        event = self.make_event()
        s.save_event(actor=self.owner, event_id=event.pk, data={},
                     category_ids=[self.house.pk], tag_ids=[self.afro.pk, second.pk])
        self.assertEqual(s.tempo_estimate(Event.objects.get(pk=event.pk)), (115, 142))
        s.save_tag(actor=self.admin, tag_id=second.pk, data={"bpm_min": 118, "bpm_max": 122})
        self.assertEqual(s.tempo_estimate(Event.objects.get(pk=event.pk)), (115, 125))


    def test_pins_count_only_matching_events_without_private_fields(self):
        self.make_event()
        self.make_event(title="Second")
        hidden = self.make_event(title="Hidden")
        s.save_event(actor=self.admin, event_id=hidden.pk, data={}, category_ids=[self.house.pk], hidden=True)
        response = self.client.get("/api/map/events/")
        self.assertEqual(response.status_code, 200)
        pin = response.json()["venues"][0]
        self.assertEqual(pin["count"], 2)
        self.assertEqual(len(pin["categories"]), 1)
        self.assertNotIn("review_note", str(response.json()))
        self.assertNotIn("email", str(response.json()))

    def test_bad_endpoint_input_is_400_not_server_error(self):
        for query in [{"start": "tomorrow"}, {"start": "2026-10-01"}, {"match": "xor"}, {"categories": "oops"}, {"bounds": ""}, {"tags": "999999"}, {"categories": "99999999999999999999999999"}, {"start": "9999-12-31T00:00:00Z"}]:
            with self.subTest(query=query):
                self.assertEqual(self.client.get("/api/map/events/", query).status_code, 400)
        self.assertEqual(self.client.post("/api/map/events/").status_code, 405)

    def test_follow_unfollow_and_recipient_scoped_inbox(self):
        event = self.make_event()
        s.follow_event(actor=self.other, event_id=event.pk)
        s.follow_event(actor=self.other, event_id=event.pk)
        self.assertEqual(EventFollow.objects.count(), 1)
        self.edit(event, data={}, cancelled=True)
        notice = inbox(actor=self.other).get()
        self.assertFalse(inbox(actor=self.owner).exists())
        with self.assertRaises(Notification.DoesNotExist):
            mark_read(actor=self.owner, notification_id=notice.pk)
        mark_read(actor=self.other, notification_id=notice.pk)
        self.assertFalse(inbox(actor=self.other, unread_only=True).exists())
        s.unfollow_event(actor=self.other, event_id=event.pk)
        self.edit(event, data={}, cancelled=False)
        self.assertEqual(Notification.objects.count(), 1)

    def test_reporting_requires_review_not_automatic_removal(self):
        event = self.make_event()
        report = s.report_event(actor=self.other, event_id=event.pk, reason="safety_concern", explanation="Check")
        self.assertTrue(s.search_events().exists())
        with self.assertRaises(PermissionDenied):
            s.review_report(actor=self.other, report_id=report.pk, status="actioned", hide_event=True)
        s.review_report(actor=self.admin, report_id=report.pk, status="actioned", hide_event=True)
        self.assertFalse(s.search_events().exists())
        report.refresh_from_db()
        self.assertEqual(report.reviewed_by, self.admin)

    def test_references_permissions_and_category_consistency(self):
        event = self.make_event()
        data = dict(title="Set", artist_credit="Artist", kind="set", url="https://example.org/set", display_order=0)
        ref = s.save_event_reference(actor=self.owner, event_id=event.pk, data=data)
        with self.assertRaises(PermissionDenied):
            s.save_event_reference(actor=self.other, event_id=event.pk, data=data, reference_id=ref.pk)
        curated = s.save_genre_reference(actor=self.admin, data=data, category_ids=[self.house.pk], tag_ids=[self.afro.pk])
        with self.assertRaises(ValidationError):
            s.save_genre_reference(actor=self.admin, reference_id=curated.pk, data={}, category_ids=[self.rock.pk], tag_ids=[self.afro.pk])
        s.delete_event_reference(actor=self.owner, reference_id=ref.pk)
        self.assertFalse(event.listening_references.exists())

    def test_used_tag_cannot_move_and_break_existing_events(self):
        self.make_event()
        with self.assertRaises(ValidationError):
            s.save_tag(actor=self.admin, tag_id=self.afro.pk, data={"category": self.rock})
        self.assertEqual(GenreTag.objects.get(pk=self.afro.pk).category_id, self.house.pk)

    def event_admin_payload(self, **updates):
        data = {
            "venue": self.venue.pk, "title": "Via admin", "description": "Description",
            "starts_at_0": "2026-10-01", "starts_at_1": "20:00:00",
            "ends_at_0": "2026-10-02", "ends_at_1": "02:00:00",
            "categories": [self.house.pk], "tags": [self.afro.pk], "ticket_url": "", "_save": "Save",
        }
        data.update(updates)
        return data






    def test_equivalent_coordinate_format_does_not_send_false_alert(self):
        event = self.make_event()
        s.follow_event(actor=self.other, event_id=event.pk)
        s.save_venue(actor=self.admin, venue_id=self.venue.pk, data={"latitude": "48.85", "longitude": "2.35"})
        self.assertFalse(EventChange.objects.exists())
        self.assertFalse(Notification.objects.exists())




    def test_local_datetime_rejects_dst_gap_and_ambiguity(self):
        for day, clock in [("2026-03-29", "02:30:00"), ("2026-10-25", "02:30:00")]:
            with self.subTest(day=day):
                form = EventForm(data=self.event_admin_payload(
                    starts_at_0=day, starts_at_1=clock, ends_at_0=day, ends_at_1="05:00:00",
                ))
                self.assertFalse(form.is_valid())
                self.assertIn("starts_at", form.errors)

    def test_local_datetime_uses_new_venue_on_edit(self):
        event = self.make_event()
        venue = s.save_venue(actor=self.admin, review_status="approved", data={
            "name": "New York", "latitude": 40, "longitude": -74, "timezone": "America/New_York",
        })
        form = EventForm(instance=event, data=self.event_admin_payload(venue=venue.pk))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["starts_at"].astimezone(dt_timezone.utc), datetime(2026, 10, 2, 0, tzinfo=dt_timezone.utc))




    def test_nearby_performer_search_uses_matching_event_before_deduplication(self):
        performer = DJProfile.objects.create(name="Mira Sol", description="Live DJ")
        performer.categories.add(self.house)
        first = self.make_event(title="First night")
        second = self.make_event(title="Second night", starts_at=self.start + timedelta(days=1),
                                 ends_at=self.start + timedelta(days=1, hours=5))
        deep = s.save_tag(actor=self.admin, data={
            "name": "Deep House", "category": self.house, "description": "Deep House",
        })
        s.save_event(actor=self.owner, event_id=second.pk, data={}, category_ids=[self.house.pk],
                     tag_ids=[deep.pk])
        first.performers.add(performer)
        second.performers.add(performer)
        results = s.nearby_performers(latitude=48.85, longitude=2.35, search_terms={"Deep House"})
        self.assertEqual(results, [(performer, second)])


    def test_nearby_performers_have_no_date_limit_and_come_in_date_order(self):
        later = DJProfile.objects.create(name="Later DJ", description="x")
        sooner = DJProfile.objects.create(name="Sooner DJ", description="x")
        for dj in (later, sooner):
            dj.categories.add(self.house)
        far = self.make_event(title="Months away", starts_at=self.start + timedelta(days=90), ends_at=self.start + timedelta(days=90, hours=5))
        near = self.make_event(title="Next week", starts_at=self.start + timedelta(days=7), ends_at=self.start + timedelta(days=7, hours=5))
        far.performers.add(later)
        near.performers.add(sooner)
        results = s.nearby_performers(latitude=48.85, longitude=2.35)
        self.assertEqual([performer.name for performer, event in results], ["Sooner DJ", "Later DJ"])
