
import logging

from django.conf import settings
from django.db import IntegrityError, transaction

from orders.models import Order
from payments.models import Payment
from notifications.models import Notification

logger = logging.getLogger(__name__)


class NotificationService:
    @staticmethod
    def add_notification(event):
        event_id = event.get("event_id")
        data = event.get("data") or {}

        order_id = data.get("order_id")
        payment_id = data.get("payment_id")

        if not event_id or not order_id or not payment_id:
            raise ValueError(
                "PaymentCaptured event is missing required identifiers"
            )

        order = Order.objects.filter(pk=order_id).first()
        payment = Payment.objects.filter(
            pk=payment_id,
            order_id=order_id,
        ).first()

        if order is None:
            raise ValueError(f"Order {order_id} was not found")

        if payment is None:
            raise ValueError(
                f"Payment {payment_id} for order {order_id} was not found"
            )

        recipient_name = order.shipping_full_name
        recipient_email = order.user.email
        amount = payment.amount
        currency = payment.currency

        channels = settings.NOTIFICATION_CHANNELS

        for channel_name, config in channels.items():
            if not config.get("enabled", False):
                continue

            if channel_name == "email":
                if not recipient_email:
                    raise ValueError(
                        f"Order {order_id} has no customer email address"
                    )

                message_data = {
                    "subject": "Your order has been confirmed",
                    "body": (
                        f"Hi {recipient_name},\n\n"
                        f"Your payment of {currency} {amount} was successful.\n"
                        f"Your order {order.order_no} has been confirmed."
                    ),
                }

                try:
                    with transaction.atomic():
                        Notification.objects.create(
                            event_id=event_id,
                            channel=channel_name,
                            recipient=recipient_email,
                            message=message_data,
                            status="pending",
                        )
                except IntegrityError:
                    # Only treat this as a duplicate if the same
                    # event/channel notification already exists.
                    if Notification.objects.filter(
                        event_id=event_id,
                        channel=channel_name,
                    ).exists():
                        logger.info(
                            "Notification already exists for event %s "
                            "and channel %s",
                            event_id,
                            channel_name,
                        )
                        continue
                    raise

        return None
