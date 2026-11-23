"""Public static-client projections. Visibility stays in Discovery's domain layer."""
from pathlib import PurePosixPath

from django.db.models import Q
from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_GET

from discovery import services
from discovery.models import DJProfile, Event, GenreCategory
from .api import endpoint


def reference_json(reference):
    return {"title": reference.title, "url": reference.url, "kind": reference.kind,
            "artist_credit": getattr(reference, "artist_credit", "")}


def asset_path(value):
    # Only bundled artwork paths are public; uploaded files use a visibility-checked route.
    path = PurePosixPath(value)
    return str(path) if value and not path.is_absolute() and ".." not in path.parts else ""


def artist_json(artist):
    return {"id": artist.pk, "name": artist.name, "description": artist.description,
            "photo": asset_path(artist.photo), "photo_credit": artist.photo_credit,
            "photo_source_url": artist.photo_source_url, "photo_license": artist.photo_license,
            "origin": artist.origin, "active_since": artist.active_since, "labels": artist.labels,
            "official_url": artist.official_url,
            "category_ids": [c.pk for c in artist.categories.all()]}


def event_json(event):
    return {"id": event.pk, "title": event.title, "description": event.description,
            "starts_at": event.starts_at, "ends_at": event.ends_at,
            "cancelled": event.cancelled_at is not None, "ticket_url": event.ticket_url,
            "has_poster": bool(event.poster), "demo_poster": asset_path(event.demo_poster),
            "venue": {"id": event.venue_id, "name": event.venue.name,
                      "address": event.venue.address, "timezone": event.venue.timezone,
                      "latitude": float(event.venue.latitude), "longitude": float(event.venue.longitude)},
            "categories": list(event.categories.values("id", "slug", "name", "color")),
            "tags": list(event.tags.values("id", "name")),
            "performers": [{"id": a.pk, "name": a.name} for a in event.performers.all()],
            "tempo": services.tempo_display(event)}


@require_GET
@endpoint
def browse(request):
    categories = request.GET.getlist("category")
    events = services.search_events(category_ids=categories, unbounded=True).prefetch_related("performers")
    query = request.GET.get("q", "").strip()[:200]
    if query:
        events = events.filter(Q(title__icontains=query) | Q(description__icontains=query)
            | Q(venue__name__icontains=query) | Q(categories__name__icontains=query)
            | Q(tags__name__icontains=query) | Q(performers__name__icontains=query)).distinct()
    return JsonResponse({"events": [event_json(e) for e in events[:200]], "limit": 200})


@require_GET
@endpoint
def detail(request, event_id):
    event = services.get_event(event_id=event_id)
    result = event_json(event)
    result["samples"] = [reference_json(r) for r in services.event_sound_samples(event)]
    result["references"] = [reference_json(r) for r in event.listening_references.all()]
    return JsonResponse(result)


@require_GET
@endpoint
def poster(request, event_id):
    try:
        return FileResponse(services.open_poster(event_id=event_id), content_type="image/jpeg")
    except FileNotFoundError:
        raise Event.DoesNotExist from None


@require_GET
@endpoint
def artists(request):
    return JsonResponse({"artists": [artist_json(a) for a in DJProfile.objects.prefetch_related("categories")]})


@require_GET
@endpoint
def artist(request, artist_id):
    person = DJProfile.objects.get(pk=artist_id)
    result = artist_json(person)
    result["links"] = list(person.social_links.values("platform", "url"))
    result["recordings"] = [reference_json(r) for r in person.media_links.all()]
    events = services.search_events(unbounded=True).filter(performers=person)
    result["events"] = [event_json(e) for e in events[:100]]
    return JsonResponse(result)


@require_GET
@endpoint
def genre(request, genre_id):
    return genre_response(GenreCategory.objects.get(pk=genre_id))


@require_GET
@endpoint
def genre_by_slug(request, genre_slug):
    return genre_response(GenreCategory.objects.get(slug=genre_slug))


def genre_response(category):
    references = category.listening_references.prefetch_related("tags")
    return JsonResponse({"id": category.pk, "slug": category.slug, "name": category.name, "description": category.description,
        "color": category.color, "tempo": category.bpm_display,
        "tags": list(category.tags.values("id", "name", "description", "bpm_min", "bpm_max")),
        "samples": [{**reference_json(r), "tag_ids": [t.pk for t in r.tags.all()]} for r in references],
        "artists": [artist_json(a) for a in category.djs.all()]})
