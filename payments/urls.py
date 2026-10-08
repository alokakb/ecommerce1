from django.urls import path

from payments.views.payment_razorpay import ( RazorpayWebhookAPIView,
                                              RazorpayPaymentInitiateAPIView,
                                              TestRazorpayPaymentCheckoutAPIView,
                                            )

from payments.views.refund_razorpay import RefundWebhookAPIView, RefundInitiateAPIView

urlpatterns = [

    # payments webhook
    path('webhook/razorpay/', RazorpayWebhookAPIView.as_view(), name='razorpay-webhook'),
    path('order/<str:order_no>/initiate/razorpay/', RazorpayPaymentInitiateAPIView.as_view(),name='razorpay-payment-initiate'),
    path('test_payment_checkout/razorpay/', TestRazorpayPaymentCheckoutAPIView.as_view(),name='razorpay-payment-checkout'),
    path('order/<str:order_no>/refund/initiate/razorpay/', RefundInitiateAPIView.as_view(),name='razorpay-refund-initiate'),
    path('webhook/refund/razorpay/', RefundWebhookAPIView.as_view(), name='razorpay-webhook'),

]