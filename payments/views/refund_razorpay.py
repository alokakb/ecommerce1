from django.db import transaction, IntegrityError
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings
from orders.models import Order, Refund, Payment
from payments.models import PaymentEvent
from idempotency.models import IdempotencyRecord

import razorpay
import logging

from requests import exceptions

from payments.services.process_refund import process_successful_refund, process_failed_refund
logger = logging.getLogger(__name__)


class RefundWebhookAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        payload_body = request.body.decode('utf-8')
        signature = request.headers.get('X-Razorpay-Signature')

        print("Refund webhook HEADERS: ", request.headers)
        print("Refund webhook BODY: \n", payload_body)

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


        payload = request.data
        event_id = request.headers.get("X-Razorpay-Event-Id")
        event_type = payload.get("event")

        refund_entity = (
            payload
            .get("payload", {})
            .get("refund", {})
            .get("entity", {})
        )

        refund_id = refund_entity.get("id")
        refund_status = refund_entity.get("status")
        payment_id = refund_entity.get("payment_id")
        amount = refund_entity.get("amount")
        currency = refund_entity.get("currency")

        payment_entity = (
            payload
            .get("payload", {})
            .get("payment", {})
            .get("entity", {})
        )

        order_no = (
            payment_entity
            .get("notes", {})
            .get("order_no")
        )

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
                    order = Order.objects.get(order_no=order_no)
                    payment = Payment.objects.get(order=order,
                                                  status='captured',
                                                  provider='razorpay')
                    refund = Refund.objects.get(payment=payment, status='processing')

                    # Before creating PaymentEvent :
                    # Validation of payment_id and refund_id
                    if not payment_id == payment.gateway_payment_id:
                        return Response({"Error": "payment_id does not match"}, status=status.HTTP_409_CONFLICT)
                    if not refund_id == refund.gateway_refund_id:
                        return Response({"Error": "refund_id does not match"}, status=status.HTTP_409_CONFLICT)

                    PaymentEvent.objects.create(event_id=event_id,
                                                event_type=event_type,
                                                order=order,
                                                provider='Razorpay'
                                                )
            except IntegrityError:
                return Response({'Status': 'Processed'}, status=status.HTTP_200_OK)
            except Order.DoesNotExist:
                return Response({'Error' : 'Order does not exist'}, status=status.HTTP_404_NOT_FOUND)
            except Payment.DoesNotExist:
                return Response({'Error': 'Payment does not exist'}, status=status.HTTP_404_NOT_FOUND)
            except Refund.DoesNotExist:
                return Response({'Error': 'Refund initiation did not happen or does not exist'}, status=status.HTTP_404_NOT_FOUND)


            try:
                refund.amount = amount / 100
                refund.currency = currency
                if refund_status == 'processed':
                    process_successful_refund(order, refund)
                elif refund_status == 'failed':
                    process_failed_refund(order, refund)
                else:
                    logger.warning("Unhandled Razorpay refund status %s for refund %s",
                                   refund_status, refund_id)
                    return Response({"error":"Unhandled refund status"},
                                    status=status.HTTP_400_BAD_REQUEST)
                refund.save(update_fields=['amount', 'currency'])
                return Response({"status":"processed"}, status=status.HTTP_200_OK)

            except Exception:
                transaction.set_rollback(True)
                logger.exception(f"Failed to process webhook order_no : {order_no}, gateway_order_id : {payment.gateway_order_id}")
                return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class RefundInitiateAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, order_no):
        # TODO: Next phase : Phase 2
        # Add operation-specific idempotency for refund initiation.
        # Current phase relies on Order row locking + refund_status.

        # payload = request.data
        # order_no = payload.get("order_no")

        if not order_no:
            return Response({'Error': 'order_no is required.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                order = Order.objects.select_for_update().get(order_no=order_no,
                                                              user=request.user,
                                                              order_status='paid')
                payment = Payment.objects.get(order=order,
                                              status='captured',
                                              provider='razorpay')

                # 1. check whether this payment already has a successful refund
                successful_refund = Refund.objects.filter(payment=payment,
                                                          status='success').first()
                if successful_refund:
                    return Response(
                        {
                            "error": "Refund has already been successfully processed."
                        },
                        status=status.HTTP_409_CONFLICT
                    )

                # 2. check whether a refund is currently in progress -> either it is 'created' or 'processing'
                active_refund = Refund.objects.filter(payment=payment,
                                                      status__in=['created', 'processing']).first()
                if active_refund:
                    return Response(
                        {
                            "error": "Refund is already in progress."
                        },
                        status=status.HTTP_409_CONFLICT
                    )

                # 3. A new refund attempt is allowed.
                refund = Refund.objects.create(payment=payment, status='created')

                client = razorpay.Client(auth=(settings.RAZORPAY_KEY, settings.RAZORPAY_SECRET))
                try:
                    refund_response = client.payment.refund(
                        payment.gateway_payment_id, {}
                    )
                    print("Refund payload: \n", refund_response)
                    refund_id = refund_response.get("id")
                    refund_status = refund_response.get("status")

                    if refund_status == "pending" and refund_id:
                        order.order_status = "cancelled"
                        order.cancelled_at = timezone.now()
                        refund.status = 'processing'
                        refund.gateway_refund_id = refund_id
                        order.save(update_fields=['order_status', 'cancelled_at'])
                        refund.save(update_fields=['gateway_refund_id', 'status'])

                        return Response(
                            {'Msg': 'Order refund was successfully created'},
                            status=status.HTTP_200_OK
                        )
                    else:
                        refund.status = 'failed'
                        refund.save(update_fields=['status'])
                        logger.error(
                            "Unexpected Razorpay refund response for order %s: %s",
                            order.order_no,
                            refund_response,
                        )

                    return Response(
                        {
                            "error": "Refund was not created by Razorpay",
                            "razorpay_status": refund_status,
                        },
                        status=status.HTTP_502_BAD_GATEWAY
                    )

                except razorpay.errors.BadRequestError as e:
                    refund.status = 'failed'
                    refund.save(update_fields=['status'])
                    return Response(
                        {"error": f"Razorpay bad request: {str(e)}"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except Order.DoesNotExist:
                return Response({'Error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)
            except Payment.DoesNotExist:
                return Response({'Error': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)



# -----------------  Version V1 of RefundWebhookAPIView ------------------------
#
# class RefundWebhookAPIView(APIView):
#     permission_classes = [AllowAny]
#
#     def post(self, request):
#         payload_body = request.body.decode('utf-8')
#         signature = request.headers.get('X-Razorpay-Signature')
#
#         print("Refund webhook HEADERS: ", request.headers)
#         print("Refund webhook BODY: \n", payload_body)
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
#         event_id = request.headers.get("X-Razorpay-Event-Id")
#         event_type = payload.get("event")
#
#         refund_entity = (
#             payload
#             .get("payload", {})
#             .get("refund", {})
#             .get("entity", {})
#         )
#
#         refund_id = refund_entity.get("id")
#         refund_status = refund_entity.get("status")
#         payment_id = refund_entity.get("payment_id")
#
#
#         payment_entity = (
#             payload
#             .get("payload", {})
#             .get("payment", {})
#             .get("entity", {})
#         )
#
#         order_no = (
#             payment_entity
#             .get("notes", {})
#             .get("order_no")
#         )
#
#         if not event_id:
#             return Response(
#                 {"error": "Missing X-Razorpay-Event-Id"},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
#         if not order_no:
#             return Response({"Error": "Missing Order no"}, status=status.HTTP_400_BAD_REQUEST)
#
#         with transaction.atomic():
#             try:
#                 with transaction.atomic():
#                     order = Order.objects.get(order_no=order_no)
#                     PaymentEvent.objects.create(event_id=event_id,
#                                                 event_type=event_type,
#                                                 order=order,
#                                                 provider='Razorpay'
#                                                 )
#             except IntegrityError:
#                 return Response({'Status': 'Processed'}, status=status.HTTP_200_OK)
#             except Order.DoesNotExist:
#                 return Response({'Error' : 'Order does not exist'}, status=status.HTTP_404_NOT_FOUND)
#
#             # Validation of payment_id and refund_id
#             if not payment_id == order.gateway_payment_id:
#                 return Response({"Error": "payment_id does not match"}, status=status.HTTP_409_CONFLICT)
#             if not refund_id == order.refund_id:
#                 return Response({"Error": "refund_id does not match"}, status=status.HTTP_409_CONFLICT)
#
#             try:
#                 if refund_status == 'processed':
#                     process_successful_refund(order)
#                 elif refund_status == 'failed':
#                     process_failed_refund(order)
#
#                 return Response({"status":"processed"}, status=status.HTTP_200_OK)
#
#             except Exception as e:
#                 logger.exception(f"Failed to process webhook order_no : {order_no}, gateway_order_id : {order.gateway_order_id}")
#                 return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# ---------------   Version V1 of RefundInitiateAPIView  ----------------------
#
# class RefundInitiateAPIView(APIView):
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [IsAuthenticated]
#
#     def post(self, request, order_no):
#         # TODO: Next phase : Phase 2
#         # Add operation-specific idempotency for refund initiation.
#         # Current phase relies on Order row locking + refund_status.
#
#
#         # payload = request.data
#         # order_no = payload.get("order_no")
#
#         if not order_no:
#             return Response({'Error': 'order_no is required.'}, status=status.HTTP_400_BAD_REQUEST)
#
#         with transaction.atomic():
#             try:
#                 order = Order.objects.select_for_update().get(order_no=order_no,
#                                                              user=request.user)
#
#                 if order.refund_status == 'created':
#                     return Response({'Error': 'Order refund is already initiated'}, status=status.HTTP_409_CONFLICT)
#
#                 elif order.refund_status == 'success':
#                     return Response({'Error': 'Order refund is already successfully processed'}, status=status.HTTP_409_CONFLICT)
#
#                 elif order.refund_status == 'failed':
#                     return Response({'Error': 'Order refund is failed. Please contact customer support'}, status=status.HTTP_409_CONFLICT)
#
#                 if order.order_status == 'paid' and order.payment_status == 'captured' and order.refund_status == 'not_requested':
#                     client = razorpay.Client(auth=(settings.RAZORPAY_KEY, settings.RAZORPAY_SECRET))
#                     try:
#                         refund_response = client.payment.refund(
#                             order.gateway_payment_id, {}
#                         )
#                         print("Refund payload: \n", refund_response)
#                         refund_id = refund_response.get("id")
#                         refund_status = refund_response.get("status")
#                         if refund_status == "pending" and refund_id:
#                             order.refund_status = "created"
#                             order.order_status = "cancelled"
#                             order.cancelled_at = timezone.now()
#                             order.refund_id = refund_id
#                             order.save(update_fields=['refund_status', 'refund_id', 'cancelled_at'])
#
#                             return Response(
#                                 {'Msg': 'Order refund was successfully created'},
#                                 status=status.HTTP_200_OK
#                             )
#                         else:
#                             logger.error(
#                                 "Unexpected Razorpay refund response for order %s: %s",
#                                 order.order_no,
#                                 refund_response,
#                             )
#
#                         return Response(
#                             {
#                                 "error": "Refund was not created by Razorpay",
#                                 "razorpay_status": refund_status,
#                             },
#                             status=status.HTTP_502_BAD_GATEWAY
#                         )
#
#                     except razorpay.errors.BadRequestError as e:
#                         return Response(
#                             {"error": f"Razorpay bad request: {str(e)}"},
#                             status=status.HTTP_400_BAD_REQUEST,
#                         )
#
#                 else:
#                     return Response(
#                         {"error": "Refund is not applicable for this order."},
#                         status=status.HTTP_409_CONFLICT
#                     )
#
#             except Order.DoesNotExist:
#                 return Response({'Error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)
