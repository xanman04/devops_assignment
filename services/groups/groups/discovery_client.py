"""Bounded HTTP boundary. Never imports Discovery code or opens its database."""
import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.utils.dateparse import parse_datetime

from .context import ContextError, NotFound, Unauthorized, Unavailable


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise Unavailable("Unexpected Discovery redirect.")


def request_json(path, credential=None, *, identity=False):
    if connection.in_atomic_block:
        raise ContextError("Peer calls cannot run inside a Groups transaction.")
    headers = {"Accept": "application/json"}
    if credential:
        headers["Authorization"] = credential
    request = Request(settings.DISCOVERY_URL + path, headers=headers)
    try:
        with build_opener(NoRedirect()).open(request, timeout=settings.DISCOVERY_TIMEOUT_S) as response:
            if response.status != 200:
                raise Unavailable("Discovery unavailable.")
            raw = response.read(65537)
            if len(raw) > 65536:
                raise Unavailable("Invalid Discovery response.")
            data = json.loads(raw)
    except HTTPError as error:
        if identity and error.code == 401:
            raise Unauthorized() from None
        if identity and error.code == 403:
            raise PermissionDenied() from None
        if not identity and error.code == 404:
            raise NotFound() from None
        raise Unavailable("Discovery unavailable.") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise Unavailable("Discovery unavailable or returned invalid JSON.") from None
    if not isinstance(data, dict):
        raise Unavailable("Invalid Discovery response.")
    return data


def identity(authorization):
    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() != "bearer" or not credential:
        raise Unauthorized()
    data = request_json("/api/auth/identity/", authorization, identity=True)
    if (type(data.get("id")) is not int or data["id"] <= 0
            or not isinstance(data.get("display_name"), str) or not data["display_name"]
            or len(data["display_name"]) > 150 or type(data.get("active")) is not bool
            or not isinstance(data.get("permissions"), list)
            or any(not isinstance(p, str) for p in data["permissions"])):
        raise Unavailable("Invalid Discovery identity.")
    if not data["active"]:
        raise PermissionDenied()
    return data


def event(event_id):
    data = request_json(f"/api/events/{event_id}/")
    if (type(data.get("id")) is not int or data["id"] != event_id
            or not isinstance(data.get("title"), str) or len(data["title"]) > 200
            or type(data.get("cancelled")) is not bool
            or not isinstance(data.get("starts_at"), str)):
        raise Unavailable("Invalid Discovery event.")
    try:
        start = parse_datetime(data["starts_at"])
        if start is None or start.utcoffset() is None:
            raise ValueError()
    except (ValueError, TypeError, OverflowError):
        raise Unavailable("Invalid Discovery event time.") from None
    return {"id": data["id"], "title": data["title"], "cancelled": data["cancelled"], "starts_at": start}
