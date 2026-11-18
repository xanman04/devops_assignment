"""Serialize short local writes; peer HTTP must finish before entering here."""
from functools import wraps
from contextlib import contextmanager
from contextvars import ContextVar
from django.db import connection, transaction, OperationalError
from .context import ContextError

_domain_scope = ContextVar('groups_domain_transaction', default=False)


def acquire_domain_lock():
    if not connection.in_atomic_block:
        raise RuntimeError('Groups write lock requires a transaction.')
    if connection.vendor == 'microsoft':
        with connection.cursor() as cursor:
            cursor.execute("""
                DECLARE @result int;
                EXEC @result = sys.sp_getapplock @Resource = %s,
                    @LockMode = 'Exclusive', @LockOwner = 'Transaction', @LockTimeout = 10000;
                SELECT @result;
            """, ['bassline-groups-write'])
            if cursor.fetchone()[0] < 0:
                raise OperationalError('Groups write lock timed out.')
    # SQLite uses BEGIN IMMEDIATE, configured in its connection options.


def domain_write(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with domain_transaction():
            return function(*args, **kwargs)
    return wrapped


@contextmanager
def domain_transaction():
    if connection.in_atomic_block and not _domain_scope.get():
        raise ContextError('Enter the domain transaction before reading mutable group state.')
    with transaction.atomic():
        if not _domain_scope.get():
            acquire_domain_lock()
        token = _domain_scope.set(True)
        try:
            yield
        finally:
            _domain_scope.reset(token)
