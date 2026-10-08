from rest_framework import serializers

from products.models import Category, Product, ProductVariant

# Related to Public customer storefront

class CategorySerializer(serializers.ModelSerializer):
    """
    1. BASE/FLAT SERIALIZER
    For high performance step by step drill-downs
    No recursive data loops
    """
    class Meta:
        model = Category
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'parent',
            'filterable_attributes',
        ]

class GlobalMenuCategorySerializer(CategorySerializer):
    """
    1. NESTED / GLOBAL MENU SERIALIZER
    """

    # Self-nested field to display subcategories
    children = serializers.SerializerMethodField()

    class Meta(CategorySerializer.Meta):
        fields = CategorySerializer.Meta.fields + ['children']

    def get_children(self, obj):
        active_children = obj.children.filter(is_active=True)
        return CategorySerializer(active_children, many=True).data


class ProductVariantSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    class Meta:
        model = ProductVariant
        fields = [
            'id',
            'sku',
            'attributes',
            'price',
            'is_in_stock',
            'stock_quantity',
        ]

class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    specifications = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id',
            'category',
            'category_name',
            'name',
            'slug',
            'base_price',
            'main_image',
            'specifications'
        ]

    def get_specifications(self, obj):
        full_specs = obj.specifications or {}

        # check if the view passed the request in context to look for a layout parameter
        request = self.context.get('request')
        short_version = request.query_params.get('spec_layout').lower() == 'short' \
            if 'spec_layout' in request.query_params else False

        # If frontend request the short preview, give first 2 specifications
        if short_version and len(full_specs) > 2:
            sliced_keys = list(full_specs.keys())[:2]
            return {key: full_specs[key] for key in sliced_keys}

        return full_specs




class ProductDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    variations = ProductVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'category',
            'category_name',
            'name',
            'slug',
            'description',
            'base_price',
            'main_image',
            'specifications',  # Your global JSON specs field
            'variations'  # Array of all available sizes/colors
        ]
