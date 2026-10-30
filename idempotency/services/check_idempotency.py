from rest_framework import status
from rest_framework.response import Response

from idempotency.models import IdempotencyRecord



def check_idempotent_request(user, idempotency_key):
    # -------------------------------------------------
    # 4. Check whether THIS exact request was already
    # processed.
    #
    # Same IK = same logical checkout operation.
    # -------------------------------------------------
    try:
        idempotency_record = (
            IdempotencyRecord.objects
            .select_for_update()
            .get(
                user=user,
                idempotency_key=idempotency_key
            )
        )

        # Same request was already completed.
        # Return the previously created order.
        if idempotency_record.status == "completed":
            order = idempotency_record.order

            return Response(
                {
                    "message": "Checkout request already processed.",
                    "order_id": order.id,
                    "order_no": order.order_no,
                    "total_amount": order.total_amount,
                },
                status=status.HTTP_200_OK
            )

        # Another request with the same IK is currently
        # being processed.
        return Response(
            {"error": "This checkout request is already being processed."},
            status=status.HTTP_409_CONFLICT
        )

    except IdempotencyRecord.DoesNotExist:

        # First time we have seen this IK.
        return IdempotencyRecord.objects.create(
            user=user,
            idempotency_key=idempotency_key,
            status="processing",
        )

