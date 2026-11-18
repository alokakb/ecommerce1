from django.db import transaction
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication

from products.models import Product, ProductVariant
from products.serializers.seller import SellerProductCreationSerializer, SellerProductVariantCreationSerializer, \
    SellerProductUpdateSerializer, SellerProductVariantUpdateSerializer
from sellers.permissions import IsVerifiedSellers
from products.services.cache_service import invalidate_product_cache, invalidate_product_search_cache, \
    invalidate_category_drilldown_cache, invalidate_product_variant_cache


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

            transaction.on_commit(invalidate_product_search_cache)
            transaction.on_commit(invalidate_category_drilldown_cache)

        print(f"This is the Product seller has pushed  {product} ")
        # Return a detail schema
        response_serializer = SellerProductCreationSerializer(product)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class SellerProductVariantCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsVerifiedSellers]

    @transaction.atomic
    def post(self, request, product_id):
        seller_profile = request.user.seller_profile

        product = get_object_or_404(Product, id=product_id,
                                    seller=seller_profile, is_active=True)

        serializer = SellerProductVariantCreationSerializer(
            data=request.data,
            many=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(product=product)
        transaction.on_commit(invalidate_product_cache(product_id))

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SellerProductUpdateAndDeleteView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsVerifiedSellers]

    def patch(self, request, product_id):
        seller = request.user.seller_profile
        product = get_object_or_404(Product, id=product_id, seller=seller, is_active=True)
        serializer = SellerProductUpdateSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        transaction.on_commit(invalidate_product_cache(product_id))
        transaction.on_commit(invalidate_product_search_cache)
        transaction.on_commit(invalidate_category_drilldown_cache)
        return Response(serializer.data, status=status.HTTP_200_OK)


    # This is temporary deactivation/soft deletion of product instead of deleting permanently
    def delete(self, request, product_id):
        seller = request.user.seller_profile
        product = get_object_or_404(Product, id=product_id, seller=seller, is_active=True)
        product.is_active = False
        product.save(update_fields=["is_active", "updated_at"])
        transaction.on_commit(invalidate_product_cache(product_id))
        transaction.on_commit(invalidate_product_search_cache)
        transaction.on_commit(invalidate_category_drilldown_cache)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SellerProductRecoverView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsVerifiedSellers]

    def patch(self, request, product_id):
        seller = request.user.seller_profile
        product = get_object_or_404(Product, id=product_id, seller=seller, is_active=False)
        product.is_active = True
        product.save(update_fields=['is_active', 'updated_at'])
        transaction.on_commit(invalidate_product_cache(product_id))
        transaction.on_commit(invalidate_product_search_cache)
        transaction.on_commit(invalidate_category_drilldown_cache)
        return Response( {"message": "Product reactivated successfully", "is_active": product.is_active},
                         status=status.HTTP_200_OK)


class SellerProductVariantUpdateAndDeleteView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsVerifiedSellers]

    def patch(self, request, product_id, variant_id):
        seller = request.user.seller_profile
        variant = get_object_or_404(ProductVariant, id=variant_id, product__id=product_id,
                                    product__seller=seller, is_active=True)
        serializer = SellerProductVariantUpdateSerializer(variant, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        transaction.on_commit(invalidate_product_cache(product_id))
        return Response(
            serializer.data, status=status.HTTP_200_OK
        )

    def delete(self, request, product_id, variant_id):
        seller = request.user.seller_profile
        variant = get_object_or_404(ProductVariant, id=variant_id, product__id=product_id,
                                    product__seller=seller, is_active=True)
        variant.is_active = False
        variant.save(update_fields=['is_active', 'updated_at'])
        transaction.on_commit(invalidate_product_cache(product_id))
        return Response(status=status.HTTP_204_NO_CONTENT)

class SellerProductVariantRecoverView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsVerifiedSellers]

    def patch(self, request, product_id, variant_id):
        seller = request.user.seller_profile
        variant = get_object_or_404(ProductVariant, id=variant_id,product__id=product_id,
                                    product__seller=seller, is_active=False)
        variant.is_active = True
        variant.save(update_fields=['is_active', 'updated_at'])
        transaction.on_commit(invalidate_product_cache(product_id))
        return Response({'message': 'Product Variant activated successfully'},
                        status=status.HTTP_200_OK)








