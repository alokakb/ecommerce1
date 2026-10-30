from datetime import timedelta

from django.core.management import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q, F
from django.utils import timezone

from notifications.models import Notification
from notifications.services.dispatcher import NotificationDispatcher
import logging

from payments.management.commands.publish_outbox_events import MAX_RETRY_DELAY_SECONDS

logger = logging.getLogger(__name__)


MAX_ATTEMPTS = 5
MAX_RETRY_DELAY_SECONDS = 3600


def calculate_delay(no_of_attempts):
    return min(MAX_RETRY_DELAY_SECONDS, 30* (2 ** no_of_attempts))


class Command(BaseCommand):
    help = 'Notification worker'

    def handle(self, *args, **options):
        now = timezone.now()
        notifications_to_process = Notification.objects.filter(
            Q(status="pending", next_attempt_at__isnull=True)
            | Q(status="pending", next_attempt_at__lte=now)
            | Q(status="failed", next_attempt_at__lte=now)
        ).order_by("created_at", "pk")

        for notification in notifications_to_process:
            try:
                with transaction.atomic():
                    notification = Notification.objects.select_for_update().get(pk=notification.pk)

                    # Another worker may have claimed or completed this job.
                    if notification.status not in ("pending", "failed"):
                        continue

                    # retry safeguard
                    now = timezone.now()
                    if (notification.next_attempt_at is not None
                            and notification.next_attempt_at > now):
                        continue

                    notification.status = "sending"
                    notification.attempts += 1
                    notification.updated_at = timezone.now()
                    notification.save(update_fields=["status", "attempts", "updated_at"])

                result = NotificationDispatcher().dispatch(notification)
                if result != 1:
                    raise RuntimeError(
                        f"Unexpected dispatch result: {result!r}"
                    )

                notification.status = "sent"
                notification.sent_at = timezone.now()
                notification.next_attempt_at = None
                notification.last_error = ""

                notification.save(
                    update_fields=[
                        "status",
                        "sent_at",
                        "next_attempt_at",
                        "last_error",
                        "updated_at",
                    ]
                )
                logger.info("Email sent to %s ", notification.recipient)
                self.stdout.write(f"Email sent to {notification.recipient}")
            except Exception as exc:
                logger.exception(
                    'unexpected error in dispatching notification event_id : %s, channel : %s',
                    notification.event_id,
                    notification.channel)
                notification.status = "failed"
                notification.last_error = str(exc)[:5000]
                if notification.attempts < MAX_ATTEMPTS:
                    delay = calculate_delay(notification.attempts)
                    notification.next_attempt_at = timezone.now() + timedelta(seconds=delay)
                else:
                    notification.status = "dead"
                    notification.next_attempt_at = None

                notification.updated_at = timezone.now()
                notification.save(update_fields=[
                    "status", "last_error", "next_attempt_at", "updated_at"])

                self.stderr.write(f'Unexpected error in dispatching notification '
                                  f'event_id : {notification.event_id}, channel : {notification.channel}'
                                  f'continuing with remaining notifications to process.')
                continue



