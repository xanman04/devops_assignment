"""JSON moderation adapters for venue and event report review."""
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods

from discovery import services
from discovery.models import EventReport, Venue
from .api import body, endpoint
from .authentication import identity


def capabilities(actor):
    return {
        "venues": actor.has_perm("discovery.change_venue"),
        "reports": actor.has_perm("discovery.change_eventreport"),
        "hide_events": actor.has_perm("discovery.hide_reported_event"),
    }


@require_GET
@endpoint
def queue(request):
    actor, _ = identity(request)
    allowed = capabilities(actor)
    if not allowed["venues"] and not allowed["reports"]:
        raise PermissionDenied()

    pending_venues = []
    if allowed["venues"]:
        pending_venues = list(Venue.objects.filter(
            review_status=Venue.ReviewStatus.PENDING
        ).order_by("created_at", "pk").values(
            "id", "name", "address", "latitude", "longitude", "timezone", "review_status"
        )[:200])

    pending_reports = []
    if allowed["reports"]:
        pending_reports = [
            {"id": report.pk, "event_id": report.event_id,
             "event_title": report.event.title, "reason": report.reason,
             "explanation": report.explanation, "status": report.status}
            for report in EventReport.objects.filter(
                status=EventReport.Status.PENDING
            ).select_related("event").order_by("created_at", "pk")[:200]
        ]

    return JsonResponse({"capabilities": allowed,
                         "pending_venues": pending_venues,
                         "pending_reports": pending_reports})


@require_http_methods(["POST"])
@endpoint
def review_venue(request, venue_id):
    actor, _ = identity(request)
    services.require_permission(actor, "discovery.change_venue")
    data = body(request)
    if set(data) != {"status", "review_note"}:
        raise ValueError()
    status, note = data["status"], data["review_note"]
    if status not in {Venue.ReviewStatus.APPROVED, Venue.ReviewStatus.REJECTED}:
        raise ValueError()
    if not isinstance(note, str) or len(note) > 2000:
        raise ValueError()
    venue = services.save_venue(actor=actor, data={}, venue_id=venue_id,
                                review_status=status, review_note=note)
    return JsonResponse({"id": venue.pk, "status": venue.review_status})


@require_http_methods(["POST"])
@endpoint
def review_report(request, report_id):
    actor, _ = identity(request)
    data = body(request)
    if set(data) != {"status", "resolution_note", "hide_event"}:
        raise ValueError()
    status, note, hide_event = data["status"], data["resolution_note"], data["hide_event"]
    if status not in {EventReport.Status.DISMISSED, EventReport.Status.ACTIONED}:
        raise ValueError()
    if not isinstance(note, str) or len(note) > 2000 or type(hide_event) is not bool:
        raise ValueError()
    report = services.review_report(actor=actor, report_id=report_id,
        status=status, resolution_note=note, hide_event=hide_event)
    return JsonResponse({"id": report.pk, "status": report.status})
