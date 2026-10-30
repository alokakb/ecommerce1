from django.db.models import F

from products.models import ProductVariant
from payments.exceptions import InsufficientStockError


def reserve_stock_from_cart(cart_items):
    # Deduct stock from variant using atomic DB update
    for cart_item in cart_items:
        updated = ProductVariant.objects.filter(
            pk=cart_item.variant.pk,
            stock_quantity__gte=cart_item.quantity
        ).update(stock_quantity=F("stock_quantity") - cart_item.quantity)

        # rollback the whole transaction if any item is out of stock
        if updated == 0:
            raise InsufficientStockError(
                cart_item.variant.pk,
                cart_item.quantity
            )