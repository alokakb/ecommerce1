from rest_framework import serializers

from products.models import Category, Product, ProductVariant

# Related to Public customer storefront

class CategorySerializer(serializers.ModelSerializer):
    # Self-nested field to display subcategories
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'parent',
            'filterable_attributes',
            'children'
        ]
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

    class Meta:
        model = Product
        fields = [
            'id',
            'category',
            'category_name',
            'name',
            'slug',
            'base_price',
            'main_img'
        ]

class ProductDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    variant = ProductVariantSerializer(many=True, read_only=True)

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
            'variants'  # Array of all available sizes/colors
        ]

# Related to Vendor Dashboard
class SellerProductVariantCreationSerializer(serializers.ModelSerializer):
    """Handles incoming variant formats directly under the parent creation structure"""
    class Meta:
        model = ProductVariant
        fields = ['sku', 'attributes', 'price_override', 'stock_quantity', 'low_stock_threshold']

class SellerProductCreationSerializer(serializers.ModelSerializer):
    """Handles nested insertion validation for entire multi-tenant creation flow"""

    variations = SellerProductVariantCreationSerializer(many=True)

    class Meta:
        model = Product
        fields = [
            'category', 'name', 'description', 'base_price',
            'main_image', 'specifications', 'variations'
        ]

    def validate_variations(self, value):
        if not value:
            raise serializers.ValidationError({'The product must be listed with at least one variant configurations'})
        return value

