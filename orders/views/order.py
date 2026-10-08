from django.db.models import F
from django.utils import timezone
from django.db import transaction
from django.shortcuts import render
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.db import models
from cart.models import CartItem, Cart
from orders.exceptions import InsufficientStockError
from orders.models import Order, OrderItem
from products.models import ProductVariant
from users.models import Address
from orders.services.discount_services import calculate_discount
from decimal import Decimal
from idempotency.models import IdempotencyRecord


# Create your views here.

# ---------------    Version V2 of OrderCreateAPIView      -----------------------------

class OrderCreateAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):

        # ---------------------------------------------------------
        # 1. Idempotency-Key is required from the client
        # ---------------------------------------------------------
        idempotency_key = request.headers.get("Idempotency-Key")

        if not idempotency_key:
            return Response(
                {"error": "Idempotency-Key header is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ---------------------------------------------------------
        # 2. Validate shipping address before starting transaction
        # ---------------------------------------------------------
        address_query_set = Address.objects.filter(
            user=request.user,
            is_default=True
        ).values(
            shipping_full_name=models.F("full_name"),
            shipping_phone_number=models.F("phone_number"),
            shipping_address_line_1=models.F("address_line1"),
            shipping_address_line_2=models.F("address_line2"),
            shipping_city=models.F("city"),
            shipping_state=models.F("state_province"),
            shipping_postal_code=models.F("postal_code"),
            shipping_country=models.F("country"),
        )

        address_data = address_query_set.first()

        if not address_data:
            address_data = request.data.get("shipping_address")

        if not address_data:
            return Response(
                {"error": "Shipping address is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        coupon_code = request.data.get("coupon_code")

        try:
            with ((transaction.atomic())):

                # -------------------------------------------------
                # 3. Lock the user's cart
                #
                # This serializes concurrent checkout operations
                # against the same cart.
                # -------------------------------------------------
                cart = (
                    Cart.objects
                    .select_for_update()
                    .get(user=request.user)
                )

                # -------------------------------------------------
                # 4. Check whether THIS exact request was already
                # processed.
                #
                # Same IK = same logical checkout operation.
                # -------------------------------------------------
                try:
                    idempotency_record = (
                        IdempotencyRecord.objects
                        .select_for_update()
                        .get(
                            user=request.user,
                            idempotency_key=idempotency_key
                        )
                    )

                    # Same request was already completed.
                    # Return the previously created order.
                    if idempotency_record.status == "completed":
                        order = idempotency_record.order

                        return Response(
                            {
                                "message": "Checkout request already processed.",
                                "order_id": order.id,
                                "order_no": order.order_no,
                                "total_amount": order.total_amount,
                            },
                            status=status.HTTP_200_OK
                        )

                    # Another request with the same IK is currently
                    # being processed.
                    return Response(
                        {"error": "This checkout request is already being processed."},
                        status=status.HTTP_409_CONFLICT
                    )

                except IdempotencyRecord.DoesNotExist:

                    # First time we have seen this IK.
                    idempotency_record = IdempotencyRecord.objects.create(
                        user=request.user,
                        idempotency_key=idempotency_key,
                        status="processing",
                    )

                # -------------------------------------------------
                # 5. Lock cart items
                #
                # Checkout now has exclusive access to these items.
                # -------------------------------------------------
                cart_items = (
                    CartItem.objects
                    .select_for_update()
                    .select_related("variant__product")
                    .filter(cart=cart)
                )

                if not cart_items.exists():
                    return Response(
                        {"error": "Cart is empty."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # -------------------------------------------------
                # 6. Validate stock while holding the row locks
                # -------------------------------------------------
                for cart_item in cart_items:

                    if cart_item.quantity > cart_item.variant.stock_quantity:
                        return Response(
                            {
                                "error": (
                                    f"Quantity exceeded for {cart_item.variant}. "
                                    f"Only {cart_item.variant.stock_quantity} units available."
                                )
                            },
                            status=status.HTTP_400_BAD_REQUEST
                        )

                # -------------------------------------------------
                # 7. Create Order
                #
                # The Order represents a snapshot of the cart
                # at this particular checkout attempt.
                # -------------------------------------------------
                order = Order.objects.create(
                    user=request.user,
                    subtotal=Decimal("0.00"),
                    total_amount=Decimal("0.00"),
                    order_status="pending",
                    **address_data
                )

                order_items_to_create = []
                total_price = Decimal("0.00")

                # -------------------------------------------------
                # 8. Create OrderItems and reserve/deduct stock
                # -------------------------------------------------
                for cart_item in cart_items:

                    order_item = OrderItem(
                        order=order,
                        variant=cart_item.variant,
                        price_at_purchase=cart_item.variant.price,
                        sku_at_purchase=cart_item.variant.sku,
                        quantity_ordered=cart_item.quantity,
                    )

                    order_items_to_create.append(order_item)

                    total_price += cart_item.subtotal

                    # Deduct stock from variant using atomic DB update
                    updated = ProductVariant.objects.filter(
                        pk=cart_item.variant.pk,
                        stock_quantity__gte=cart_item.quantity
                    ).update(stock_quantity=F("stock_quantity") - cart_item.quantity)

                    # rollback the whole transaction if any item is out of stock
                    if updated == 0:
                        raise InsufficientStockError(
                            cart_item.variant.pk,
                            cart_item.quantity
                        )

                    cart_item.variant.stock_quantity -= cart_item.quantity
                    cart_item.variant.save(
                        update_fields=["stock_quantity"]
                    )

                # -------------------------------------------------
                # 9. Calculate discount and final amount
                # -------------------------------------------------
                discount_amount = calculate_discount(
                    total_price,
                    coupon_code
                )

                total_amount = total_price - discount_amount

                order.discount_amount = discount_amount
                order.subtotal = total_price
                order.total_amount = total_amount

                order.save(
                    update_fields=[
                        "discount_amount",
                        "subtotal",
                        "total_amount",
                    ]
                )

                OrderItem.objects.bulk_create(order_items_to_create)

                # -------------------------------------------------
                # 10. Mark IK as completed and associate it with
                #     the newly created order.
                #
                # Everything is inside the same transaction.
                # If anything fails, the order + stock changes +
                # idempotency record all roll back together.
                # -------------------------------------------------
                idempotency_record.status = "completed"
                idempotency_record.order = order
                idempotency_record.completed_at = timezone.now()

                idempotency_record.save(
                    update_fields=[
                        "status",
                        "order",
                        "completed_at",
                    ]
                )

                return Response(
                    {
                        "message": "Checkout session initiated successfully.",
                        "order_id": order.id,
                        "order_no": order.order_no,
                        "total_amount": order.total_amount,
                    },
                    status=status.HTTP_201_CREATED
                )

        except Cart.DoesNotExist:
            return Response(
                {"error": "Cart not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        except InsufficientStockError as e:
            return Response(
                {"Error": e.message},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# ---------    version v1 of this OrderCreateAPIView  ---------------------

# class OrderCreateAPIView(APIView):
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [IsAuthenticated]
#
#     def post(self, request):
#
#         address_query_set = Address.objects.filter(user=request.user, is_default=True).values(
#             shipping_full_name = models.F('full_name'),
#             shipping_phone_number = models.F('phone_number'),
#             shipping_address_line_1 = models.F('address_line1'),
#             shipping_address_line_2=models.F('address_line2'),
#             shipping_city = models.F('city'),
#             shipping_state = models.F('state_province'),
#             shipping_postal_code = models.F('postal_code'),
#             shipping_country = models.F('country')
#
#         )
#         print(address_query_set)
#         address_data = address_query_set.first()
#
#         print(address_data)
#
#         if not address_query_set.exists():
#             address_data = request.data.get('shipping_address')
#
#         coupon_code = request.data.get('coupon_code')
#
#         if not address_data:
#             return Response({"Error": "Shipping Address Field is required"}, status=status.HTTP_400_BAD_REQUEST)
#
#         try:
#             with transaction.atomic():
#                 cart_item_container = CartItem.objects.select_for_update().select_related('variant__product').filter(
#                     cart__user=request.user
#                 )
#
#                 if not cart_item_container.exists():
#                     return Response({"Error": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST)
#
#                 for cart_item in cart_item_container:
#                     if cart_item.quantity > cart_item.variant.stock_quantity:
#                         return Response(
#                             {"Message": f"Quantity exceeded for {cart_item.variant}. "
#                                         f"Only {cart_item.variant.stock_quantity} units available"
#                              },
#                             status=status.HTTP_400_BAD_REQUEST
#                         )
#
#                 order = Order.objects.create(
#                     user=request.user, subtotal=Decimal('0.00'), total_amount=Decimal('0.00'),
#                     order_status='pending', payment_status='unpaid', **address_data
#                 )
#                 order_items_to_create = []
#                 total_price = Decimal('0.00')
#
#                 # Deduct the units of variant from inventory stock quantities
#                 for cart_item in cart_item_container:
#
#                     order_item = OrderItem(
#                         order=order,
#                         variant=cart_item.variant,
#                         price_at_purchase=cart_item.variant.price,
#                         sku_at_purchase=cart_item.variant.sku,
#                         quantity_ordered=cart_item.quantity
#                     )
#                     order_items_to_create.append(order_item)
#                     total_price += cart_item.subtotal
#                     cart_item.variant.stock_quantity -= cart_item.quantity
#                     cart_item.variant.save()
#
#                 discount_amount = calculate_discount(total_price, coupon_code)
#                 total_amount = total_price - discount_amount
#
#                 # setting discount and financial fields
#                 order.discount_amount = discount_amount
#                 order.subtotal = total_price
#                 order.total_amount = total_amount
#                 order.save()
#
#                 OrderItem.objects.bulk_create(order_items_to_create)
#
#                 return Response(
#                     {
#                         "message": "Checkout Session initiated successfully",
#                         "order_id": order.id,
#                         "order_no": order.order_no,
#                         "Total amount": order.total_amount,
#                     },
#                     status=status.HTTP_201_CREATED
#                 )
#         except Exception as e:
#             return Response({"Error": str(e)}, status=status.HTTP_400_BAD_REQUEST)














