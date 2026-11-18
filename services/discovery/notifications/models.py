"""Discovery-owned event notifications, with no Groups relations."""
from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Kind(models.TextChoices):
        EVENT_CHANGE = "event_change", "Event change"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="notifications")
    kind = models.CharField(max_length=14, choices=Kind, default=Kind.EVENT_CHANGE)
    event_change = models.ForeignKey("discovery.EventChange", on_delete=models.PROTECT, related_name="notifications")
    summary = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(kind="event_change"), name="notification_event_kind"),
            models.UniqueConstraint(fields=["recipient", "event_change"], name="notification_event_once"),
        ]


class HealthProbe(models.Model):
    """One durable row allows health to prove an actual database write."""
    value = models.PositiveIntegerField(default=0)


class DataImport(models.Model):
    fingerprint = models.CharField(max_length=64, unique=True)
    imported_at = models.DateTimeField(auto_now_add=True)
