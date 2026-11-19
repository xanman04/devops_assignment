"""HTTP adapters authenticate before touching domain operations."""
import hashlib
import json
from functools import wraps

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_GET, require_http_methods

from groups import discovery_client, services
from groups.transactions import domain_transaction
from groups.context import Conflict, ContextError, NotFound, Unauthorized, Unavailable, permissions, validated_event
from groups.models import AttendanceGroup, CreationReceipt, JoinRequest, Person
from notifications import services as notices
from notifications.models import HealthProbe


def endpoint(*, authenticated=True):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            token = permissions.set({})
            try:
                request.actor = None
                if authenticated:
                    identity = discovery_client.identity(request.headers.get("Authorization", ""))
                    request.actor, _ = Person.objects.get_or_create(pk=identity["id"],
                        defaults={"display_name": identity["display_name"]})
                    if request.actor.display_name != identity["display_name"]:
                        request.actor.display_name = identity["display_name"]
                        request.actor.save(update_fields=["display_name"])
                    permissions.set(identity)
                return view(request, *args, **kwargs)
            except Unauthorized:
                return JsonResponse({"error": "Invalid or expired credential."}, status=401)
            except PermissionDenied:
                return JsonResponse({"error": "Permission denied."}, status=403)
            except (ObjectDoesNotExist, NotFound):
                return JsonResponse({"error": "Record not found."}, status=404)
            except Conflict as error:
                return JsonResponse({"error": str(error)}, status=409)
            except ContextError:
                return JsonResponse({"error": "Internal request validation error."}, status=500)
            except IntegrityError:
                return JsonResponse({"error": "Operation conflicts with existing group state."}, status=409)
            except Unavailable:
                return JsonResponse({"error": "Discovery unavailable; try again later."}, status=503)
            except ValidationError as error:
                return JsonResponse({"error": " ".join(error.messages)}, status=400)
            except (ValueError, TypeError, KeyError):
                return JsonResponse({"error": "Invalid request or group operation."}, status=400)
            except DatabaseError:
                return JsonResponse({"error": "Groups database unavailable."}, status=503)
            finally:
                permissions.reset(token)
        return wrapped
    return decorate


def body(request):
    if request.content_type != "application/json":
        raise ValueError()
    data = json.loads(request.body)
    if not isinstance(data, dict):
        raise ValueError()
    return data


def group_json(group):
    return {"id": group.pk, "event_id": group.event_id, "event_title": group.event_title,
        "event_starts_at": group.event_starts_at.isoformat(), "owner_id": group.owner_id,
        "name": group.name, "description": group.description, "capacity": group.capacity,
        "joining_mode": group.joining_mode, "member_count": group.memberships.count()}


def group_input(data, *, creating=False):
    allowed = {"name", "description", "capacity", "joining_mode"}
    if creating:
        allowed.add("event_id")
        if set(data) != allowed:
            raise ValueError()
    if set(data) - allowed:
        raise ValueError()
    for field in ("event_id", "capacity"):
        if field in data and (type(data[field]) is not int or data[field] <= 0):
            raise ValueError()
    for field in ("name", "description", "joining_mode"):
        if field in data and not isinstance(data[field], str):
            raise ValueError()
    return data


def receipt(actor, key, fingerprint):
    record = CreationReceipt.objects.filter(user=actor, key=key).first()
    if record is not None and record.fingerprint != fingerprint:
        raise Conflict("Idempotency key already used with a different payload.")
    return record


@require_GET
def health(request):
    try:
        with transaction.atomic():
            probe, _ = HealthProbe.objects.get_or_create(pk=1)
            probe.value = (probe.value + 1) % 1000000
            probe.save(update_fields=["value"])
            HealthProbe.objects.get(pk=1)
    except DatabaseError:
        return JsonResponse({"status": "unavailable", "db": "unavailable", "version": settings.VERSION}, status=503)
    return JsonResponse({"status": "ok", "db": "ok", "version": settings.VERSION})


@require_GET
@endpoint(authenticated=False)
def public_groups(request, event_id):
    return JsonResponse({"groups": [group_json(g) for g in services.visible_groups(event_id=event_id)]})


@require_GET
@endpoint(authenticated=False)
def detail(request, group_id):
    return JsonResponse(group_json(services.get_group(group_id=group_id)))


@require_GET
@endpoint()
def mine(request):
    groups = AttendanceGroup.objects.filter(memberships__user=request.actor).order_by("id")
    return JsonResponse({"groups": [group_json(g) for g in groups],
        "requests": [{"id": r.pk, "group_id": r.group_id, "group_name": r.group.name,
                      "event_id": r.group.event_id, "status": r.status}
                     for r in JoinRequest.objects.filter(applicant=request.actor).select_related("group").order_by("-id")[:200]]})


@require_http_methods(["POST"])
@endpoint()
def create(request):
    data = group_input(body(request), creating=True)
    key = request.headers.get("Idempotency-Key", "")
    if not key or len(key) > 120 or type(data.get("event_id")) is not int or data["event_id"] <= 0:
        raise ValueError()
    fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    previous = receipt(request.actor, key, fingerprint)
    if previous:
        return JsonResponse(previous.response, status=201)
    event = discovery_client.event(data["event_id"])
    try:
        with validated_event(event), domain_transaction():
            previous = receipt(request.actor, key, fingerprint)
            if previous:
                return JsonResponse(previous.response, status=201)
            group = services.save_group(actor=request.actor, data=data)
            response = group_json(group)
            CreationReceipt.objects.create(user=request.actor, key=key, fingerprint=fingerprint, group=group, response=response)
    except IntegrityError:
        # Re-read only after the failed transaction has rolled back.
        previous = receipt(request.actor, key, fingerprint)
        if previous:
            return JsonResponse(previous.response, status=201)
        raise Conflict("Concurrent group operation conflicts with existing membership.") from None
    return JsonResponse(response, status=201)


