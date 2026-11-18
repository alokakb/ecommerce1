import hashlib
import json

from django.core.cache import cache
from django.db.models import Prefetch
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.generics import RetrieveAPIView, ListAPIView
from rest_framework.response import Response
from rest_framework import status
import logging
from products.models import Product, Category
from products.serializers.public import (CategorySerializer, ProductListSerializer,
                                         ProductDetailSerializer, GlobalMenuCategorySerializer)
from products.services.cache_service import get_product_search_version
from products.services.category_tree import CategoryTreeService

from core.cache_monitoring import monitored_cache_get, monitored_cache_set

logger = logging.getLogger(__name__)

class GlobalMenuAPIView(APIView):
    permission_classes = [AllowAny]

    CACHE_KEY = 'catalog:global_menu:v1'
    CACHE_TTL = 60
    API_NAME = 'global_menu_v1'
    def get(self, request):
        # cached_menu = cache.get(self.CACHE_KEY)
        cached_menu = monitored_cache_get(api_name=self.API_NAME, cache_key=self.CACHE_KEY)

        if cached_menu is not None:
            logger.info("GLOBAL MENU: Serving data from Redis cache")
            return Response(cached_menu, status=status.HTTP_200_OK)

        logger.info("GLOBAL MENU: Cache MISS. Fetching data from PostgreSQL")

        root_categories = Category.objects.filter(parent=None, is_active=True).prefetch_related(
            Prefetch(
                'children',
                queryset=Category.objects.filter(is_active=True),
                to_attr='active_children',
            )
        )
        serializer = GlobalMenuCategorySerializer(root_categories, many=True)
        menu_data = serializer.data
        # cache.set(self.CACHE_KEY, menu_data, self.CACHE_TTL)
        monitored_cache_set(api_name=self.API_NAME, cache_key=self.CACHE_KEY,
                            value=menu_data, timeout=self.CACHE_TTL)
        logger.info("GLOBAL MENU: Data fetched from PostgreSQL and stored in Redis")
        return Response(menu_data, status=status.HTTP_200_OK)


class CategoryDrillDownAPIView(APIView):
    """Dynamic catalog Navigator. Resolves whether to return subcategories
        or start streaming products depending on the tree structure"""
    permission_classes = [AllowAny]
    CACHE_TTL = 60
    API_NAME = 'category_drill_down_v1'

    def get(self, request, category_id=None):

        # check frontend override flag
        force_show_products = request.query_params.get('show_products').lower() == 'true' \
            if 'show_products' in request.query_params else False

        cache_key = (
            f'catalog:category_drill_down_{category_id}:'
            f'show_products_{force_show_products}:v1'
        )
        # cached_menu = cache.get(CACHE_KEY)
        cached_menu = monitored_cache_get(api_name=self.API_NAME, cache_key=cache_key)

        if cached_menu is not None:
            logger.info("CATEGORY DRILLDOWN V1: Serving data from Redis cache")
            return Response(cached_menu, status=status.HTTP_200_OK)

        logger.info("CATEGORY DRILLDOWN V1: Cache MISS. Fetching data from PostgreSQL")

        # 1. Landing page / Root Level
        if category_id is None:
            root_categories = Category.objects.filter(parent=None)
            serializer = CategorySerializer(root_categories, many=True)
            menu_data = {
                "view_type": "ROOT_CATEGORIES",
                "categories": serializer.data
            }
            # cache.set(cache_key, menu_data, self.CACHE_TTL)
            monitored_cache_set(api_name=self.API_NAME, cache_key=cache_key,
                                value=menu_data, timeout=self.CACHE_TTL)
            logger.info("CATEGORY DRILLDOWN V1: Data fetched from PostgreSQL and stored in Redis")
            return Response(menu_data, status=status.HTTP_200_OK)

        # 2. Category Drilldown
        try:
            current_category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return Response({"Error": "Category not found"}, status=status.HTTP_404_NOT_FOUND)

        # 3. Subcategories living underneath the category
        child_categories = current_category.children.filter(is_active=True)

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
            products = Product.objects.filter(category_id__in=all_target_ids, is_active=True).order_by('-id')
            response_data["products"] = ProductListSerializer(products, many=True, context={'request': request}).data

        # Condition B: No child categories exists anymore,show products related to the leaf node
        elif not child_categories.exists():
            response_data["view_type"] = "PRODUCT_LISTING"

            # Fetch Products belonging directly to this leaf category
            products = Product.objects.filter(category=current_category, is_active=True).order_by('-id')
            response_data["products"] = ProductListSerializer(products, many=True).data

        # Condition C: Standard dill-down mode
        else:
            response_data["sub_categories"] = CategorySerializer(child_categories, many=True).data

        menu_data = response_data
        # cache.set(cache_key, menu_data, self.CACHE_TTL)
        monitored_cache_set(api_name=self.API_NAME, cache_key=cache_key,
                            value=menu_data, timeout=self.CACHE_TTL)
        logger.info("CATEGORY DRILLDOWN V1: Data fetched from PostgreSQL and stored in Redis")
        return Response(response_data, status=status.HTTP_200_OK)



