from django.core.management import BaseCommand
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
import logging

from orders.models import Order
from payments.models import Payment
from payments.services.process_payment import (check_actual_gateway_status,
                                               process_successful_payment)
from orders.services.process_checkout import process_abandoned_order
from payments.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "safely handles order cancellations and salvages delayed gateway success"
    def handle(self, *args, **options):
        expiration_time = timezone.now() - timedelta(minutes=3)


        expired_orders = Order.objects.prefetch_related('payments').filter(
            order_status='pending',
            created_at__lt=expiration_time
        ).exclude(payments__status='captured')

        if not expired_orders.exists():
            self.stdout.write(self.style.SUCCESS("No stale pending orders Found"))
            return

        for order in expired_orders:
            try:
                # Reconciliation protection : Double-check the state from source
                latest_payment = Payment.objects.filter(order=order).order_by('-updated_at', '-id').first()

                if latest_payment is None:
                    logger.error('No payment record for order %s', order.order_no)
                    continue

                real_gateway_state = check_actual_gateway_status(order, latest_payment)

                if real_gateway_state == 'undetermined':
                    self.stdout.write(self.style.ERROR(
                        f"Order {order.order_no} status is undetermined. Need investigation"))
                    continue  # Safe skip before determining the actual status

                with transaction.atomic():
                    order = Order.objects.select_for_update().get(pk=order.pk)
                    latest_payment = Payment.objects.select_for_update().get(pk=latest_payment.pk)

                    # Re-check because webhook could have modified
                    # the order/payment while gateway call was running.
                    if order.order_status != "pending":
                        continue

                    if latest_payment.status == "captured":
                        continue

                    if real_gateway_state == 'success':
                        # Crash Salvage : The user paid but our servers missed -> process that order
                        process_successful_payment(order, latest_payment)
                        self.stdout.write(self.style.SUCCESS(
                            f"Order {order.order_no} Salvaged! Webhook was missed, but cron completed it"))
                        continue   # Safe skip

                    elif real_gateway_state in ['false', 'pending']:
                        process_abandoned_order(order, latest_payment)
                        self.stdout.write(self.style.WARNING(
                            f"Order {order.order_no} moved to abandoned successfully. Stock returned to shelves."
                        ))

                    else:
                        # Defensive protection in case a new status is
                        # introduced without updating this command.
                        logger.error(
                            "Unknown gateway state %s for order %s",
                            real_gateway_state,
                            order.order_no,
                        )
                        continue
            except ConfigurationError:
                # This is a system/configuration problem.
                # Don't make a decision about this order.
                logger.error(
                    "Gateway configuration error for order %s",
                    order.order_no,
                )
                continue

            except Exception:
                # Defensive fallback
                logger.exception(
                    "Unexpected failure checking order %s",
                    order.order_no,
                )
                continue
