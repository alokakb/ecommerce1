from django.core.cache import cache
from django.db import transaction
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from products.models import Category
from products.serializers.staff_admin import AdminCategorySerializer
from products.services.cache_service import invalidate_category_cache, invalidate_product_search_cache


class AdminCategoryCreateAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = AdminCategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        serializer.save()
        # invalidate the cache
        transaction.on_commit(invalidate_category_cache)
        transaction.on_commit(invalidate_product_search_cache())
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class AdminCategoryUpdateAndDeleteView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    def patch(self, request, category_id):
        category = get_object_or_404(Category, id=category_id)
        serializer = AdminCategorySerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # invalidate the cache
        transaction.on_commit(invalidate_category_cache)
        transaction.on_commit(invalidate_product_search_cache)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, category_id):
        category = get_object_or_404(Category, id=category_id)

        if category.children.exists():
            return Response({
                "error": "Cannot delete this category because it has child categories. Move them first."
            },
                status=status.HTTP_400_BAD_REQUEST, )

        if category.products.exists():
            return Response(
                {
                    "error": "Cannot delete this category because it has associated products. Reassign them first."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        category.delete()
        # invalidate the cache
        transaction.on_commit(invalidate_category_cache)
        transaction.on_commit(invalidate_product_search_cache)
        return Response(status=status.HTTP_204_NO_CONTENT)







