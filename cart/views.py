from django.db import transaction, IntegrityError
from django.shortcuts import render
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from cart.models import Cart, CartItem
from cart.serializers import CartSerializer, CartItemSerializer


# Create your views here.

class CartAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Fetch or create active cart container
        cart, _ = Cart.objects.get_or_create(user=request.user)

        cart_queryset = Cart.objects.prefetch_related('items__variant__product').get(id=cart.id)
        serializer = CartSerializer(cart_queryset)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        serializer = CartItemSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        variant = serializer.validated_data.get('variant')
        quantity = serializer.validated_data.get('quantity')

        try:
            with transaction.atomic():
                cart_item = CartItem.objects.select_for_update().get(cart=cart, variant=variant)

                # stock check here
                if cart_item.quantity + quantity > variant.stock_quantity:
                    return Response(
                        {"stock": f"Cannot add more. Only {variant.quantity} units available"},status.HTTP_400_BAD_REQUEST
                    )
                cart_item.quantity += quantity
                cart_item.save()

        except CartItem.DoesNotExist:
            try:
                with transaction.atomic():
                    cart_item = CartItem.objects.create(cart=cart, variant=variant, quantity=quantity)
            except IntegrityError:
                with transaction.atomic():
                    cart_item = CartItem.objects.select_for_update().get(cart=cart, variant=variant)

                    # stock check here just to be safe before saving the addition
                    if cart_item.quantity + quantity > variant.stock_quantity:
                        return Response(
                            {"stock": f"Cannot add more. Max stock is {variant.stock_quantity}."},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    cart_item.quantity += quantity
                    cart_item.save()

        return Response({"message":"Item added to Cart Successfully"}, status=status.HTTP_201_CREATED)

    def patch(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)

        variant_id = request.data.get('variant')
        quantity_change = request.data.get('quantity')

        quantity_change = int(quantity_change)
        try:
            with transaction.atomic():
                cart_item = CartItem.objects.select_for_update().select_related('variant').get(cart=cart, variant_id=variant_id)

                new_quantity = cart_item.quantity + quantity_change

                if new_quantity <= 0:
                    cart_item.delete()
                    return Response({"message":"Item removed from the cart"}, status=status.HTTP_200_OK)

                if new_quantity > 0 and new_quantity > cart_item.variant.stock_quantity:
                    return Response(
                        {"stock": f"Cannot add more. Max stock is {cart_item.variant.stock_quantity}."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                cart_item.quantity = new_quantity
                cart_item.save()

                return Response({"message":"Cart Updated"}, status=status.HTTP_200_OK)

        except CartItem.DoesNotExist:
            return Response({"message":"Item Not Found in the Cart"}, status=status.HTTP_400_BAD_REQUEST)


    def delete(self, request):

        cart, _ = Cart.objects.get_or_create(user=request.user)

        variant_id = request.data.get('variant')

        try:
            with transaction.atomic():
                cart_item = CartItem.objects.select_for_update().get(cart=cart, variant_id=variant_id)
                cart_item.delete()
                return Response({"message": "Item Deleted"}, status=status.HTTP_200_OK)
        except CartItem.DoesNotExist:
            return Response({"message":"Item Not Found in the Cart"}, status=status.HTTP_400_BAD_REQUEST)













