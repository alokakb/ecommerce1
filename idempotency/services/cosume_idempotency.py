from django.utils import timezone

from idempotency.models import IdempotencyRecord


def consume_idempotency_record(user, idempotency_record, order):
    # -------------------------------------------------
    # 10. Mark IK as completed and associate it with
    #     the newly created order.
    #
    # Everything is inside the same transaction.
    # If anything fails, the order + stock changes +
    # idempotency record all roll back together.
    # -------------------------------------------------
    # idempotency_record = IdempotencyRecord.objects.get(user=user, idempotency_key=idempotency_key)
    idempotency_record.status = "completed"
    idempotency_record.order = order
    idempotency_record.completed_at = timezone.now()

    idempotency_record.save(
        update_fields=[
            "status",
            "order",
            "completed_at",
        ]
    )