"""Groups HTTP adapters exercised against a contract-shaped Discovery stub.

The stub replaces only HTTP transport, not the Groups client or its validators.
It checks headers, URLs and timeouts, and refuses network work in transactions.
"""
import io
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.db import IntegrityError, OperationalError, connection, transaction
from django.test import Client, TransactionTestCase, override_settings
from django.utils import timezone

from groups import services
from groups.context import ContextError, permissions
from groups.models import AttendanceGroup, CreationReceipt, GroupBan, JoinRequest, Membership, Person


class Response(io.BytesIO):
    status = 200


class GroupsApiTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.identities = {
            'owner': {'id': 1, 'display_name': 'Owner', 'active': True, 'permissions': []},
            'guest': {'id': 2, 'display_name': 'Guest', 'active': True, 'permissions': []},
            'other': {'id': 3, 'display_name': 'Other', 'active': True, 'permissions': []},
            'admin': {'id': 4, 'display_name': 'Admin', 'active': True, 'permissions': ['groups.*']},
        }
        self.event = {'id': 10, 'title': 'Music night', 'starts_at':
            (timezone.now()+timedelta(days=2)).isoformat(), 'cancelled': False,
            'ends_at': (timezone.now()+timedelta(days=2,hours=4)).isoformat(),
            'venue': {'id': 1, 'name': 'Venue', 'timezone': 'Europe/Paris'}}
        self.event_status = 200
        self.identity_status = 200
        self.calls = []
        self.transport_error = None
        self.raw_response = None
        self.patcher = patch('groups.discovery_client.build_opener')
        self.opener = self.patcher.start().return_value
        self.opener.open.side_effect = self.peer
        self.addCleanup(self.patcher.stop)

    def peer(self, request, timeout):
        self.assertFalse(connection.in_atomic_block, 'HTTP while holding a local transaction')
        self.assertEqual(timeout, 2)
        self.calls.append(request.full_url)
        if self.transport_error:
            raise self.transport_error
        if self.raw_response is not None:
            return Response(self.raw_response)
        if request.full_url.endswith('/api/auth/identity/'):
            credential = request.get_header('Authorization', '').removeprefix('Bearer ')
            status = self.identity_status if credential in self.identities else 401
            data = self.identities.get(credential, {})
        else:
            self.assertEqual(request.full_url, settings.DISCOVERY_URL+'/api/events/10/')
            status, data = self.event_status, self.event
        if status != 200:
            raise HTTPError(request.full_url, status, 'test response', {}, io.BytesIO(b'{}'))
        return Response(json.dumps(data).encode())

    def call(self, path, data=None, actor='owner', method='post', key=None):
        headers = {'HTTP_AUTHORIZATION': 'Bearer '+actor} if actor else {}
        if key:
            headers['HTTP_IDEMPOTENCY_KEY'] = key
        if method == 'get':
            return self.client.get(path, **headers)
        return getattr(self.client, method)(path, json.dumps(data or {}), content_type='application/json', **headers)

    def create(self, actor='owner', capacity=4, mode='public', key='first'):
        return self.call('/api/groups/', {'event_id': 10, 'name': actor+' group', 'description': 'Music',
            'capacity': capacity, 'joining_mode': mode}, actor, key=key)

    def group(self, **kwargs):
        response = self.create(**kwargs)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    def action(self, group_id, action, actor='guest', **data):
        return self.call(f'/api/groups/{group_id}/{action}/', data, actor)

    def test_create_retry_and_conflicting_payload(self):
        group_id = self.group()
        self.event['cancelled'] = True
        before = len(self.calls)
        repeated = self.create()
        self.assertEqual(repeated.status_code, 201)
        self.assertEqual(repeated.json()['id'], group_id)
        self.assertEqual(len(self.calls)-before, 1)  # Identity only; no new event fetch.
        self.assertEqual(self.create(capacity=9).status_code, 409)
        self.assertEqual(AttendanceGroup.objects.count(), 1)
        self.assertEqual(CreationReceipt.objects.count(), 1)

    def test_my_request_history_is_scoped_to_applicant(self):
        group_id = self.group(mode='approval_required')
        self.assertEqual(self.action(group_id, 'request').status_code, 200)
        guest = self.call('/api/groups/mine/', actor='guest', method='get').json()
        self.assertEqual(guest['requests'][0]['status'], 'pending')
        self.assertEqual(guest['requests'][0]['group_id'], group_id)
        self.assertEqual(self.call('/api/groups/mine/', actor='owner', method='get').json()['requests'], [])
        self.assertEqual(self.call('/api/groups/mine/', actor='other', method='get').json()['requests'], [])

    def test_missing_key_invalid_fields_and_forged_identity(self):
        for payload in ({}, {'event_id': '10'}, {'event_id': True}, {'event_id': -1}):
            self.assertEqual(self.call('/api/groups/', payload, key='k').status_code, 400)
        self.assertEqual(self.create(key=None).status_code, 400)
        payload = {'event_id': 10, 'owner_id': 999, 'name': 'Forged', 'capacity': 3,
                   'description': 'Music', 'joining_mode': 'public'}
        self.assertEqual(self.call('/api/groups/', payload, key='k').status_code, 400)
        self.assertEqual(AttendanceGroup.objects.count(), 0)

    def test_public_reads_and_health_survive_discovery_outage(self):
        group_id = self.group()
        self.transport_error = URLError('offline')
        self.assertEqual(self.client.get('/health').status_code, 200)
        self.assertEqual(self.client.get(f'/api/groups/{group_id}/').status_code, 200)
        self.assertEqual(len(self.client.get('/api/events/10/groups/').json()['groups']), 1)
        self.assertEqual(self.action(group_id, 'join').status_code, 503)
        self.assertEqual(Membership.objects.count(), 1)
        self.assertFalse(apps.is_installed('discovery'))
        self.assertFalse(apps.is_installed('accounts'))
        self.assertNotIn('password', {f.name for f in Person._meta.fields})

    def test_status_mapping_and_no_membership_after_failure(self):
        group_id = self.group()
        for status, expected in ((404, 404), (500, 503), (503, 503), (302, 503)):
            self.event_status = status
            self.assertEqual(self.action(group_id, 'join').status_code, expected)
        self.event_status = 200
        self.event['cancelled'] = True
        self.assertEqual(self.action(group_id, 'join').status_code, 409)
        self.event['cancelled'] = False
        self.event['starts_at'] = (timezone.now()-timedelta(days=1)).isoformat()
        self.assertEqual(self.action(group_id, 'join').status_code, 409)
        self.assertEqual(Membership.objects.count(), 1)

    def test_credentials_and_fresh_privileges_each_request(self):
        self.assertEqual(self.call('/api/groups/mine/', actor=None, method='get').status_code, 401)
        self.assertEqual(self.call('/api/groups/mine/', actor='invalid', method='get').status_code, 401)
        for status, expected in ((401, 401), (403, 403), (500, 503), (404, 503)):
            self.identity_status = status
            self.assertEqual(self.call('/api/groups/mine/', method='get').status_code, expected)
        self.identity_status = 200
        group_id = self.group()
        self.assertEqual(self.call(f'/api/groups/{group_id}/edit/', {'name': 'Admin edit'}, 'admin', method='put').status_code, 200)
        self.identities['admin']['permissions'] = []
        self.assertEqual(self.call(f'/api/groups/{group_id}/edit/', {'name': 'Denied'}, 'admin', method='put').status_code, 403)
        self.assertEqual(permissions.get(), {})
        self.identities['owner']['active'] = False
        self.assertEqual(self.call('/api/groups/mine/', method='get').status_code, 403)

    def test_malformed_peer_responses_and_timeout(self):
        for raw in (b'bad json', b'[]', b'{}', b'x'*65537):
            self.raw_response = raw
            self.assertEqual(self.call('/api/groups/mine/', method='get').status_code, 503)
        self.raw_response = None
        self.transport_error = TimeoutError()
        self.assertEqual(self.call('/api/groups/mine/', method='get').status_code, 503)
        self.transport_error = None
        group_id = self.group()
        for changed in ({'id': 999}, {'cancelled': 'false'}, {'starts_at': '2026-01-01T12:00:00'}, {'starts_at': 'bad'}):
            original = self.event.copy()
            self.event.update(changed)
            self.assertEqual(self.action(group_id, 'join').status_code, 503)
            self.event = original

    def test_join_idempotence_capacity_and_database_uniqueness(self):
        group_id = self.group(capacity=2)
        for _ in range(2):
            self.assertEqual(self.action(group_id, 'join').status_code, 200)
        self.assertEqual(self.action(group_id, 'join', actor='other').status_code, 400)
        self.assertEqual(Membership.objects.filter(group_id=group_id).count(), 2)
        # A database constraint also prevents the same account joining another group at that event.
        person = Person.objects.get(pk=2)
        group = AttendanceGroup.objects.get(pk=group_id)
        second = AttendanceGroup.objects.create(owner=person, event_id=10, event_title='Music',
            event_starts_at=group.event_starts_at, name='Second', description='Music', capacity=4, joining_mode='public')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Membership.objects.create(user=person, group=second)

    def test_private_request_owner_review_autojoins_and_inboxes(self):
        group_id = self.group(mode='approval_required')
        self.assertEqual(self.action(group_id, 'join').status_code, 400)
        for _ in range(2):
            self.assertEqual(self.action(group_id, 'request').status_code, 200)
        record = JoinRequest.objects.get()
        self.assertEqual(self.call(f'/api/groups/{group_id}/requests/', actor='guest', method='get').status_code, 403)
        self.assertEqual(self.call(f'/api/requests/{record.pk}/review/', {'approve': True}).status_code, 200)
        record.refresh_from_db()
        self.assertEqual(record.status, 'accepted')
        self.assertTrue(Membership.objects.filter(group_id=group_id, user_id=2).exists())
        inbox = self.call('/api/notifications/', actor='guest', method='get').json()['notifications']
        self.assertEqual(len(inbox), 1)
        self.assertEqual(self.call(f"/api/notifications/{inbox[0]['id']}/read/", actor='other').status_code, 404)
        self.assertEqual(self.call(f"/api/notifications/{inbox[0]['id']}/read/", actor='guest').status_code, 200)

    def test_private_offer_switch_confirmation_is_atomic(self):
        public = self.group(actor='guest')
        private = self.group(mode='approval_required')
        self.assertEqual(self.action(private, 'request').status_code, 200)
        record = JoinRequest.objects.get()
        self.assertEqual(self.call(f'/api/requests/{record.pk}/review/', {'approve': True}).status_code, 200)
        record.refresh_from_db()
        self.assertEqual(record.status, 'approved')
        path = f'/api/requests/{record.pk}/accept/'
        self.assertEqual(self.call(path, actor='guest').status_code, 400)
        self.assertTrue(Membership.objects.filter(group_id=public, user_id=2).exists())
        self.assertEqual(self.call(path, {'confirm_switch': True}, 'guest').status_code, 200)
        self.assertFalse(AttendanceGroup.objects.filter(pk=public).exists())
        self.assertTrue(Membership.objects.filter(group_id=private, user_id=2).exists())

    def test_public_switch_owner_transfer_leave_and_chat_privacy(self):
        first = self.group()
        second = self.group(actor='other')
        self.assertEqual(self.action(first, 'join').status_code, 200)
        self.assertEqual(self.action(second, 'join').status_code, 400)
        self.assertEqual(self.action(second, 'join', confirm_switch=True).status_code, 200)
        self.assertEqual(self.action(first, 'join').status_code, 400)
        self.assertEqual(self.action(first, 'join', confirm_switch=True).status_code, 200)
        self.assertEqual(self.action(first, 'leave', actor='owner').status_code, 200)
        self.assertEqual(AttendanceGroup.objects.get(pk=first).owner_id, 2)
        self.assertEqual(self.call(f'/api/groups/{first}/chat/', actor='owner', method='get').status_code, 403)
        self.assertEqual(self.call(f'/api/groups/{first}/chat/', actor='guest', method='get').status_code, 200)
        self.assertEqual(self.action(first, 'leave').status_code, 200)
        self.assertEqual(self.client.get(f'/api/groups/{first}/').status_code, 404)

    def test_chat_edit_delete_signature_and_moderation(self):
        group_id = self.group()
        self.assertEqual(self.action(group_id, 'join').status_code, 200)
        path = f'/api/groups/{group_id}/chat/'
        before = self.call(path, method='get').json()['signature']
        post = f'/api/groups/{group_id}/messages/'
        message_id = self.call(post, {'body': 'Hello'}).json()['id']
        self.assertNotEqual(before, self.call(path, method='get').json()['signature'])
        message = f'/api/messages/{message_id}/'
        self.assertEqual(self.call(message, {'body': 'Bad edit'}, 'guest', method='put').status_code, 403)
        self.assertEqual(self.call(message, {'body': 'Edited'}, method='put').status_code, 200)
        self.assertEqual(self.call(message, actor='other', method='delete').status_code, 403)
        self.assertEqual(self.call(message, actor='admin', method='delete').status_code, 200)
        self.assertEqual(self.call(message, {'body': 'Restore'}, method='put').status_code, 400)
        self.assertEqual(self.call(post, {'body': ' '}).status_code, 400)
        self.assertEqual(self.call(post, {'body': 'x'*4001}).status_code, 400)

    def test_ban_lift_removal_and_owner_protection(self):
        group_id = self.group()
        self.assertEqual(self.action(group_id, 'join').status_code, 200)
        remove = f'/api/groups/{group_id}/members/2/remove/'
        self.assertEqual(self.call(remove, {'ban': True, 'reason': 'Abuse'}).status_code, 200)
        self.assertEqual(self.action(group_id, 'join').status_code, 403)
        ban = GroupBan.objects.get()
        listing = f'/api/groups/{group_id}/bans/'
        self.assertEqual(self.call(listing, actor='guest', method='get').status_code, 403)
        listed = self.call(listing, method='get').json()['bans']
        self.assertEqual([(b['id'], b['user_id'], b['reason']) for b in listed], [(ban.pk, 2, 'Abuse')])
        self.assertEqual(self.call(f'/api/bans/{ban.pk}/lift/', actor='guest').status_code, 403)
        self.assertEqual(self.call(f'/api/bans/{ban.pk}/lift/').status_code, 200)
        self.assertEqual(self.call(listing, method='get').json()['bans'], [])
        self.assertEqual(self.action(group_id, 'join').status_code, 200)
        self.assertEqual(self.call(remove).status_code, 200)
        self.assertEqual(self.call(f'/api/groups/{group_id}/members/1/remove/', {'ban': True}).status_code, 400)

    def test_edit_capacity_and_request_reject_cancel(self):
        group_id = self.group(mode='approval_required')
        self.assertEqual(self.action(group_id, 'request').status_code, 200)
        record = JoinRequest.objects.get()
        self.assertEqual(self.call(f'/api/requests/{record.pk}/review/', {'approve': False}).status_code, 200)
        self.assertEqual(self.action(group_id, 'request').status_code, 200)
        pending = JoinRequest.objects.get(status='pending')
        self.assertEqual(self.call(f'/api/requests/{pending.pk}/cancel/', actor='guest').status_code, 200)
        self.assertEqual(self.call(f'/api/groups/{group_id}/edit/', {'capacity': 0}, method='put').status_code, 400)
        self.assertEqual(self.call(f'/api/groups/{group_id}/edit/', {'event_id': 99}, method='put').status_code, 400)
        self.assertEqual(self.call(f'/api/groups/{group_id}/edit/', {'name': 'Renamed'}, method='put').status_code, 200)

    def test_no_stale_event_context_and_no_http_inside_atomic(self):
        group_id = self.group()
        with self.assertRaises(ContextError):
            services.join_group(actor=Person.objects.get(pk=2) if Person.objects.filter(pk=2).exists() else Person(pk=2), group_id=group_id)
        from groups.discovery_client import event
        with transaction.atomic(), self.assertRaises(ContextError):
            event(10)
        from groups.transactions import domain_transaction
        with transaction.atomic(), self.assertRaises(ContextError), domain_transaction():
            pass

    def test_concurrent_identical_create_returns_one_group_and_same_response(self):
        barrier = Barrier(2)
        original_peer = self.peer

        def synchronized_peer(request, timeout):
            response = original_peer(request, timeout)
            if '/api/events/' in request.full_url:
                barrier.wait(timeout=10)
            return response

        self.opener.open.side_effect = synchronized_peer
        payload = {'event_id': 10, 'name': 'Concurrent', 'description': 'Music',
                   'capacity': 4, 'joining_mode': 'public'}

        def create():
            try:
                response = Client().post('/api/groups/', json.dumps(payload), content_type='application/json',
                    HTTP_AUTHORIZATION='Bearer owner', HTTP_IDEMPOTENCY_KEY='race')
                return response.status_code, response.json()
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: create(), range(2)))
        self.assertEqual([status for status, _ in responses], [201, 201])
        self.assertEqual(responses[0][1], responses[1][1])
        self.assertEqual((AttendanceGroup.objects.count(), Membership.objects.count(), CreationReceipt.objects.count()), (1, 1, 1))

    def test_integrity_failure_recovers_receipt_only_after_rollback(self):
        group_id = self.group()
        existing = CreationReceipt.objects.get()
        with patch('config.api.receipt', side_effect=[None, None, existing]), patch(
                'config.api.services.save_group', side_effect=IntegrityError('concurrent write')):
            response = self.create()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['id'], group_id)
        self.assertFalse(connection.in_atomic_block)
        with patch('config.api.receipt', return_value=None), patch(
                'config.api.services.save_group', side_effect=IntegrityError('membership conflict')):
            self.assertEqual(self.create(key='different-key').status_code, 409)
        self.assertEqual(AttendanceGroup.objects.count(), 1)

    @override_settings(UI_ORIGIN='https://ui.example', VERSION='test-sha')
    def test_health_own_db_and_cors(self):
        with self.assertLogs('requests', level='INFO'):
            response = self.client.get('/health', HTTP_ORIGIN='https://ui.example')
        self.assertEqual(response.json(), {'status': 'ok', 'db': 'ok', 'version': 'test-sha'})
        self.assertEqual(response['Access-Control-Allow-Origin'], 'https://ui.example')
        self.assertNotIn('Access-Control-Allow-Origin', self.client.get('/health', HTTP_ORIGIN='https://wrong.example'))
        response = self.client.options('/api/groups/', HTTP_ORIGIN='https://ui.example')
        self.assertIn('Idempotency-Key', response['Access-Control-Allow-Headers'])
        with patch('config.api.HealthProbe.objects.get_or_create', side_effect=OperationalError('offline')):
            self.assertEqual(self.client.get('/health').status_code, 503)

    def test_delete_group_requires_admin_and_no_password_authority(self):
        group_id = self.group()
        path = f'/api/groups/{group_id}/delete/'
        self.assertEqual(self.call(path, method='delete').status_code, 403)
        self.assertEqual(self.call(path, actor='admin', method='delete').status_code, 200)
        self.assertEqual(self.client.get(f'/api/groups/{group_id}/photo/').status_code, 404)
