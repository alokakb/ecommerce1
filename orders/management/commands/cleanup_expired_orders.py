from django.core.management import BaseCommand
from datetime import datetime, timedelta
from django.db import transaction
from django.utils import timezone
from django.db.models import F

from orders.models import Order
from products.models import ProductVariant
from payments.services.process_payment import check_actual_gateway_status, process_successful_payment


class Command(BaseCommand):
    help = "safely handles order cancellations and salvages delayed gateway success"
    def handle(self, *args, **options):
        expiration_time = timezone.now() - timedelta(minutes=15)

        with transaction.atomic():

            expired_orders = Order.objects.filter(
                order_status='pending',
                order__payments__in=['unpaid', 'failed'],
                created_at__lt=expiration_time
            ).select_related('order__payment')

            if not expired_orders.exists():
                self.stdout.write(self.style.SUCCESS("No stale pending orders Found"))
                return

            for order in expired_orders:
                # Reconciliation protection : Double-check the state from source
                real_gateway_state = check_actual_gateway_status(order)

                if real_gateway_state == 'success':
                    # Crash Salvage : The user paid but our servers missed -> process that order
                    process_successful_payment(order.order_no)
                    self.stdout.write(self.style.SUCCESS(
                        f"Order {order.order_no} Salvaged! Webhook was missed, but cron completed it"))
                    continue   # Safe skip

                # Ghost checkout case -> Genuine abandonment confirmed
                # Release the reserved stocks back to the inventory
                for item in order.items.all():
                    ProductVariant.objects.filter(id=item.variant_id).update(
                        stock_quantity=F('stock_quantity') + item.quantity_ordered,
                    )

                # Lock down final terminal states
                order.order_status = 'abandoned'
                order.save()

                self.stdout.write(self.style.WARNING(
                    f"Order {order.order_no} moved to abandoned successfully. Stock returned to shelves."
                ))