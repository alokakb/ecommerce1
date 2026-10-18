from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication

from payments.constants import RAZORPAY_STATUS_MAP
from orders.models import Order
from payments.models import PaymentEvent, Payment
from payments.services.process_payment import process_successful_payment, process_failed_payment
from django.conf import settings

from django.db import transaction, IntegrityError
from django.shortcuts import render

import razorpay
import logging

logger = logging.getLogger(__name__)



# -----------------   Version V2 of RazorpayWebhookAPIView   -----------------

@method_decorator(csrf_exempt, name='dispatch')
class RazorpayWebhookAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        payload_body = request.body.decode('utf-8')
        signature = request.headers.get('X-Razorpay-Signature')

        if not signature:
            return Response({
                "Error": "Missing X-Razorpay-Signature"
            }, status=status.HTTP_400_BAD_REQUEST)

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY, settings.RAZORPAY_SECRET))
        try:
            client.utility.verify_webhook_signature(
                payload_body, signature, settings.RAZORPAY_WEBHOOK_SECRET
            )
        except razorpay.errors.SignatureVerificationError:
            logger.warning("Razorpay webhook Signature verification failed")
            return Response({
                "Error": "Invalid webhook signature"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Extract payload data

        payload = request.data
        event_id = request.headers.get("X-Razorpay-Event-Id")
        event_type = payload.get("event")
        payment_entity = (
            payload
            .get("payload", {})
            .get("payment", {})
            .get("entity", {})
        )
        payment_id = payment_entity.get("id")
        order_id = payment_entity.get("order_id")
        raw_status = payment_entity.get("status")
        order_no = (
            payment_entity
            .get("notes", {})
            .get("order_no")
        )
        payment_method = payment_entity.get("method")

        if not event_id:
            return Response(
                {"error": "Missing X-Razorpay-Event-Id"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not order_no:
            return Response({"Error": "Missing Order no"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                with transaction.atomic():
                    order = Order.objects.select_for_update().get(order_no=order_no)
                    payment = Payment.objects.select_for_update().get(order=order,
                                                  provider="razorpay",
                                                  status="unpaid")
                    PaymentEvent.objects.create(event_id=event_id,
                                                event_type=event_type,
                                                order=order,
                                                provider='Razorpay'
                                                )
            except IntegrityError:
                if PaymentEvent.objects.filter(event_id=event_id).exists():
                    logger.info('Duplicate Razorpay webhook event %s ', event_id)
                    return Response({'Status': 'Processed'}, status=status.HTTP_200_OK)
                logger.exception('Unexpected Integrity Error creating PaymentEvent for event %s', event_id)
                raise
            except Order.DoesNotExist:
                return Response({'Error' : 'Order does not exist'}, status=status.HTTP_400_BAD_REQUEST)
            except Payment.DoesNotExist:
                # handle existing payment if it is already captured/failed, webhook must not retry
                existing_payment = Payment.objects.filter(order=order, provider='razorpay',
                                                          gateway_order_id=order_id).first()
                if existing_payment and existing_payment.status == 'captured':
                    return Response({'status': 'Already paid'}, status=status.HTTP_200_OK)
                if existing_payment and existing_payment.status == 'failed':
                    return Response({'status': 'Payment attempt was failed'}, status=status.HTTP_200_OK)
                return Response({'Error' : 'Payment attempt not found'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                if not payment.gateway_payment_id:
                    payment.gateway_payment_id = payment_id

                payment.payment_method = payment_method
                payment.save(update_fields=["gateway_payment_id", "payment_method"])

                translated_status = RAZORPAY_STATUS_MAP.get(raw_status, 'pending')
                if translated_status == 'success':
                    process_successful_payment(order, payment)
                elif translated_status == 'failed':
                    process_failed_payment(order, payment)
                elif translated_status == "pending":
                    logger.info(
                        "Payment is not terminal yet; order_no=%s, raw_status=%s",
                        order_no,raw_status,)
                    return Response({"status": "pending"},status=status.HTTP_200_OK)
                else:
                    logger.warning(
                        "Unhandled Razorpay payment status; order_no=%s, raw_status=%s",
                        order_no,raw_status,)
                    return Response({"error": "Unhandled payment status"},status=status.HTTP_400_BAD_REQUEST)
                return Response({"status":"processed"}, status=status.HTTP_200_OK)

            except Exception:
                transaction.set_rollback(True)
                logger.exception(f"Failed to process webhook order_no : {order_no}, gateway_order_id : {payment.gateway_order_id}")
                return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class RazorpayPaymentInitiateAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, order_no):

        if not order_no:
            return Response(
                {"error": "order_no is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use a transaction because select_for_update() only works
        # inside a database transaction.
        with transaction.atomic():

            # Lock this Order row so two concurrent payment-initiation
            # requests cannot process the same order simultaneously.
            try:
                order = (
                    Order.objects
                    .select_for_update()
                    .get(
                        order_no=order_no,
                        user=request.user,
                        order_status="pending",
                    )
                )
            except Order.DoesNotExist:
                return Response(
                    {"error": "Order not found or is already paid/cancelled."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            payment = Payment.objects.filter(order=order,
                                             provider="razorpay",
                                             status="unpaid").first()

            # If a Razorpay order was already created for this local order,
            # don't create another one. Just return the existing gateway order.
            if payment and payment.gateway_order_id:
                return Response(
                    {
                        "order_no": order.order_no,
                        "razorpay_order_id": payment.gateway_order_id,
                        "amount": int(order.total_amount * 100),
                        "currency": "INR",
                        "key_id": settings.RAZORPAY_KEY,
                    },
                    status=status.HTTP_200_OK,
                )
            if not payment:
                payment = Payment.objects.create(
                    order=order,
                    amount=order.total_amount,
                    currency=order.currency,
                    provider="razorpay",
                    status="unpaid",
                )

            # Convert total amount to paise (integer).
            amount_in_paise = int(order.total_amount * 100)

            # Initialize Razorpay Client.
            client = razorpay.Client(
                auth=(
                    settings.RAZORPAY_KEY,
                    settings.RAZORPAY_SECRET
                )
            )

            # Prepare payload for Razorpay.
            payload = {
                "amount": amount_in_paise,
                "currency": "INR",
                "receipt": f"receipt_{order.order_no}",
                "notes": {
                    "order_no": order.order_no,
                },
            }


            try:
                # Create Razorpay order.
                razorpay_order = client.order.create(data=payload)

                # Save the Razorpay order ID against our local Order.
                payment.provider = "razorpay"
                payment.gateway_order_id = razorpay_order["id"]

                payment.save(
                    update_fields=[
                        "provider",
                        "gateway_order_id",
                    ]
                )

                # Return details needed by frontend / Postman.
                return Response(
                    {
                        "order_no": order.order_no,
                        "razorpay_order_id": razorpay_order["id"],
                        "amount": razorpay_order["amount"],
                        "currency": razorpay_order["currency"],
                        "key_id": settings.RAZORPAY_KEY,
                    },
                    status=status.HTTP_200_OK,
                )

            except razorpay.errors.BadRequestError as e:
                payment.status = "failed"
                payment.save(update_fields=["status"])
                return Response(
                    {"error": f"Razorpay bad request: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            except Exception as e:
                payment.status = "failed"
                payment.save(update_fields=["status"])
                logger.exception("Unexpected Razorpay payment initiation failure for order %s",
                                 order.order_no)
                return Response(
                    {"error": f"Failed to initiate Razorpay order: {str(e)}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )




class TestRazorpayPaymentCheckoutAPIView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        order_no = request.query_params.get("order_no")
        if not order_no:
            return Response(
                {"error": "order_no is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            order = (
                Order.objects
                .get(
                    order_no=order_no,
                    user=request.user,
                    order_status="pending",
                )
            )
            payment = Payment.objects.get(order=order, provider="razorpay",
                                          status="unpaid")
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found or is already paid/cancelled."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Payment.DoesNotExist:
            return Response(
                {"error": "Payment not found or is already paid/cancelled."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Razorpay order must already have been created
        if not payment.gateway_order_id:
            return Response(
                {"error": "Razorpay payment has not been initiated for this order."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        razorpay_order_id = payment.gateway_order_id
        amount = int(order.total_amount * 100)
        currency = order.currency

        return render(
            request, "index.html",
            {
             "razorpay_key_id": settings.RAZORPAY_KEY,
             "razorpay_order_id": razorpay_order_id,
             "amount": amount,
             "currency": currency
             }
        )


# -----------------   Version V1 of RazorpayPaymentInitiateAPIView   -----------------

# class RazorpayPaymentInitiateAPIView(APIView):
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [IsAuthenticated]
#
#     def post(self, request, order_no):
#
#         if not order_no:
#             return Response(
#                 {"error": "order_no is required."},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )
#
#         # Use a transaction because select_for_update() only works
#         # inside a database transaction.
#         with transaction.atomic():
#
#             # Lock this Order row so two concurrent payment-initiation
#             # requests cannot process the same order simultaneously.
#             try:
#                 order = (
#                     Order.objects
#                     .select_for_update()
#                     .get(
#                         order_no=order_no,
#                         user=request.user,
#                         payment_status="unpaid",
#                         order_status="pending",
#                     )
#                 )
#             except Order.DoesNotExist:
#                 return Response(
#                     {"error": "Order not found or is already paid/cancelled."},
#                     status=status.HTTP_404_NOT_FOUND,
#                 )
#
#             # If a Razorpay order was already created for this local order,
#             # don't create another one. Just return the existing gateway order.
#             if order.gateway_order_id:
#                 return Response(
#                     {
#                         "order_no": order.order_no,
#                         "razorpay_order_id": order.gateway_order_id,
#                         "amount": int(order.total_amount * 100),
#                         "currency": "INR",
#                         "key_id": settings.RAZORPAY_KEY,
#                     },
#                     status=status.HTTP_200_OK,
#                 )
#
#             # Convert total amount to paise (integer).
#             amount_in_paise = int(order.total_amount * 100)
#
#             # Initialize Razorpay Client.
#             client = razorpay.Client(
#                 auth=(
#                     settings.RAZORPAY_KEY,
#                     settings.RAZORPAY_SECRET
#                 )
#             )
#
#             # Prepare payload for Razorpay.
#             payload = {
#                 "amount": amount_in_paise,
#                 "currency": "INR",
#                 "receipt": f"receipt_{order.order_no}",
#                 "notes": {
#                     "order_no": order.order_no,
#                 },
#             }
#
#             try:
#                 # Create Razorpay order.
#                 razorpay_order = client.order.create(data=payload)
#
#                 # Save the Razorpay order ID against our local Order.
#                 order.payment_method = "razorpay"
#                 order.gateway_order_id = razorpay_order["id"]
#
#                 order.save(
#                     update_fields=[
#                         "payment_method",
#                         "gateway_order_id",
#                     ]
#                 )
#
#                 # Return details needed by frontend / Postman.
#                 return Response(
#                     {
#                         "order_no": order.order_no,
#                         "razorpay_order_id": razorpay_order["id"],
#                         "amount": razorpay_order["amount"],
#                         "currency": razorpay_order["currency"],
#                         "key_id": settings.RAZORPAY_KEY,
#                     },
#                     status=status.HTTP_200_OK,
#                 )
#
#             except razorpay.errors.BadRequestError as e:
#                 return Response(
#                     {"error": f"Razorpay bad request: {str(e)}"},
#                     status=status.HTTP_400_BAD_REQUEST,
#                 )
#
#             except Exception as e:
#                 return Response(
#                     {"error": f"Failed to initiate Razorpay order: {str(e)}"},
#                     status=status.HTTP_502_BAD_GATEWAY,
#                 )



# -----------------   Version V1 of RazorpayWebhookAPIView   -----------------
#
# @method_decorator(csrf_exempt, name='dispatch')
# class RazorpayWebhookAPIView(APIView):
#     permission_classes = [AllowAny]
#
#     def post(self, request):
#         payload_body = request.body.decode('utf-8')
#         signature = request.headers.get('X-Razorpay-Signature')
#
#         if not signature:
#             return Response({
#                 "Error": "Missing X-Razorpay-Signature"
#             }, status=status.HTTP_400_BAD_REQUEST)
#
#         client = razorpay.Client(auth=(settings.RAZORPAY_KEY, settings.RAZORPAY_SECRET))
#         try:
#             client.utility.verify_webhook_signature(
#                 payload_body, signature, settings.RAZORPAY_WEBHOOK_SECRET
#             )
#         except razorpay.errors.SignatureVerificationError:
#             logger.warning("Razorpay webhook Signature verification failed")
#             return Response({
#                 "Error": "Invalid webhook signature"
#             }, status=status.HTTP_400_BAD_REQUEST)
#
#
#         payload = request.data
#
#         # debugging
#         event_id = request.headers.get('X-Razorpay-Event-ID')
#         print("event_id : \n")
#         print(event_id)
#
#         # 1. Extract Razorpay specific payload keys
#         order_no = payload.get('payload', {}).get('order', {}).get('entity', {}).get('notes', {}).get('order_no')
#         raw_status = payload.get('payload', {}).get('payment', {}).get('entity', {}).get('status')
#
#         if not order_no:
#             return Response({"Error":"Missing Order no"}, status=status.HTTP_400_BAD_REQUEST)
#
#         translated_status = RAZORPAY_STATUS_MAP.get(raw_status, 'pending')
#         try:
#             if translated_status == 'success':
#                 process_successful_payment(order_no)
#             elif translated_status == 'failed':
#                 process_failed_payment(order_no)
#             return Response({"status":"processed"}, status=status.HTTP_200_OK)
#
#         except Order.DoesNotExist:
#             return Response({"Error": f"Order {order_no} does not exist"}, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as e:
#             return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
#






