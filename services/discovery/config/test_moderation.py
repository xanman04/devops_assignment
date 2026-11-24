"""Authentication, permission, validation, and domain-rule tests for moderation JSON."""
import json
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.utils import timezone

from discovery import services
from discovery.models import EventReport, Venue
from . import moderation_api
from .authentication import issue_token


class ModerationApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user("moderation-owner", password="owner-password")
        cls.reporter = User.objects.create_user("moderation-reporter", password="reporter-password")
        cls.venue_mod = User.objects.create_user("venue-moderator", password="venue-password")
        cls.report_mod = User.objects.create_user("report-moderator", password="report-password")
        cls.hide_denied_mod = User.objects.create_user("hide-denied", password="hide-password")
        cls.admin = User.objects.create_superuser("moderation-admin", password="admin-password")

        def grant(user, codename):
            permission = Permission.objects.get(
                codename=codename, content_type__app_label="discovery")
            user.user_permissions.add(permission)

        grant(cls.venue_mod, "change_venue")
        grant(cls.report_mod, "change_eventreport")
        grant(cls.hide_denied_mod, "change_eventreport")
        cls.category = services.save_category(actor=cls.admin, data={
            "name": "House", "color": "#123456", "description": "House music"})
        cls.pending_venue = services.save_venue(actor=cls.owner, data={
            "name": "Pending venue", "latitude": "40.4", "longitude": "-3.7",
            "timezone": "Europe/Madrid"})
        cls.approved_venue = services.save_venue(actor=cls.admin,
            review_status=Venue.ReviewStatus.APPROVED, data={
                "name": "Approved venue", "latitude": "40.5", "longitude": "-3.8",
                "timezone": "Europe/Madrid"})
        start = timezone.now() + timedelta(days=5)
        cls.event = services.save_event(actor=cls.owner, data={
            "venue": cls.approved_venue, "title": "Reported event",
            "description": "A public event", "starts_at": start,
            "ends_at": start + timedelta(hours=4), "ticket_url": ""},
            category_ids=[cls.category.pk])
        cls.report = services.report_event(actor=cls.reporter,
            event_id=cls.event.pk, reason=EventReport.Reason.OTHER,
            explanation="Please review this listing.")

    def call(self, view, *, actor=None, method="get", data=None, args=()):
        factory = RequestFactory()
        headers = {}
        if actor is not None:
            password = {
                "moderation-owner": "owner-password",
                "moderation-reporter": "reporter-password",
                "venue-moderator": "venue-password",
                "report-moderator": "report-password",
                "hide-denied": "hide-password",
                "moderation-admin": "admin-password",
                "ordinary": "ordinary-password",
            }[actor.username]
            headers["HTTP_AUTHORIZATION"] = "Bearer " + issue_token(actor.username, password)
        if method == "get":
            request = factory.get("/api/moderation/", **headers)
        else:
            request = getattr(factory, method)("/api/moderation/", data=json.dumps(data),
                content_type="application/json", **headers)
        return view(request, *args)

    def test_authentication_and_no_permission_are_rejected(self):
        self.assertEqual(self.call(moderation_api.queue).status_code, 401)
        ordinary = get_user_model().objects.create_user("ordinary", password="ordinary-password")
        self.assertEqual(self.call(moderation_api.queue, actor=ordinary).status_code, 403)

    def test_routed_reviews_hide_object_existence_from_unauthorized_users(self):
        headers = {'HTTP_AUTHORIZATION': 'Bearer '+issue_token(self.owner.username, 'owner-password')}
        for identity in (self.pending_venue.pk, 999999):
            response = self.client.post(f'/api/moderation/venues/{identity}/review/',
                json.dumps({'status': 'approved', 'review_note': ''}), content_type='application/json', **headers)
            self.assertEqual(response.status_code, 403)
        for user, password, expected in ((self.owner, 'owner-password', False), (self.venue_mod, 'venue-password', True)):
            response = self.client.get('/api/account/', HTTP_AUTHORIZATION='Bearer '+issue_token(user.username, password))
            self.assertEqual(response.json()['can_moderate'], expected)

    def test_queue_exposes_only_authorized_pending_domains(self):
        venues = json.loads(self.call(moderation_api.queue, actor=self.venue_mod).content)
        self.assertTrue(venues["capabilities"]["venues"])
        self.assertFalse(venues["capabilities"]["reports"])
        self.assertFalse(venues["capabilities"]["hide_events"])
        self.assertEqual([row["id"] for row in venues["pending_venues"]], [self.pending_venue.pk])
        self.assertEqual(venues["pending_reports"], [])
        reports = json.loads(self.call(moderation_api.queue, actor=self.report_mod).content)
        self.assertFalse(reports["capabilities"]["venues"])
        self.assertTrue(reports["capabilities"]["reports"])
        self.assertEqual(reports["pending_venues"], [])
        self.assertEqual([row["id"] for row in reports["pending_reports"]], [self.report.pk])
        self.assertEqual(set(reports["pending_reports"][0]),
            {"id", "event_id", "event_title", "reason", "explanation", "status"})
        self.assertNotIn("email", str(reports))

    def test_valid_venue_and_report_reviews_record_reviewer(self):
        approved = self.call(moderation_api.review_venue, actor=self.venue_mod,
            method="post", args=(self.pending_venue.pk,),
            data={"status": "approved", "review_note": "Checked"})
        self.assertEqual(approved.status_code, 200, approved.content)
        self.assertEqual(json.loads(approved.content), {"id": self.pending_venue.pk, "status": "approved"})
        self.pending_venue.refresh_from_db()
        self.assertEqual(self.pending_venue.reviewed_by, self.venue_mod)
        self.assertEqual(self.pending_venue.review_note, "Checked")

        reviewed = self.call(moderation_api.review_report, actor=self.report_mod,
            method="post", args=(self.report.pk,),
            data={"status": "dismissed", "resolution_note": "Reviewed", "hide_event": False})
        self.assertEqual(reviewed.status_code, 200, reviewed.content)
        self.report.refresh_from_db()
        self.assertEqual(self.report.reviewed_by, self.report_mod)
        self.assertEqual(self.report.resolution_note, "Reviewed")

    def test_denied_hide_is_atomic_for_report_and_event(self):
        response = self.call(moderation_api.review_report, actor=self.hide_denied_mod,
            method="post", args=(self.report.pk,),
            data={"status": "actioned", "resolution_note": "Hide", "hide_event": True})
        self.assertEqual(response.status_code, 403)
        self.report.refresh_from_db()
        self.event.refresh_from_db()
        self.assertEqual(self.report.status, EventReport.Status.PENDING)
        self.assertIsNone(self.report.reviewed_by)
        self.assertFalse(self.event.moderation_hidden)

    def test_granted_reviewer_can_hide_reported_event_but_cannot_edit_others_events(self):
        with patch.dict('os.environ', {'MODERATOR_USERNAME': self.report_mod.username}):
            call_command('grant_moderator', stdout=StringIO())
        headers = {'HTTP_AUTHORIZATION': 'Bearer '+issue_token(self.report_mod.username, 'report-password')}
        payload = {'event': {'venue_id': self.approved_venue.pk, 'title': 'Unauthorized rename',
            'description': 'Changed', 'starts_at': self.event.starts_at.isoformat(),
            'ends_at': self.event.ends_at.isoformat(), 'ticket_url': ''}, 'category_ids': [self.category.pk]}
        response = self.client.put(f'/api/events/{self.event.pk}/edit/', json.dumps(payload),
                                  content_type='application/json', **headers)
        self.assertEqual(response.status_code, 403)
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, 'Reported event')
        response = self.client.post(f'/api/moderation/reports/{self.report.pk}/review/',
            json.dumps({'status': 'actioned', 'resolution_note': 'Reviewed', 'hide_event': True}),
            content_type='application/json', **headers)
        self.assertEqual(response.status_code, 200, response.content)
        self.event.refresh_from_db(); self.report.refresh_from_db()
        self.assertTrue(self.event.moderation_hidden)
        self.assertEqual(self.report.status, 'actioned')

    def test_payload_validation_and_missing_ids(self):
        good_venue = {"status": "approved", "review_note": ""}
        for payload in ({**good_venue, "forged": True},
                        {"status": "pending", "review_note": ""},
                        {"status": "approved", "review_note": 4},
                        {"status": "approved", "review_note": "x" * 2001}):
            with self.subTest(payload=payload):
                response = self.call(moderation_api.review_venue, actor=self.venue_mod,
                    method="post", args=(self.pending_venue.pk,), data=payload)
                self.assertEqual(response.status_code, 400, response.content)
        good_report = {"status": "dismissed", "resolution_note": "", "hide_event": False}
        for payload in ({**good_report, "forged": True},
                        {**good_report, "hide_event": 1},
                        {**good_report, "resolution_note": "x" * 2001},
                        {**good_report, "status": "pending"}):
            response = self.call(moderation_api.review_report, actor=self.report_mod,
                method="post", args=(self.report.pk,), data=payload)
            self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(self.call(moderation_api.review_venue, actor=self.venue_mod,
            method="post", args=(999999,), data=good_venue).status_code, 404)
        self.assertEqual(self.call(moderation_api.review_report, actor=self.report_mod,
            method="post", args=(999999,), data=good_report).status_code, 404)

    def test_malformed_json_and_methods(self):
        request = RequestFactory().post("/api/moderation/", data="{", content_type="application/json",
            HTTP_AUTHORIZATION="Bearer " + issue_token("venue-moderator", "venue-password"))
        self.assertEqual(moderation_api.review_venue(request, self.pending_venue.pk).status_code, 400)
        self.assertEqual(self.call(moderation_api.queue, actor=self.venue_mod,
            method="post", data={}).status_code, 405)
        self.assertEqual(self.call(moderation_api.review_venue, actor=self.venue_mod,
            method="get", args=(self.pending_venue.pk,)).status_code, 405)
        self.assertEqual(self.call(moderation_api.review_report, actor=self.report_mod,
            method="get", args=(self.report.pk,)).status_code, 405)
