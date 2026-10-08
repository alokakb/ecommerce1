from django.contrib import admin

from cart.models import Cart, CartItem


# Register your models here.
@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Cart._meta.fields]

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CartItem._meta.fields]



