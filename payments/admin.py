from django.contrib import admin

from payments.models import PaymentEvent


# Register your models here.
@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = [field.name for field in PaymentEvent._meta.fields]
