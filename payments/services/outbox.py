import uuid

from django.utils import timezone

from payments.models import Payment, OutboxEvent


def create_payment_captured_event(payment : Payment):
    event_id = uuid.uuid4()

    payload = {
        "event_id" : str(event_id),
        "event_type" : "PaymentCaptured",
        "event_version" : 1,
        "occurred_at" : timezone.now().isoformat(),
        "data" : {
            "payment_id" : payment.pk,
            "order_id" : payment.order.pk,
            "amount" : str(payment.amount),
            "currency" : payment.currency,
            "provider" : payment.provider,
            "gateway_payment_id" : payment.gateway_payment_id,
            "gateway_order_id" : payment.gateway_order_id,
        }
    }

    return OutboxEvent.objects.create(
        event_id = event_id,
        event_type = "PaymentCaptured",
        aggregate_id = str(payment.pk),
        payload = payload,
    )