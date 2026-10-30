from orders.models import Order
from payments.models import Payment
from cart.services import cart_cleanup
from products.services import release_stocks

def process_successful_checkout(order : Order):
    if order.order_status == 'paid':
        return
    order.order_status = 'paid'
    order.save(update_fields=['order_status'])
    cart_cleanup.cart_cleanup(order)

def process_abandoned_order(order : Order, payment : Payment):
    if order.order_status == 'paid' or payment.status == 'captured':
        return

    # Ghost checkout case -> Genuine abandonment confirmed
    # Release the reserved stocks back to the inventory
    release_stocks.release_stocks_back_to_inventory(order)

    # Lock down final terminal states
    order.order_status = 'abandoned'
    order.save(update_fields=['order_status'])


