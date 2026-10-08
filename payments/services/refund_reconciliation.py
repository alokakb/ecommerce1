from decimal import Decimal

from django.conf import settings
from django.db import transaction

from orders.models import Refund
import razorpay
import logging

from payments.services.process_refund import process_failed_refund, process_successful_refund

logger = logging.getLogger(__name__)


class RefundReconciliationService:

    def refund_reconcile_without_id(self, refund : Refund):
        if refund.gateway_refund_id:
            pass

        # initialize razorpay client
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY, settings.RAZORPAY_SECRET)
        )
        response = client.payment.fetch_multiple_refund(
            refund.payment.gateway_payment_id,
            {}
        )
        gateway_refunds = response.get("items", [])
        if not gateway_refunds:
            process_failed_refund(refund.payment.order, refund)
            return {
                "status": "reconciled",
                "gateway_payment_id": refund.payment.gateway_payment_id,
            }

        internal_refunds_dict = set()
        for internal_refund in refund.payment.refunds.all():
            if internal_refund.gateway_refund_id:
                internal_refunds_dict.add(internal_refund.gateway_refund_id)

        for gateway_refund in gateway_refunds:
            print(
                gateway_refund["id"],
                gateway_refund["status"],
                gateway_refund["amount"],
                gateway_refund["payment_id"],
            )
            resp_refund_id = gateway_refund.get("id")
            resp_status = gateway_refund.get("status")
            resp_amount = gateway_refund.get("amount")
            resp_currency = gateway_refund.get("currency")
            resp_payment_id = gateway_refund.get("payment_id")

            with transaction.atomic():
                try:
                    if resp_refund_id not in internal_refunds_dict:
                        refund = Refund.objects.select_for_update().get(pk=refund.pk)
                        refund.amount = resp_amount / Decimal(100)
                        refund.currency = resp_currency
                        refund.gateway_refund_id = resp_refund_id
                        if resp_status == "processed":
                            process_successful_refund(refund.payment.order, refund)
                        elif resp_status == "failed":
                            process_failed_refund(refund.payment.order, refund)
                        elif resp_status == "created":
                            refund.status = "processing"
                            refund.save(update_fields=["status", "gateway_refund_id", "amount", "currency"])
                            logger.info(
                                'No reconciliation action for gateway_payment_id=%s. '
                                'Razorpay refund is still processing.',
                                refund.payment.gateway_payment_id,
                            )
                            return {
                                'status': 'no action',
                                'gateway_payment_id': refund.payment.gateway_payment_id,
                            }
                        else:
                            logger.warning(
                                'Unexpected refund state for gateway_payment_id=%s: '
                                'gateway_status=%s',
                                refund.payment.gateway_payment_id,
                                resp_status,
                            )
                            return {
                                'status': 'investigate',
                                'gateway_payment_id': refund.payment.gateway_payment_id,
                            }
                        refund.save(update_fields=["gateway_refund_id", "amount", "currency"])
                        return {
                            "status": "reconciled",
                            "gateway_payment_id": refund.payment.gateway_payment_id,
                        }
                except Exception:
                    transaction.set_rollback(True)
                    logger.exception('Refund reconciliation failed for gateway_payment_id : %s ',
                                     refund.payment.gateway_payment_id)
                    return {
                        "status": "failed",
                        "gateway_payment_id": refund.payment.gateway_payment_id
                    }
        process_failed_refund(refund.payment.order, refund)
        return {
            "status": "reconciled",
            "gateway_payment_id": refund.payment.gateway_payment_id,
        }


    def refund_reconcile_with_id(self, refund: Refund):

        if not refund.gateway_refund_id:
            raise ValueError("refund_reconcile_with_id called without gateway_refund_id")

        # initialize razorpay client
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY, settings.RAZORPAY_SECRET)
        )
        gateway_refund = client.refund.fetch(
            refund.gateway_refund_id
        )
        if not gateway_refund:
            logger.info(
                'could not find refund in the received response from razorpay payment_id=%s refund_id=%s. ',
                refund.payment.gateway_payment_id,
                refund.gateway_refund_id,)
            return {
                "status": "Investigate",
                "gateway_payment_id": refund.payment.gateway_payment_id,
                "gateway_refund_id": refund.gateway_refund_id
            }
        resp_refund_id = gateway_refund.get("id")
        resp_status = gateway_refund.get("status")
        resp_amount = gateway_refund.get("amount")
        resp_currency = gateway_refund.get("currency")
        resp_payment_id = gateway_refund.get("payment_id")

        # Validate the important fields
        validation_error = None
        if resp_refund_id != refund.gateway_refund_id:
            validation_error = (
                f"gateway_refund_id mismatch: "
                f"local={refund.gateway_refund_id}, "
                f"gateway={resp_refund_id}"
            )
        if resp_payment_id != refund.payment.gateway_payment_id:
            validation_error = (
                f"gateway_payment_id mismatch: "
                f"local={refund.payment.gateway_payment_id}, "
                f"gateway={resp_payment_id}"
            )
        if validation_error:
            logger.error(
                "Refund reconciliation validation failed for "
                "gateway_payment_id=%s: %s",
                refund.payment.gateway_payment_id,
                validation_error,
            )
            return {
                "status": "failed",
                "gateway_payment_id": refund.payment.gateway_payment_id,
                "gateway_refund_id": refund.gateway_refund_id
            }

        with transaction.atomic():
            try:
                refund = Refund.objects.select_for_update().get(pk=refund.pk)
                refund.amount = resp_amount / Decimal(100)
                refund.currency = resp_currency
                if resp_status == "processed":
                    process_successful_refund(refund.payment.order, refund)
                elif resp_status == "failed":
                    process_failed_refund(refund.payment.order, refund)
                elif resp_status == "created" and refund.status not in ["success", "failed"]:
                    refund.status = "processing"
                    refund.save(update_fields=["status", "amount", "currency"])
                    logger.info(
                        'No reconciliation action for gateway_refund_id=%s gateway_payment_id=%s. '
                        'Razorpay refund is still processing.',
                        refund.gateway_refund_id,
                        refund.payment.gateway_payment_id,
                    )
                    return {
                        'status': 'no action',
                        'gateway_payment_id': refund.payment.gateway_payment_id,
                        "gateway_refund_id": refund.gateway_refund_id
                    }
                else:
                    logger.warning(
                        'Unexpected refund state for gateway_refund_id=%s gateway_payment_id=%s: '
                        'gateway_status=%s',
                        refund.gateway_refund_id,
                        refund.payment.gateway_payment_id,
                        resp_status,
                    )
                    return {
                        'status': 'investigate',
                        'gateway_payment_id': refund.payment.gateway_payment_id,
                        "gateway_refund_id": refund.gateway_refund_id
                    }
                refund.save(update_fields=["amount", "currency"])
                return {
                    "status": "reconciled",
                    "gateway_payment_id": refund.payment.gateway_payment_id,
                    "gateway_refund_id": refund.gateway_refund_id,
                }
            except Exception:
                transaction.set_rollback(True)
                logger.exception('Refund reconciliation failed for gateway_refund_id=%s gateway_payment_id : %s ',
                                 refund.gateway_refund_id,
                                 refund.payment.gateway_payment_id)
                return {
                    "status": "failed",
                    "gateway_payment_id": refund.payment.gateway_payment_id,
                    "gateway_refund_id": refund.gateway_refund_id
                }









