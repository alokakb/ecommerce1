from django.contrib import admin

from payments.models import PaymentEvent, Payment, Refund, OutboxEvent


# Register your models here.
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Payment._meta.fields]

@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Refund._meta.fields]

@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = [field.name for field in PaymentEvent._meta.fields]

@admin.register(OutboxEvent)
class OutboxEventAdmin(admin.ModelAdmin):
    list_display = [field.name for field in OutboxEvent._meta.fields]


