"""Opaque, expiring bearer credentials backed by Discovery's own session table."""
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.core.exceptions import PermissionDenied
from django.utils.crypto import constant_time_compare


class InvalidCredential(Exception):
    pass


def issue_token(username, password):
    user = authenticate(username=username, password=password)
    if user is None:
        raise InvalidCredential()
    session = SessionStore()
    session["user_id"] = user.pk
    session["auth_hash"] = user.get_session_auth_hash()
    session.set_expiry(settings.TOKEN_TTL_S)
    session.create()
    return session.session_key


def identity(request):
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise InvalidCredential()
    session = SessionStore(session_key=token)
    user_id = session.get("user_id")
    if user_id is None:
        raise InvalidCredential()
    try:
        user = get_user_model().objects.get(pk=user_id)
    except get_user_model().DoesNotExist:
        raise InvalidCredential() from None
    if not user.is_active:
        raise PermissionDenied("Account inactive.")
    if not constant_time_compare(session.get("auth_hash", ""), user.get_session_auth_hash()):
        raise InvalidCredential()
    return user, session
