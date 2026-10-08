from django.db import transaction
from django.db.models import F

from orders.models import Order, Refund

import logging

from products.models import ProductVariant

logger = logging.getLogger(__name__)


def process_successful_refund(order: Order, refund: Refund):

    if refund.status == 'success':
        return
    refund.status = 'success'
    refund.save(update_fields=['status'])

    # Todo : Logic to return the order items back to inventory
    # Full refund
    order_items = order.items.all()
    for item in order_items:
        updated = ProductVariant.objects.filter(
            pk=item.variant.pk).update(stock_quantity=F('stock_quantity') + item.quantity_ordered)

        if updated != 1:
            raise RuntimeError(
                f"ProductVariant {item.variant.pk} not found"
            )

        item.variant.stock_quantity += item.quantity_ordered
        item.quantity_returned = item.quantity_ordered
        item.save(update_fields=['quantity_returned'])
        item.variant.save(update_fields=['stock_quantity'])


def process_failed_refund(order : Order, refund : Refund):
    refund.status = 'failed'
    refund.save(update_fields=['status'])


