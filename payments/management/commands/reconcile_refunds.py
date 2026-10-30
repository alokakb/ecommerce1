from datetime import timedelta
import logging
from django.core.management import BaseCommand
from django.utils import timezone
from payments.models import Refund, Payment
from payments.services.refund_reconciliation import RefundReconciliationService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Reconcile refunds"

    def handle(self, *args, **options):
        cutoff_time = timezone.now() - timedelta(minutes=5)

        # refund logic including both with refund_id and without refund_id and
        # join with payment & order table to prevent N+1 query problem
        refund_set = Refund.objects.filter(payment__provider='razorpay', payment__status='captured',
                                           status__in =['created', 'processing'], updated_at__lte=cutoff_time).select_related('payment','payment__order')

        service = RefundReconciliationService()
        for refund in refund_set.iterator():
            try:
                if refund.gateway_refund_id:
                    result = service.refund_reconcile_with_id(refund)
                else:
                    result = service.refund_reconcile_without_id(refund)

                self.stdout.write(f"refund_gateway_payment_id : {refund.payment.gateway_payment_id}  "
                                  f"refund_gateway_refund_id : {refund.gateway_refund_id}  "
                                  f"{result['status']}")
            except Exception:
                logger.exception('Unexpected reconciliation error for gateway_refund_id : %s'
                                 'gateway_payment_id : %s',
                                 refund.gateway_refund_id, refund.payment.gateway_payment_id)
                self.stderr.write(f"Reconciliation failed unexpectedly for local refund "
                                  f"{refund.pk}; continuing with remaining refunds.")
                continue



