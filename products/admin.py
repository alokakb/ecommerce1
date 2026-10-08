from dataclasses import field

from django.contrib import admin

from orders.models import Order
from products.models import Product, Category, ProductVariant


# Register your models here.
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Product._meta.fields]

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Category._meta.fields]

@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = [field.name for field in ProductVariant._meta.fields]

