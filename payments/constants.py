


# App's internal, canonical transaction states
INTERNAL_STATUS_SUCCESS = 'success'
INTERNAL_STATUS_FAILURE = 'failure'
INTERNAL_STATUS_PENDING = 'pending'

# Razorpay status map
RAZORPAY_STATUS_MAP ={
    'captured': INTERNAL_STATUS_SUCCESS,
    'failed': INTERNAL_STATUS_FAILURE,
    'authorized': INTERNAL_STATUS_PENDING,
    'created': INTERNAL_STATUS_PENDING,
}

# Stripe status map
STRIPE_STATUS_MAP = {
    'succeeded': INTERNAL_STATUS_SUCCESS,
    'charge.succeeded': INTERNAL_STATUS_SUCCESS,
    'payment_intent.succeeded': INTERNAL_STATUS_SUCCESS,
    'payment_intent.payment_failed': INTERNAL_STATUS_FAILURE,
    'requires_capture': INTERNAL_STATUS_PENDING,
    'processing': INTERNAL_STATUS_PENDING,
}

# paypal status map
PAYPAL_STATUS_MAP = {
    'COMPLETED': INTERNAL_STATUS_SUCCESS,
    'FAILED': INTERNAL_STATUS_FAILURE,
    'DENIED': INTERNAL_STATUS_FAILURE,
    'PENDING': INTERNAL_STATUS_PENDING,
}

GATEWAY_REGISTRY = {
    'razorpay': {
        'url_template': 'https://api.razorpay.com/v1/orders/{gateway_order_id}',
        'status_map': RAZORPAY_STATUS_MAP,
        'status_json_path': ['status']
    },
    'stripe': {
        'url_template': 'https://api.stripe.com/v1/payment_intents/{gateway_order_id}',
        'status_map': STRIPE_STATUS_MAP,
        'status_json_path': ['status']
    },
    'paypal': PAYPAL_STATUS_MAP,
}