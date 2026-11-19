"""Shared database counters bound public password hashing across worker threads."""
import hashlib
import hmac
import ipaddress
import unicodedata
from time import time
from django.conf import settings
from django.db.models import F
from django.http import JsonResponse
from accounts.models import AuthWindow


def limited(request, action, username=''):
    minute = int(time() // 60)
    AuthWindow.objects.filter(minute__lt=max(0, minute-10)).delete()
    source = request.META.get('REMOTE_ADDR', '')
    # Enable only behind ACA HTTP ingress, which appends the trusted rightmost
    # address. Direct local servers ignore the entire caller-controlled header.
    if settings.TRUST_CONTAINER_APPS_INGRESS:
        forwarded = request.headers.get('X-Forwarded-For', '').rsplit(',', 1)[-1].strip()
        try:
            source = str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    buckets = [(source, 50 if action == 'login' else 10)]
    if action == 'login':
        buckets.append(('username:'+unicodedata.normalize('NFKC', username).casefold(), 20))
    for value, limit in buckets:
        key = hmac.new(settings.SECRET_KEY.encode(), f'{action}:{minute}:{value}'.encode(), hashlib.sha256).hexdigest()
        AuthWindow.objects.get_or_create(key=key, defaults={'minute': minute})
        if not AuthWindow.objects.filter(key=key, attempts__lt=limit).update(attempts=F('attempts')+1):
            response = JsonResponse({'error': 'Too many attempts. Try again in one minute.'}, status=429)
            response['Retry-After'] = '60'
            return response
    return None
