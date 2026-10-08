from rest_framework import serializers
from .models import Order, OrderItem

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            'id',
            'product',
            'price_at_purchase',
            'quantity_ordered',
            'quantity_returned',
            # properties for API fields!
            'is_partially_returned',
            'net_quantity_retained',
            'net_line_total'
        ]

class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = '__all__'

