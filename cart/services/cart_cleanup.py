from cart.models import CartItem

def cart_cleanup(order):
    purchased_variant_ids = order.items.values_list('variant_id', flat=True)
    cart_item = CartItem.objects.select_for_update().filter(
        cart__user=order.user, variant_id__in=purchased_variant_ids
    )
    cart_item.delete()
