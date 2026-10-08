from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication

from products.serializers.seller import SellerProductCreationSerializer, SellerProductVariantCreationSerializer
from sellers.permissions import IsVerifiedSellers


class SellerProductCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsVerifiedSellers]

    @transaction.atomic
    def post(self, request):
        vendor_profile = request.user.seller_profile

        # Initiate the parent serializer with raw incoming data
        parent_serializer = SellerProductCreationSerializer(data=request.data)
        parent_serializer.is_valid(raise_exception=True)

        # Extract the variations data array we stripped ot via validation
        variations_data = parent_serializer.validated_data.pop('variations')

        print(f"Variations data for pushing product by seller : {variations_data}")

        # atomic db transaction block
        with transaction.atomic():
            product = parent_serializer.save(seller=vendor_profile)

            # Instantiate the child serializer using variations_data
            variant_serializer = SellerProductVariantCreationSerializer(
                data=variations_data,
                many=True
            )

            variant_serializer.is_valid(raise_exception=True)
            variant_serializer.save(product=product)

        print(f"This is the Product seller has pushed  {product} ")
        # Return a detail schema
        response_serializer = SellerProductCreationSerializer(product)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)



