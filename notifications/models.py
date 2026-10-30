from django.db import models

# Create your models here.

class Notification(models.Model):
    CHANNEL_CHOICES = [
        ("email", "Email"),
        ("whatsapp", "Whatsapp"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sending", "Sending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
        ("dead", "Dead")
    ]
    event_id = models.UUIDField()
    channel = models.CharField(max_length=20,choices=CHANNEL_CHOICES)
    status = models.CharField(max_length=20,choices=STATUS_CHOICES,default='pending')
    recipient = models.CharField(max_length=255, db_index=True)
    message = models.JSONField(default=dict)

    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event_id", "channel"],
                name="unique_notifications_per_event_channel",
            )
        ]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.channel} notification for {self.event_id}: {self.status}"