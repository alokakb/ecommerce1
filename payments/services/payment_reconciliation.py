from django.conf import settings
from django.db import transaction

from payments.models import Payment
import razorpay
import logging

from payments.services.process_payment import process_successful_payment, process_failed_payment

logger = logging.getLogger(__name__)


class PaymentReconciliationService:

    def reconcile_payment(self, payment: Payment):

        # Initialize Razorpay Client.
        client = razorpay.Client(
            auth=(
                settings.RAZORPAY_KEY,
                settings.RAZORPAY_SECRET
            )
        )
        response = client.order.payments(
            payment.gateway_order_id
        )
        gateway_payment_resp = response.get("items", [])
        if not gateway_payment_resp:
            logger.info("Razorpay could not find any payment against this order gateway_order_id : %s ", payment.gateway_order_id)
            return {
                "status": "no action",
                "gateway_order_id": payment.gateway_order_id,
            }

        gateway_payments = gateway_payment_resp[0]
        resp_gateway_order_id = gateway_payments.get('order_id')
        resp_gateway_amount = gateway_payments.get('amount')
        resp_gateway_currency = gateway_payments.get('currency')
        resp_gateway_status = gateway_payments.get('status')

        # Validate the important fields
        validation_error = None
        if resp_gateway_order_id != payment.gateway_order_id:
            validation_error = (
                f"gateway_order_id mismatch: "
                f"local={payment.gateway_order_id}, "
                f"gateway={resp_gateway_order_id}"
            )

        if resp_gateway_amount != payment.amount*100:
            validation_error = (
                f"amount mismatch: "
                f"local={payment.amount * 100}, "
                f"gateway={resp_gateway_amount}"
            )

        if resp_gateway_currency != payment.currency:
            validation_error = (
                f"currency mismatch: "
                f"local={payment.currency}, "
                f"gateway={resp_gateway_currency}"
            )

        if validation_error:
            logger.error(
                "Payment reconciliation validation failed for "
                "gateway_order_id=%s: %s",
                payment.gateway_order_id,
                validation_error,
            )
            return {
                "status": "failed",
                "gateway_order_id": payment.gateway_order_id,
            }

        # fetch status & repair
        with transaction.atomic():
            try:
                payment = Payment.objects.select_for_update().get(pk=payment.pk)
                if payment.status == 'unpaid' and resp_gateway_status == 'captured':
                    process_successful_payment(payment.order, payment)
                elif payment.status == 'unpaid' and resp_gateway_status == 'failed':
                    process_failed_payment(payment.order, payment)
                elif payment.status == 'unpaid' and resp_gateway_status == 'created':
                    logger.info(
                        'No reconciliation action for gateway_order_id=%s. '
                        'Razorpay payment is still in created state.',
                        payment.gateway_order_id,
                    )
                    return {
                        'status': 'no action',
                        'gateway_order_id': payment.gateway_order_id,
                    }
                elif payment.status == 'captured' and resp_gateway_status == 'captured':
                    logger.info('No Inconsistency in gateway_order_id : %s Already paid',
                                payment.gateway_order_id)
                    return {
                        'status': 'no action',
                        "gateway_order_id": payment.gateway_order_id,
                    }
                else:
                    logger.warning(
                        'Unexpected payment state for gateway_order_id=%s: '
                        'local_status=%s, gateway_status=%s',
                        payment.gateway_order_id,
                        payment.status,
                        resp_gateway_status,
                    )
                    return {
                        'status': 'investigate',
                        'gateway_order_id': payment.gateway_order_id,
                    }
                return {
                    "status": "reconciled",
                    "gateway_order_id": payment.gateway_order_id,
                }
            except Exception:
                transaction.set_rollback(True)
                logger.exception('Payment reconciliation failed for gateway_order_id : %s ', payment.gateway_order_id)
                return {
                    "status": "failed",
                    "gateway_order_id": payment.gateway_order_id
                }








