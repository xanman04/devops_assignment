"""Request-scoped validated peer facts; never persistent permissions."""
from contextlib import contextmanager
from contextvars import ContextVar

from django.core.exceptions import PermissionDenied
from django.utils import timezone

permissions = ContextVar("validated_identity", default={})
events = ContextVar("validated_events", default={})


class Unavailable(Exception):
    pass


class ContextError(RuntimeError):
    pass


class Unauthorized(Exception):
    pass


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


def require_user(actor):
    if actor is None or not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("An active account is required.")


def can_manage(actor, permission):
    return actor is not None and actor.has_perm(permission)


def require_permission(actor, permission):
    require_user(actor)
    if not can_manage(actor, permission):
        raise PermissionDenied("Permission denied.")


def require_event(event_id):
    event = events.get().get(event_id)
    if event is None:
        raise ContextError("Event must be validated for this request before a transaction.")
    if event["cancelled"] or timezone.now() >= event["starts_at"]:
        raise Conflict("New group participation is closed for this event.")
    return event


@contextmanager
def validated_event(event):
    token = events.set({event["id"]: event})
    try:
        yield
    finally:
        events.reset(token)
