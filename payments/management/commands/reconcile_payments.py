from datetime import timedelta

from django.core.management import BaseCommand
from django.utils import timezone

from orders.models import Payment
from payments.services.payment_reconciliation import PaymentReconciliationService


class Command(BaseCommand):
    help = 'Reconcile pending razorpay payments'

    def handle(self, *args, **options):
        cutoff_time = timezone.now() - timedelta(minutes=5)

        payment_set = Payment.objects.filter(
            provider='razorpay',
            status='unpaid',
            gateway_order_id__isnull=False,
            updated_at__lte=cutoff_time
        )

        service = PaymentReconciliationService()

        for payment in payment_set.iterator():
            result = service.reconcile_payment(payment)

            self.stdout.write( f"Payment order_id {payment.gateway_order_id}: "
                f"{result['status']}")