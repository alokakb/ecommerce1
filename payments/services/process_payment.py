from django.db import transaction
from cart.models import CartItem
from orders.constants import GATEWAY_REGISTRY, INTERNAL_STATUS_SUCCESS
from orders.models import Order, Payment
from django.conf import settings
import logging

import requests

logger = logging.getLogger(__name__)

def check_actual_gateway_status(order: Order) -> str:
    """ Dynamically map configuration metadata"""
    gateway_name = order.payment_method
    config = GATEWAY_REGISTRY.get(gateway_name)

    if not config:
        logger.error(f"configuration missing for gateway {gateway_name} on order {order.order_no}")
        return 'pending'

    try:
        url = config['url_template'].format(order_no=order.order_no)
        auth_credentials = (settings.GATEWAY_KEY, settings.GATEWAY_SECRET)

        response = requests.get(url, auth=auth_credentials, timeout=5)

        if response.status_code == 200:
            gateway_data = response.json()
            raw_status = gateway_data
            for key in config['status_json_path']:
                raw_status = raw_status.key(key, {})
            return config['status_map'].get(raw_status, 'pending')

    except requests.RequestException as e:
        logger.error(f"Network error verifying gateway status for order {order.order_no}: {str(e)}")
        return 'pending'
    except Exception as e:
        logger.error(f"Unexpected error verifying gateway status for order {order.order_no}: {str(e)}")
        return 'pending'
    return 'pending'


def process_successful_payment(order: Order, payment: Payment):
    if order.order_status == 'paid':
        return
    order.order_status = 'paid'
    payment.status = 'captured'
    order.save(update_fields=["order_status"])
    payment.save(update_fields=["status"])

    purchased_variant_ids = order.items.values_list('variant_id', flat=True)
    cart_item = CartItem.objects.select_for_update().filter(
        cart__user=order.user, variant_id__in=purchased_variant_ids
    )
    cart_item.delete()


def process_failed_payment(order: Order, payment: Payment):
    payment.status = 'failed'
    payment.save(update_fields=["status"])



# ------------ Version V1 of process_successful_payment ----------

# def process_successful_payment(order: Order, payment: Payment):
#     with transaction.atomic():
#         if order.order_status == 'paid':
#             return
#         order.order_status = 'paid'
#         payment.status = 'captured'
#         order.save(update_fields=["order_status"])
#         payment.save(update_fields=["status"])
#
#         purchased_variant_ids = order.items.values_list('variant_id', flat=True)
#         cart_item = CartItem.objects.select_for_update().filter(
#             cart__user=order.user, variant_id__in=purchased_variant_ids
#         )
#         cart_item.delete()



