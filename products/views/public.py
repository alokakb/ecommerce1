from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.generics import RetrieveAPIView, ListAPIView
from rest_framework.response import Response
from rest_framework import status

from products.models import Product, Category
from products.serializers.public import (CategorySerializer, ProductListSerializer,
                                         ProductDetailSerializer, GlobalMenuCategorySerializer)
from products.services.category_tree import CategoryTreeService


class GlobalMenuAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        root_categories = Category.objects.filter(parent=None, is_active=True)
        serializer = GlobalMenuCategorySerializer(root_categories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CategoryDrillDownAPIView(APIView):
    """Dynamic catalog Navigator. Resolves whether to return subcategories
        or start streaming products depending on the tree structure"""
    permission_classes = [AllowAny]

    def get(self, request, category_id=None):
        # 1. Landing page / Root Level
        if category_id is None:
            root_categories = Category.objects.filter(parent=None)
            serializer = CategorySerializer(root_categories, many=True)
            return Response({
                "view_type": "ROOT_CATEGORIES",
                "categories": serializer.data
            }, status=status.HTTP_200_OK)

        # 2. Category Drilldown
        try:
            current_category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return Response({"Error": "Category not found"}, status=status.HTTP_404_NOT_FOUND)

        # 3. Subcategories living underneath the category
        child_categories = current_category.children.all()

        # check frontend override flag

        force_show_products = request.query_params.get('show_products').lower() == 'true' \
            if 'show_products' in request.query_params else False

        response_data = {
            "current_category": CategorySerializer(current_category).data,
            "view_type": "SUB_CATEGORIES",
            "sub_categories": [],
            "products": []
        }

        # 3. Dynamic Threshold Logic: should we pull products

        # Condition A: Frontend explicitly wants ALL products from this point down
        if force_show_products:
            response_data["view_type"] = "PRODUCT_LISTING_WITH_FILTERS"

            # Fetch products belonging to this category from service layer
            all_target_ids = CategoryTreeService.get_all_descendant_ids(current_category)
            products = Product.objects.filter(category_id__in=all_target_ids).order_by('-id')
            response_data["products"] = ProductListSerializer(products, many=True, context={'request': request}).data

        # Condition B: No child categories exists anymore,show products related to the leaf node
        elif not child_categories.exists():
            response_data["view_type"] = "PRODUCT_LISTING"

            # Fetch Products belonging directly to this leaf category
            products = Product.objects.filter(Category=current_category).order_by('-id')
            response_data["products"] = ProductListSerializer(products, many=True).data

        # Condition C: Standard dill-down mode
        else:
            response_data["sub_categories"] = CategorySerializer(child_categories, many=True).data

        return Response(response_data, status=status.HTTP_200_OK)



class ProductDetailAPIView(RetrieveAPIView):
    """Returns detailed product data along with the nested variations"""
    queryset = Product.objects.all()
    serializer_class = ProductDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = 'id'

class ProductSearchFilterAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        queryset = Product.objects.all().order_by('-id')
        target_category_id = request.query_params.get('category_filter') or request.query_params.get('category')

        if target_category_id:
            try:
                target_category = Category.objects.get(id=target_category_id)
                all_target_ids = CategoryTreeService.get_all_descendant_ids(target_category)
                queryset = queryset.filter(category_id__in=all_target_ids)
            except Category.DoesNotExist:
                return Response({"Error": "Selected Category does not exist"}, status=status.HTTP_404_NOT_FOUND)

        # Handle Price filters
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        if min_price: queryset = queryset.filter(price__gte=min_price)
        if max_price: queryset = queryset.filter(price__lte=max_price)

        for param, value in request.query_params.items():
            if param.startswith('spec__'):
                spec_key = param.replace('spec__', '')
                queryset = queryset.filter(
                    **{
                        f"spec__{spec_key}": value
                    }
                )
        serializer = ProductListSerializer(queryset, many=True, context={'request':request})
        return Response({
            "count": queryset.count(),
            "products": serializer.data
        }, status=status.HTTP_200_OK)


