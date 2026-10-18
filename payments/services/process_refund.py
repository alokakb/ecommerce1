from orders.models import Order
from payments.models import Refund
from products.services import release_stocks

import logging

logger = logging.getLogger(__name__)


def process_successful_refund(order: Order, refund: Refund):

    if refund.status == 'success':
        return
    refund.status = 'success'
    refund.save(update_fields=['status'])

    # Full refund
    release_stocks.release_stocks_on_refund(order)


def process_failed_refund(order : Order, refund : Refund):
    if refund.status == 'success':
        return
    refund.status = 'failed'
    refund.save(update_fields=['status'])


