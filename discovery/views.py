# Copyright © 2026 Xander Chen. All rights reserved.
"""Read-only discovery JSON endpoints; page handlers live in discovery.pages."""
from datetime import datetime
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import Event
from .services import get_event, map_pins, search_events


@require_GET
def event_details(request, event_id):
    """Public event contract for the future Groups service and static UI.

    Always use public visibility, even when a privileged browser is signed in.
    Private creator/account fields never cross this boundary.
    """
    try:
        event = get_event(event_id=event_id)
    except Event.DoesNotExist:
        return JsonResponse({"error": "Event not found."}, status=404)
    return JsonResponse({
        "id": event.pk,
        "title": event.title,
        "starts_at": event.starts_at.isoformat(),
        "ends_at": event.ends_at.isoformat(),
        "cancelled": event.cancelled_at is not None,
        "venue": {"id": event.venue_id, "name": event.venue.name,
                  "timezone": event.venue.timezone},
    })


def _date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise ValidationError("Dates must be ISO datetimes including a timezone.")


def _csv(value):
    return value.split(",") if value else []


@require_GET
def map_events(request):
    try:
        events = search_events(
            starts_at=_date(request.GET.get("start")), ends_at=_date(request.GET.get("end")),
            category_ids=_csv(request.GET.get("categories")), tag_ids=_csv(request.GET.get("tags")),
            match=request.GET.get("match", "any"),
            bounds=_csv(request.GET["bounds"]) if "bounds" in request.GET else None,
        )
        results = list(events[:1001])
        if len(results) > 1000:
            return JsonResponse({"error": "Too many events; narrow the dates or map area."}, status=400)
        return JsonResponse({"venues": map_pins(results)})
    except ValidationError as error:
        return JsonResponse({"errors": error.messages}, status=400)
