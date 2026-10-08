from rest_framework import serializers

from products.models import Category, Product, ProductVariant

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

