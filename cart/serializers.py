from rest_framework import serializers
from products.serializers.public import ProductVariantSerializer
from products.models import ProductVariant
from .models import CartItem, Cart


class CartItemSerializer(serializers.ModelSerializer):
    variant = ProductVariantSerializer(read_only=True)

    variant_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.filter(product__is_active=True),
        source='variant',
        write_only=True
    )

    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ['variant', 'variant_id', 'quantity', 'subtotal']

    def validate(self, attrs):
        """Check if cart item is available/is in stock"""
        variant = attrs.get('variant')
        quantity = attrs.get('quantity', 1)

        if not variant.is_in_stock:
            raise serializers.ValidationError({"Stock": "This Product Variant is currently out of stock"})

        if quantity > variant.stock_quantity:
            raise serializers.ValidationError(
                {"Stock": f"Insufficient stock Only {variant.stock_quantity} units available"})

        return attrs

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(read_only=True, many=True)

    # model's dynamic total_price property
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    total_items_count = serializers.IntegerField(source='items.count', read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'user', 'items', 'total_price', 'total_items_count']