class ProductDetailAPIView(RetrieveAPIView):
    """Returns detailed product data along with the nested variations"""
    queryset = Product.objects.all()
    serializer_class = ProductDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = 'id'

    CACHE_TTL = 60
    API_NAME = 'product_detail_v1'
    def retrieve(self, request, *args, **kwargs):
        product_id = kwargs.get(self.lookup_field, None)
        cache_key = f"catalog:product_detail:{product_id}:v1"

        # cache_menu = cache.get(cache_key)
        cache_menu = monitored_cache_get(api_name=self.API_NAME, cache_key=cache_key)

        if cache_menu is not None:
            logger.info("PRODUCT DETAIL PRODUCT_ID=%s V1: Serving data from Redis cache", product_id)
            return Response(cache_menu, status=status.HTTP_200_OK)

        logger.info("PRODUCT DETAIL PRODUCT_ID=%s V1: Cache MISS. Fetching data from PostgreSQL")

        response = super().retrieve(request, *args, **kwargs)
        if response.status_code == 200:
            # cache.set(cache_key, response.data, self.CACHE_TTL)
            monitored_cache_set(api_name=self.API_NAME, cache_key=cache_key,
                                value=response.data, timeout=self.CACHE_TTL)

        return response


class ProductSearchFilterAPIView(APIView):
    permission_classes = [AllowAny]

    CACHE_TTL = 60
    API_NAME = 'product_search_filter_v1'
    def get(self, request):
        version = get_product_search_version()

        normalized_params = sorted(
            (key, sorted(value))
            for key, value in request.query_params.lists()
        )
        filters_json = json.dumps(
            normalized_params,
            separators=(',', ':'),
            ensure_ascii=True
        )
        filter_hash= hashlib.sha256(
            filters_json.encode('utf-8')
        ).hexdigest()

        cache_key = f"catalog:product_search_filter:version:v{version}:{filter_hash}"
        # cache_menu = cache.get(cache_key)
        cache_menu = monitored_cache_get(api_name=self.API_NAME, cache_key=cache_key)

        if cache_menu is not None:
            logger.info("PRODUCT SEARCH FILTER : Serving data from Redis cache; version:%s", version)
            return Response(cache_menu, status=status.HTTP_200_OK)

        logger.info("PRODUCT SEARCH FILTER : Cache MISS. Fetching data from PostgreSQL: version:%s", version)

        target_category_id = request.query_params.get('category')
        queryset = Product.objects.filter(is_active=True).order_by('-id')

        if target_category_id:
            try:
                target_category = Category.objects.get(id=target_category_id, is_active=True)
                all_target_ids = CategoryTreeService.get_all_descendant_ids(target_category)
                queryset = queryset.filter(category_id__in=all_target_ids, is_active=True)
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
        menu_data = {
            "count": queryset.count(),
            "products": serializer.data
        }
        # cache.set(cache_key, menu_data, self.CACHE_TTL)
        monitored_cache_set(api_name=self.API_NAME, cache_key=cache_key,
                            value=menu_data, timeout=self.CACHE_TTL)
        return Response(menu_data, status=status.HTTP_200_OK)


