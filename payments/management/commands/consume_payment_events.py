import json
import logging
import uuid
from django.db import IntegrityError, transaction

from notifications.services.notification_service import NotificationService
from payments.models import ProcessedEvent

from confluent_kafka import Consumer, KafkaException
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVER = "localhost:9092"
KAFKA_TOPIC = "payment-events"
KAFKA_GROUP_ID = "payment-event-consumer"

class Command(BaseCommand):
    help = "Consume payment events from Kafka."

    def handle(self, *args, **options):
        consumer = Consumer({
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVER,
            "group.id": KAFKA_GROUP_ID,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        })
        try:
            consumer.subscribe([KAFKA_TOPIC])
            self.stdout.write(
                self.style.SUCCESS("payment event consumer started")
            )

            while True:
                message = consumer.poll(timeout=1.0)

                if message is None:
                    continue

                if message.error():
                    raise KafkaException(message.error())

                self.stdout.write(
                    f"Topic={message.topic()}, "
                    f"Partition={message.partition()}, "
                    f"Message offset={message.offset()}"
                )

                try:
                    event = json.loads(message.value().decode("utf-8"))
                    logger.info('message from kafka : %s', event)
                    self.stdout.write(
                        f"Received event {event.get('event_type')} "
                        f"(event_id = {event.get('event_id')})"
                    )

                    # add database processing and offset commits next
                    event_id = event.get("event_id")
                    event_type = event.get("event_type")

                    if not event_id or event_type != "PaymentCaptured":
                        raise CommandError(
                            f"Unsupported or invalid event: {event_type!r}"
                        )

                    try:
                        self.stdout.write(f"Raw event_id: {event_id!r}, type: {type(event_id)}")
                        event_id = uuid.UUID(event_id)
                    except (ValueError, TypeError, AttributeError) as exc:
                        logger.error("Skipping malformed event_id: %r", event_id)
                        continue
                        raise CommandError(
                            f"Invalid event id: {event_id!r}"
                        ) from exc


                    try:
                        with transaction.atomic():
                            ProcessedEvent.objects.create(
                                event_id=event_id,
                                event_type=event_type,
                            )
                            NotificationService.add_notification(event)

                        self.stdout.write(
                            self.style.SUCCESS(f"Recorded processed event: {event_id}")
                        )

                    except IntegrityError:
                        if ProcessedEvent.objects.filter(event_id=event_id).exists():
                            logger.warning("Duplicate event encountered: %s", event_id)
                            self.stdout.write(f"Duplicate event skipped: {event_id}")
                        else:
                            logger.exception(
                                "Database integrity error while processing event %s",
                                event_id,
                            )
                            raise

                    # Commit only after successful processing or confirmed duplicate
                    result = consumer.commit(message=message, asynchronous=False)

                    for topic_partition in result:
                        if topic_partition.error is not None:
                            raise KafkaException(topic_partition.error)

                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Committed offset {topic_partition.offset} "
                                f"for partition {topic_partition.partition}"
                            )
                        )

                except (UnicodeDecodeError, json.JSONDecodeError) as exec:
                    logger.exception("Invalid event message")
                    raise CommandError(
                        "Received an invalid json or UTF-8 event"
                    ) from exec

        except KeyboardInterrupt:
            self.stdout.write("Stopping payment event consumer...")

        finally:
            consumer.close()
