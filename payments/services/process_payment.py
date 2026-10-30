from payments.constants import GATEWAY_REGISTRY
from orders.models import Order
from payments.models import Payment
from django.conf import settings
import logging
from payments.exceptions import ConfigurationError
from orders.services import process_checkout

from payments.services import outbox

import requests

logger = logging.getLogger(__name__)

def check_actual_gateway_status(order: Order, payment: Payment) -> str:

    """ Dynamically map configuration metadata"""
    gateway_name = payment.provider
    config = GATEWAY_REGISTRY.get(gateway_name)

    if not config:
        logger.error('Configuration missing for Gateway %s on order_no %s', gateway_name, order.order_no)
        raise ConfigurationError(
            f"Configuration missing for gateway {gateway_name}"
        )

    try:
        # This if for razorpay hardcoded
        url = config['url_template'].format(gateway_order_id=payment.gateway_order_id)
        auth_credentials = (settings.RAZORPAY_KEY, settings.RAZORPAY_SECRET)

        response = requests.get(url, auth=auth_credentials, timeout=5)
        logger.info(f"response : {response.text}", )

        if response.status_code == 200:
            gateway_data = response.json()
            raw_status = gateway_data
            for key in config['status_json_path']:
                raw_status = raw_status.get(key, {})
            return config['status_map'].get(raw_status, 'undetermined')

    except requests.RequestException as e:
        logger.error(
            f"Network error verifying gateway status for order "
            f"{order.order_no}: {e}"
        )
        return "undetermined"
    except Exception as e:
        logger.error(
            f"Unexpected error verifying gateway status for order "
            f"{order.order_no}: {e}"
        )
        return "undetermined"
    return 'undetermined'


def process_successful_payment(order: Order, payment: Payment):
    if payment.status == 'captured':
        return
    payment.status = 'captured'
    payment.save(update_fields=["status"])

    # populate outbox event
    outbox.create_payment_captured_event(payment)

    process_checkout.process_successful_checkout(order)


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



