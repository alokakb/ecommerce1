from django.db.models import F

from products.models import ProductVariant

def _release_order_items_to_stock(order):
    order_items = order.items.all()
    for item in order_items:
        updated = ProductVariant.objects.filter(
            pk=item.variant.pk).update(stock_quantity=F('stock_quantity') + item.quantity_ordered)

        if updated != 1:
            raise RuntimeError(
                f"ProductVariant {item.variant.pk} not found"
            )

def release_stocks_back_to_inventory(order):
    # Release the reserved stocks of each items back to the inventory
    _release_order_items_to_stock(order)

def release_stocks_on_refund(order):
    # Release the reserved stocks of each items back to the inventory
    _release_order_items_to_stock(order)

    # update each item field 'quantity_returned'
    order.items.update(quantity_returned=F('quantity_ordered'))


