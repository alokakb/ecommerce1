from django.urls import path

from orders.views.order import OrderCreateAPIView
# from orders.views.payments import (RazorpayWebhookAPIView,
#                                     RazorpayPaymentInitiateAPIView,
#                                     TestRazorpayPaymentCheckoutAPIView)

urlpatterns = [
    # checkout session
    path('checkout/', OrderCreateAPIView.as_view(), name='order-checkout'),

    # payments webhook
    # path('payments/webhook/razorpay/', RazorpayWebhookAPIView.as_view(), name='razorpay-webhook'),
    # path('payments/initiate/razorpay/', RazorpayPaymentInitiateAPIView.as_view(),name='razorpay-payment-initiate'),
    # path('payments/test_payment_checkout/razorpay/', TestRazorpayPaymentCheckoutAPIView.as_view(),name='razorpay-payment-checkout'),

]