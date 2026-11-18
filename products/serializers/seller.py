from rest_framework import serializers

from products.models import Category, Product, ProductVariant
from products.utils.dict_utils import deep_merge

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


class SellerProductUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'category',
            'name',
            'description',
            'base_price',
            'main_image',
            'specifications',
        ]

class SellerProductVariantUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = [
            'attributes', 'price_override', 'low_stock_threshold'
        ]

    def validate_low_stock_threshold(self, value):
        if value < 1:
            raise serializers.ValidationError({'Product low_stock_threshold must be greater than or equal to 1'})
        return value

    def update(self, instance, validated_data):
        incoming_attributes = validated_data.pop('attributes')

        if incoming_attributes is not None:
            instance.attributes = {
                **(instance.attributes or {}),
                **incoming_attributes
            }

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance










