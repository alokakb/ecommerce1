from rest_framework import serializers

from products.models import Category


class AdminCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'parent',
            'filterable_attributes',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'created_at' 'updated_at']

    def validate_parent(self, parent):
        # 1. prevent the category from becoming its own parent
        if self.instance and parent:
            if parent.id == self.instance.id:
                raise serializers.ValidationError("A category cannot be its own parent")

        # 2. prevent category to placed under any of its descendants
        current = parent
        while current:
            if current.id == self.instance.id:
                raise serializers.ValidationError("A category cannot be its own parent")
            current = current.parent

        return parent