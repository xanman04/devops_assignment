"""Static account and event forms reuse the existing validation/domain rules."""
from zoneinfo import ZoneInfo
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.http import JsonResponse, QueryDict
from django.views.decorators.http import require_GET, require_http_methods
from accounts.forms import RegistrationForm, AccountSettingsForm
from discovery import services
from discovery.forms import EventForm
from discovery.models import Event
from notifications import services as notices
from .api import body, endpoint
from .authentication import identity
from .content_api import event_json
from .throttle import limited

PROFILE_FIELDS = {'display_name', 'bio', 'email', 'instagram_url', 'spotify_url', 'apple_music_url', 'soundcloud_url'}


def validated(form):
    if not form.is_valid():
        raise ValidationError([f'{field}: {message}' for field, messages in form.errors.items() for message in messages])
    return form.cleaned_data


def account_json(user):
    return {'id': user.pk, 'username': user.username, **{field: getattr(user, field) for field in sorted(PROFILE_FIELDS)}}


@require_http_methods(['POST'])
@endpoint
def register(request):
    blocked = limited(request, 'register')
    if blocked is not None:
        return blocked
    data = body(request)
    if set(data) - (PROFILE_FIELDS | {'username', 'password1', 'password2'}):
        raise ValueError()
    if any(not isinstance(data.get(field, ''), str) or len(data.get(field, '')) > limit
           for field, limit in (('username', 150), ('password1', 4096), ('password2', 4096))):
        raise ValueError()
    form = RegistrationForm(data)
    validated(form)
    try:
        user = form.save()
    except IntegrityError:
        raise ValidationError('This username is unavailable.') from None
    return JsonResponse({'id': user.pk}, status=201)


@require_http_methods(['GET', 'PUT'])
@endpoint
def account(request):
    user, _ = identity(request)
    if request.method == 'PUT':
        data = body(request)
        if set(data) != PROFILE_FIELDS:
            raise ValueError()
        form = AccountSettingsForm(data, instance=user)
        validated(form)
        user = form.save()
    return JsonResponse(account_json(user))


@require_GET
@endpoint
def my_events(request):
    user, _ = identity(request)
    owned = Event.objects.filter(creator=user).select_related('venue').order_by('-starts_at')[:200]
    followed = services.public_events().filter(follows__user=user).select_related('venue').order_by('-starts_at')[:200]
    return JsonResponse({'owned': [event_json(e) for e in owned], 'followed': [event_json(e) for e in followed]})


@require_http_methods(['GET', 'POST', 'PUT'])
@endpoint
def event_form(request, event_id=None):
    actor, _ = identity(request)
    event = services.get_event(event_id=event_id, actor=actor) if event_id else Event()
    if event_id and event.creator_id != actor.pk:
        raise PermissionDenied()
    if request.method == 'GET':
        form = EventForm(actor=actor, instance=event)
        initial = {}
        if event_id:
            zone = ZoneInfo(event.venue.timezone)
            initial = {'venue': event.venue_id, 'title': event.title, 'description': event.description,
                'ticket_url': event.ticket_url,
                'starts_at': event.starts_at.astimezone(zone).strftime('%Y-%m-%dT%H:%M'),
                'ends_at': event.ends_at.astimezone(zone).strftime('%Y-%m-%dT%H:%M'),
                'categories': list(event.categories.values_list('pk', flat=True)),
                'tags': list(event.tags.values_list('pk', flat=True)),
                'performers': list(event.performers.values_list('pk', flat=True))}
        return JsonResponse({'initial': initial, 'venues': list(form.fields['venue'].queryset.values('id', 'name', 'timezone'))})
    if (event_id is None) != (request.method == 'POST'):
        raise ValueError()
    data = body(request)
    if set(data) - {'venue', 'title', 'description', 'ticket_url', 'starts_at', 'ends_at', 'categories', 'tags', 'performers'}:
        raise ValueError()
    values = QueryDict('', mutable=True)
    for key, value in data.items():
        if key in {'categories', 'tags', 'performers'}:
            if not isinstance(value, list):
                raise ValueError()
            values.setlist(key, [str(item) for item in value])
        elif key in {'starts_at', 'ends_at'}:
            if not isinstance(value, str):
                raise ValueError()
            day, time = value.split('T')
            values[key+'_0'], values[key+'_1'] = day, time
        else:
            values[key] = str(value)
    form = EventForm(values, actor=actor, instance=event)
    clean = validated(form)
    event = services.save_event(actor=actor, event_id=event_id,
        data={key: clean[key] for key in ('venue', 'title', 'description', 'starts_at', 'ends_at', 'ticket_url')},
        category_ids=[c.pk for c in clean['categories']], tag_ids=[t.pk for t in clean['tags']],
        performer_ids=[a.pk for a in clean['performers']])
    return JsonResponse({'id': event.pk}, status=200 if event_id else 201)


@require_http_methods(['POST'])
@endpoint
def cancel_event(request, event_id):
    actor, _ = identity(request)
    event = services.get_event(event_id=event_id, actor=actor)
    if event.creator_id != actor.pk:
        raise PermissionDenied()
    services.save_event(actor=actor, event_id=event_id, data={},
        category_ids=list(event.categories.values_list('pk', flat=True)),
        tag_ids=list(event.tags.values_list('pk', flat=True)), cancelled=True)
    return JsonResponse({'status': 'ok'})


@require_http_methods(['POST'])
@endpoint
def propose_venue(request):
    actor, _ = identity(request)
    data = body(request)
    if set(data) != {'name', 'address', 'latitude', 'longitude', 'timezone'}:
        raise ValueError()
    venue = services.save_venue(actor=actor, data=data)
    return JsonResponse({'id': venue.pk, 'review_status': venue.review_status}, status=201)


@require_http_methods(['POST'])
@endpoint
def report(request, event_id):
    actor, _ = identity(request)
    data = body(request)
    if set(data) != {'reason', 'explanation'}:
        raise ValueError()
    services.report_event(actor=actor, event_id=event_id, **data)
    return JsonResponse({'status': 'ok'}, status=201)


@require_http_methods(['POST'])
@endpoint
def read_notice(request, notice_id):
    actor, _ = identity(request)
    notices.mark_read(actor=actor, notification_id=notice_id)
    return JsonResponse({'status': 'ok'})
