from django.db import models
from orders.models import Order

# Create your models here.

class PaymentEvent(models.Model):
    event_id = models.CharField(max_length=50, unique=True)
    provider = models.CharField(max_length=50)
    event_type = models.CharField(max_length=100)
    order = models.ForeignKey(Order, on_delete=models.PROTECT)
    processed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'orders_paymentevent'
