from dataclasses import field

from django.contrib import admin

from orders.models import Order, OrderItem, Payment, Refund


# Register your models here.
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Order._meta.fields]

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Payment._meta.fields]

@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Refund._meta.fields]

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = [field.name for field in OrderItem._meta.fields]

