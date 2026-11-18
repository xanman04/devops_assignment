"""Groups-owned notification records and database probe."""
from django.conf import settings
from django.db import models
from django.db.models import Q


class Notification(models.Model):
    class Kind(models.TextChoices):
        GROUP_OFFER = "group_offer", "Group offer"
        GROUP_REQUEST = "group_request", "New group request"
        GROUP_REJECTED = "group_rejected", "Group request rejected"
        MEMBER_REMOVED = "member_removed", "Removed from group"
        MEMBER_BANNED = "member_banned", "Banned from group"
        OWNER_TRANSFER = "owner_transfer", "Group ownership transferred"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="notifications")
    kind = models.CharField(max_length=14, choices=Kind)
    join_request = models.ForeignKey("groups.JoinRequest", on_delete=models.CASCADE, null=True, blank=True)
    group = models.ForeignKey("groups.AttendanceGroup", on_delete=models.CASCADE, null=True, blank=True)
    summary = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=(
                Q(kind__in=["group_offer", "group_request", "group_rejected"], join_request__isnull=False, group__isnull=True)
                | Q(kind__in=["member_removed", "member_banned", "owner_transfer"], join_request__isnull=True, group__isnull=False)),
                name="notification_group_source"),
            models.UniqueConstraint(fields=["recipient", "join_request"], condition=Q(join_request__isnull=False), name="notification_offer_once"),
        ]


class HealthProbe(models.Model):
    value = models.PositiveIntegerField(default=0)


class DataImport(models.Model):
    fingerprint = models.CharField(max_length=64, unique=True)
    imported_at = models.DateTimeField(auto_now_add=True)
