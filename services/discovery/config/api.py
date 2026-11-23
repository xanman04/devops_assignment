"""JSON adapters reuse Discovery's existing authorization and domain rules."""
import json
from functools import wraps
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_http_methods
from discovery import services
from discovery.models import Event, GenreCategory, GenreTag, Venue
from notifications.models import HealthProbe
from notifications import services as notices
from .authentication import InvalidCredential, identity, issue_token
from .throttle import limited


def endpoint(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except InvalidCredential:
            return JsonResponse({"error": "Invalid or expired credential."}, status=401)
        except PermissionDenied:
            return JsonResponse({"error": "Permission denied."}, status=403)
        except ObjectDoesNotExist:
            return JsonResponse({"error": "Record not found."}, status=404)
        except (ValidationError, ValueError, TypeError, KeyError) as error:
            messages = error.messages if isinstance(error, ValidationError) else ["Invalid request."]
            return JsonResponse({"errors": messages}, status=400)
        except DatabaseError:
            return JsonResponse({"error": "Database unavailable."}, status=503)
    return wrapped


def body(request):
    if request.content_type != "application/json":
        raise ValueError("JSON required.")
    value = json.loads(request.body)
    if not isinstance(value, dict):
        raise ValueError("Object required.")
    return value


def event_json(event):
    return {"id": event.pk, "title": event.title, "description": event.description,
        "starts_at": event.starts_at.isoformat(), "ends_at": event.ends_at.isoformat(),
        "cancelled": event.cancelled_at is not None,
        "venue": {"id": event.venue_id, "name": event.venue.name, "timezone": event.venue.timezone},
        "category_ids": list(event.categories.values_list("pk", flat=True)),
        "tag_ids": list(event.tags.values_list("pk", flat=True))}


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


@require_http_methods(["POST"])
@endpoint
def token(request):
    data = body(request)
    if set(data) != {'username', 'password'} or not isinstance(data['username'], str) or not isinstance(data['password'], str):
        raise ValueError()
    if len(data['username']) > 150 or len(data['password']) > 4096:
        raise ValueError()
    blocked = limited(request, 'login', data['username'])
    if blocked is not None:
        return blocked
    return JsonResponse({"token": issue_token(data["username"], data["password"]),
                         "expires_in": settings.TOKEN_TTL_S})


@require_GET
@endpoint
def whoami(request):
    user, _ = identity(request)
    # Group authorization is explicitly scoped, not the entire permission list.
    permissions = ["groups.*"] if user.is_superuser else sorted(
        permission for permission in user.get_all_permissions() if permission.startswith("groups."))
    return JsonResponse({"id": user.pk, "display_name": user.public_name,
                         "active": user.is_active, "permissions": permissions})


@require_http_methods(["POST"])
@endpoint
def logout(request):
    _, session = identity(request)
    session.flush()
    return JsonResponse({"status": "ok"})


@require_GET
@endpoint
def categories(request):
    return JsonResponse({"categories": list(GenreCategory.objects.values(
        "id", "slug", "name", "color", "description", "bpm_min", "bpm_max")),
        "tags": list(GenreTag.objects.values("id", "name", "category_id", "description", "bpm_min", "bpm_max"))})


@require_GET
@endpoint
def venues(request):
    return JsonResponse({"venues": list(Venue.objects.filter(review_status="approved").values(
        "id", "name", "address", "latitude", "longitude", "timezone")[:1000])})


@require_http_methods(["GET", "POST"])
@endpoint
def events(request):
    if request.method == "GET":
        return JsonResponse({"events": [event_json(event) for event in services.search_events()[:1000]]})
    return save_event(request)


def save_event(request, event_id=None):
    user, _ = identity(request)
    data = body(request)
    fields = data["event"]
    if not isinstance(fields, dict):
        raise ValueError()
    fields = fields.copy()
    fields["venue"] = Venue.objects.get(pk=fields["venue_id"])
    del fields["venue_id"]
    for name in ("starts_at", "ends_at"):
        fields[name] = parse_datetime(fields[name])
        if fields[name] is None:
            raise ValueError()
    event = services.save_event(actor=user, event_id=event_id, data=fields,
        category_ids=data["category_ids"], tag_ids=data.get("tag_ids", []))
    return JsonResponse(event_json(event), status=200 if event_id else 201)


@require_http_methods(["PUT"])
@endpoint
def edit_event(request, event_id):
    return save_event(request, event_id)


@require_http_methods(["POST"])
@endpoint
def follow(request, event_id):
    user, _ = identity(request)
    services.follow_event(actor=user, event_id=event_id)
    return JsonResponse({"status": "ok"})


@require_http_methods(["POST"])
@endpoint
def unfollow(request, event_id):
    user, _ = identity(request)
    services.unfollow_event(actor=user, event_id=event_id)
    return JsonResponse({"status": "ok"})


@require_GET
@endpoint
def inbox(request):
    user, _ = identity(request)
    return JsonResponse({"notifications": list(notices.inbox(actor=user).values(
        "id", "kind", "summary", "created_at", "read_at")[:1000])})
