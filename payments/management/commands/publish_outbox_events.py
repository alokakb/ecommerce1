
import json
import logging
import random
import time
from datetime import timedelta

from confluent_kafka import KafkaException, Producer
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from payments.models import OutboxEvent

logger = logging.getLogger(__name__)

KAFKA_TOPIC = "payment-events"
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
DELIVERY_TIMEOUT_SECONDS = 10
MAX_RETRY_DELAY_SECONDS = 300


class KafkaDeliveryError(Exception):
    """Raised when Kafka delivery fails or cannot be confirmed."""


class Command(BaseCommand):
    help = "Publish pending transactional outbox events to Kafka."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=50)
        parser.add_argument("--poll-interval", type=float, default=2.0)

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        poll_interval = options["poll_interval"]

        if batch_size < 1:
            raise CommandError("--batch-size must be positive.")

        if poll_interval <= 0:
            raise CommandError("--poll-interval must be positive.")

        producer = Producer(
            {
                "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
                "enable.idempotence": True,
            }
        )

        self.stdout.write(self.style.SUCCESS("Outbox publisher started."))

        try:
            while True:
                published = self.publish_batch(producer, batch_size)

                if published == 0:
                    time.sleep(poll_interval)
        except KeyboardInterrupt:
            self.stdout.write("Stopping publisher...")
        finally:
            remaining = producer.flush(DELIVERY_TIMEOUT_SECONDS)

            if remaining:
                self.stderr.write(
                    self.style.WARNING(
                        f"{remaining} Kafka message(s) remain undelivered."
                    )
                )

    def publish_batch(self, producer, batch_size):
        now = timezone.now()

        events = list(
            OutboxEvent.objects.filter(published_at__isnull=True)
            .filter(
                Q(next_attempt_at__isnull=True)
                | Q(next_attempt_at__lte=now)
            )
            .order_by("created_at", "pk")[:batch_size]
        )

        for event in events:
            self.publish_one(producer, event)

        return len(events)

    def publish_one(self, producer, event):
        delivery_result = {"error": None, "message": None}

        def on_delivery(err, msg):
            delivery_result["error"] = err
            delivery_result["message"] = msg

        try:
            producer.produce(
                topic=KAFKA_TOPIC,
                key=event.aggregate_id,
                value=json.dumps(event.payload),
                callback=on_delivery,
            )

            remaining = producer.flush(DELIVERY_TIMEOUT_SECONDS)

            if remaining:
                raise KafkaDeliveryError(
                    "Delivery timed out; Kafka acceptance is uncertain."
                )

            if delivery_result["error"] is not None:
                raise KafkaDeliveryError(
                    str(delivery_result["error"])
                )

            message = delivery_result["message"]

            if message is None:
                raise KafkaDeliveryError(
                    "No delivery result was received."
                )

            with transaction.atomic():
                locked_event = (
                    OutboxEvent.objects.select_for_update()
                    .get(pk=event.pk)
                )

                if locked_event.published_at is None:
                    locked_event.published_at = timezone.now()
                    locked_event.last_error = None
                    locked_event.next_attempt_at = None
                    locked_event.save(
                        update_fields=[
                            "published_at",
                            "last_error",
                            "next_attempt_at",
                        ]
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Published {event.event_id} to "
                    f"{message.topic()} partition={message.partition()} "
                    f"offset={message.offset()}"
                )
            )

        except (KafkaException, KafkaDeliveryError, BufferError, ValueError) as exc:
            self.record_failure(event.pk, exc)

        except Exception as exc:
            logger.exception(
                "Unexpected error publishing outbox event %s",
                event.event_id,
            )
            self.record_failure(event.pk, exc)

    def record_failure(self, event_pk, exc):
        logger.error("Outbox event %s failed: %s", event_pk, exc)

        with transaction.atomic():
            locked_event = (
                OutboxEvent.objects.select_for_update()
                .get(pk=event_pk)
            )

            # Another operation may already have marked it published.
            if locked_event.published_at is not None:
                return

            locked_event.attempts = F("attempts") + 1
            locked_event.last_error = str(exc)[:5000]

            # Use the updated attempt count to calculate backoff.
            locked_event.refresh_from_db(fields=["attempts"])
            delay_seconds = 2 + random.uniform(0, min(
                2 ** locked_event.attempts,
                MAX_RETRY_DELAY_SECONDS)
            )

            locked_event.next_attempt_at = (
                timezone.now() + timedelta(seconds=delay_seconds)
            )

            locked_event.save(
                update_fields=[
                    "attempts",
                    "last_error",
                    "next_attempt_at",
                ]
            )
