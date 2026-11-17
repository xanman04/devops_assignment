# Copyright © 2026 Xander Chen. All rights reserved.
"""Group storage. Use groups.services for membership and authorization rules."""
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Q
from types import SimpleNamespace

from .context import permissions

USER = settings.AUTH_USER_MODEL


def group_photo_path(instance, filename):
    return f"groups/{uuid4().hex}{Path(filename).suffix.lower()}"


def validate_photo_size(value):
    if value.size > 5 * 1024 * 1024:
        raise ValidationError("Group photos must be at most 5 MiB.")


class AttendanceGroup(models.Model):
    class JoiningMode(models.TextChoices):
        PUBLIC = "public", "Public"
        APPROVAL = "approval_required", "Approval required"

    event_id = models.PositiveBigIntegerField(db_index=True)
    event_title = models.CharField(max_length=200)
    event_starts_at = models.DateTimeField()

    @property
    def event(self):
        return SimpleNamespace(pk=self.event_id, title=self.event_title, starts_at=self.event_starts_at)

    owner = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="owned_attendance_groups")
    name = models.CharField(max_length=120)
    description = models.TextField()
    capacity = models.PositiveIntegerField()
    joining_mode = models.CharField(max_length=17, choices=JoiningMode)
    photo = models.ImageField(upload_to=group_photo_path, blank=True, validators=[
        FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), validate_photo_size,
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(capacity__gt=0), name="group_positive_capacity"),
            models.CheckConstraint(condition=Q(joining_mode__in=["public", "approval_required"]), name="group_valid_joining_mode"),
        ]

    def __str__(self):
        return self.name


class Membership(models.Model):
    group = models.ForeignKey(AttendanceGroup, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="attendance_memberships")
    event_id = models.PositiveBigIntegerField()
    joined_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.event_id = self.group.event_id
        super().save(*args, **kwargs)


    class Meta:
        ordering = ["joined_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["group", "user"], name="membership_group_user_unique"),
            models.UniqueConstraint(fields=["event_id", "user"], name="membership_event_user_unique"),
        ]


class JoinRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved offer"
        REJECTED = "rejected", "Rejected"
        ACCEPTED = "accepted", "Accepted"
        CANCELLED = "cancelled", "Cancelled"

    group = models.ForeignKey(AttendanceGroup, on_delete=models.CASCADE, related_name="join_requests")
    applicant = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="join_requests")
    status = models.CharField(max_length=9, choices=Status, default=Status.PENDING, db_index=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, blank=True, related_name="reviewed_join_requests")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["group", "applicant"], condition=Q(status__in=["pending", "approved"]), name="request_one_unresolved"),
            models.CheckConstraint(condition=Q(status__in=["pending", "approved", "rejected", "accepted", "cancelled"]), name="request_valid_status"),
        ]


class GroupBan(models.Model):
    group = models.ForeignKey(AttendanceGroup, on_delete=models.CASCADE, related_name="bans")
    user = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="group_bans")
    issued_by = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="issued_group_bans")
    reason = models.TextField(blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    lifted_at = models.DateTimeField(null=True, blank=True)
    lifted_by = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, blank=True, related_name="lifted_group_bans")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["group", "user"], condition=Q(lifted_at__isnull=True), name="ban_one_active")]


class GroupNotice(models.Model):
    """A short grey line in the chat, like "Sam has left the group", kept in order with the messages."""

    class Kind(models.TextChoices):
        JOINED = "joined", "Joined the group"
        LEFT = "left", "Left the group"
        PROMOTED = "promoted", "Promoted to owner"

    group = models.ForeignKey(AttendanceGroup, on_delete=models.CASCADE, related_name="notices")
    kind = models.CharField(max_length=8, choices=Kind)
    subject = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="group_notices")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["group", "created_at"], name="notice_group_created_idx")]
        constraints = [models.CheckConstraint(condition=Q(kind__in=["joined", "left", "promoted"]), name="notice_valid_kind")]

    @property
    def text(self):
        name = self.subject.public_name
        if self.kind == self.Kind.JOINED:
            return f"{name} has joined the group"
        return f"{name} has left the group" if self.kind == self.Kind.LEFT else f"{name} was promoted to owner"


class Message(models.Model):
    group = models.ForeignKey(AttendanceGroup, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="group_messages")
    body = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, blank=True, related_name="deleted_group_messages")

    def clean(self):
        if self.deleted_at is None and not self.body.strip():
            raise ValidationError({"body": "A live message needs text."})

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["group", "created_at"], name="message_group_created_idx")]
        constraints = [models.CheckConstraint(
            condition=(Q(deleted_at__isnull=True, deleted_by__isnull=True) & ~Q(body="")) |
                      Q(deleted_at__isnull=False, deleted_by__isnull=False, body=""),
            name="message_live_or_tombstone",
        )]


class GroupHistory(models.Model):
    """One person's own record of group changes (created, joined, left, removed), kept after the group is gone."""

    class Kind(models.TextChoices):
        CREATED = "created", "Created a group"
        JOINED = "joined", "Joined a group"
        LEFT = "left", "Left a group"
        REMOVED = "removed", "Removed from a group"

    user = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="group_history")
    kind = models.CharField(max_length=8, choices=Kind)
    group = models.ForeignKey(AttendanceGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    group_name = models.CharField(max_length=120)
    event_title = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "-created_at"], name="grouphistory_user_idx")]
        constraints = [models.CheckConstraint(condition=Q(kind__in=["created", "joined", "left", "removed"]), name="grouphistory_valid_kind")]


class Person(models.Model):
    """Credential-free remote account reference. Privileges exist only in request context."""
    id = models.PositiveBigIntegerField(primary_key=True)
    display_name = models.CharField(max_length=150)

    @property
    def public_name(self):
        return self.display_name

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        # The current caller was validated by Discovery before obtaining this reference.
        # Historical target references are not a local account authority.
        return True

    def has_perm(self, permission):
        caller = permissions.get()
        return caller.get('id') == self.pk and (
            permission in caller.get('permissions', []) or 'groups.*' in caller.get('permissions', []))


class CreationReceipt(models.Model):
    user = models.ForeignKey(Person, on_delete=models.PROTECT)
    key = models.CharField(max_length=120)
    fingerprint = models.CharField(max_length=64)
    response = models.JSONField()
    group = models.ForeignKey(AttendanceGroup, on_delete=models.SET_NULL, null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'key'], name='create_receipt_user_key_unique')]