@require_http_methods(["PUT"])
@endpoint()
def edit(request, group_id):
    return JsonResponse(group_json(services.save_group(actor=request.actor, group_id=group_id, data=group_input(body(request)))))


@require_http_methods(["POST"])
@endpoint()
def group_action(request, group_id, action):
    data = body(request)
    if set(data) - {"confirm_switch"} or ("confirm_switch" in data and type(data["confirm_switch"]) is not bool):
        raise ValueError()
    if action == "leave":
        services.leave_group(actor=request.actor, group_id=group_id)
    else:
        group = AttendanceGroup.objects.get(pk=group_id)
        event = discovery_client.event(group.event_id)
        with validated_event(event):
            if action == "join":
                services.join_group(actor=request.actor, group_id=group_id, confirm_switch=data.get("confirm_switch", False))
            else:
                services.request_join(actor=request.actor, group_id=group_id)
    return JsonResponse({"status": "ok"})


@require_GET
@endpoint()
def requests(request, group_id):
    group = AttendanceGroup.objects.get(pk=group_id)
    services._manager(request.actor, group)
    return JsonResponse({"requests": list(group.join_requests.values("id", "applicant_id", "status", "requested_at"))})


@require_http_methods(["POST"])
@endpoint()
def request_action(request, request_id, action):
    data = body(request)
    allowed = {"approve"} if action == "review" else {"confirm_switch"} if action == "accept" else set()
    if set(data) - allowed or any(type(value) is not bool for value in data.values()):
        raise ValueError()
    if action == "cancel":
        services.cancel_request(actor=request.actor, request_id=request_id)
    else:
        record = JoinRequest.objects.select_related("group").get(pk=request_id)
        event = discovery_client.event(record.group.event_id)
        with validated_event(event):
            if action == "accept":
                services.accept_offer(actor=request.actor, request_id=request_id, confirm_switch=data.get("confirm_switch", False))
            else:
                if set(data) != {"approve"}:
                    raise ValueError()
                services.review_request(actor=request.actor, request_id=request_id, approve=data["approve"])
    return JsonResponse({"status": "ok"})


@require_http_methods(["POST"])
@endpoint()
def remove(request, group_id, user_id):
    data = body(request)
    if set(data) - {"ban", "reason"}:
        raise ValueError()
    services.remove_member(actor=request.actor, group_id=group_id, user_id=user_id,
        ban=data.get("ban", False), reason=data.get("reason", ""))
    return JsonResponse({"status": "ok"})


@require_http_methods(["POST"])
@endpoint()
def lift_ban(request, ban_id):
    services.lift_ban(actor=request.actor, ban_id=ban_id)
    return JsonResponse({"status": "ok"})


@require_GET
@endpoint()
def chat(request, group_id):
    messages = services.messages(actor=request.actor, group_id=group_id)
    group = AttendanceGroup.objects.get(pk=group_id)
    return JsonResponse({"signature": services.chat_signature(actor=request.actor, group_id=group_id),
        "messages": list(messages.values("id", "author_id", "body", "created_at", "edited_at", "deleted_at")),
        "members": list(group.memberships.values("user_id", "user__display_name", "joined_at")),
        "notices": [{"id": n.pk, "text": n.text, "created_at": n.created_at} for n in group.notices.select_related("subject")]})


@require_http_methods(["POST"])
@endpoint()
def post_message(request, group_id):
    data = body(request)
    if set(data) != {"body"}:
        raise ValueError()
    message = services.post_message(actor=request.actor, group_id=group_id, body=data["body"])
    return JsonResponse({"id": message.pk}, status=201)


@require_http_methods(["PUT", "DELETE"])
@endpoint()
def message(request, message_id):
    if request.method == "DELETE":
        services.delete_message(actor=request.actor, message_id=message_id)
    else:
        data = body(request)
        if set(data) != {"body"}:
            raise ValueError()
        services.edit_message(actor=request.actor, message_id=message_id, body=data["body"])
    return JsonResponse({"status": "ok"})


@require_GET
@endpoint()
def inbox(request):
    return JsonResponse({"notifications": list(notices.inbox(actor=request.actor).values(
        "id", "kind", "summary", "created_at", "read_at"))})


@require_http_methods(["POST"])
@endpoint()
def read_notice(request, notice_id):
    notices.mark_read(actor=request.actor, notification_id=notice_id)
    return JsonResponse({"status": "ok"})


@require_http_methods(["DELETE"])
@endpoint()
def delete_group(request, group_id):
    services.delete_group(actor=request.actor, group_id=group_id)
    return JsonResponse({"status": "ok"})


@require_GET
@endpoint(authenticated=False)
def photo(request, group_id):
    try:
        return FileResponse(services.open_photo(group_id=group_id), content_type="image/jpeg")
    except FileNotFoundError:
        raise NotFound() from None
