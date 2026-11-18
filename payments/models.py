import uuid

from django.db import models
from django.db.models import Q, JSONField

from orders.models import Order

# Create your models here.

class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = (
        ('unpaid', 'Unpaid'),
        ('authorized', 'Authorized'),
        ('captured', 'Captured / Success'),
        ('failed', 'Failed'),
    )

    PAYMENT_METHOD_CHOICES = (
        ('upi', 'UPI'),
        ('card', 'Card'),
        ('netbanking', 'Net Banking'),
        ('wallet', 'Wallet'),
    )

    PROVIDER_CHOICES = (
        ('razorpay', 'Razorpay'),
        ('stripe', 'Stripe'),
    )

    order = models.ForeignKey('orders.Order' , on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=10,decimal_places=2)
    currency = models.CharField(max_length=3,default='INR')
    provider = models.CharField(max_length=50,choices=PROVIDER_CHOICES)
    payment_method = models.CharField(max_length=50,choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20,choices=PAYMENT_STATUS_CHOICES,default='unpaid')
    gateway_order_id = models.CharField(max_length=100,blank=True,null=True,unique=True)
    gateway_payment_id = models.CharField(max_length=100,blank=True,null=True,unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    captured_at = models.DateTimeField(blank=True,null=True)

    # Here the constraint enforce : For a given Order,
    # the DB allows only one payment whose status is "pending"
    class Meta:
        db_table = "payments_payment"
        constraints = [
            models.UniqueConstraint(
                fields=["order"],
                condition=Q(status="unpaid"),
                name="one_unpaid_payment_per_order",
            )
        ]

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")

        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.add("updated_at")
            kwargs["update_fields"] = update_fields
        super().save(*args, **kwargs)


class Refund(models.Model):
    REFUND_STATUS_CHOICES = (
        ('created', 'Created'),
        ('processing', 'Processing'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    )

    payment = models.ForeignKey(Payment,on_delete=models.PROTECT,related_name='refunds')
    amount = models.DecimalField(max_digits=10,decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3,default='INR')
    status = models.CharField(max_length=20,choices=REFUND_STATUS_CHOICES,default='created')
    gateway_refund_id = models.CharField(max_length=100,blank=True,null=True,unique=True)
    reason = models.CharField(max_length=255,blank=True,null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(blank=True,null=True)

    class Meta:
        db_table = "payments_refund"
        constraints = [
            models.UniqueConstraint(
                fields=["payment"],
                condition=Q(status__in=["created", "processing"]),
                name="one_active_refund_per_payment"
            )
        ]

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")

        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.add("updated_at")
            kwargs["update_fields"] = update_fields
        super().save(*args, **kwargs)



class PaymentEvent(models.Model):
    event_id = models.CharField(max_length=50, unique=True)
    provider = models.CharField(max_length=50)
    event_type = models.CharField(max_length=100)
    order = models.ForeignKey(Order, on_delete=models.PROTECT)
    processed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'orders_paymentevent'



class OutboxEvent(models.Model):
    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    event_type = models.CharField(max_length=100)
    aggregate_id = models.CharField(max_length=100)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(blank=True, null=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, null=True)
    next_attempt_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event_type", "aggregate_id"],
                name="unique_event",
            )
        ]

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")

        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.add("updated_at")
            kwargs["update_fields"] = update_fields

        super().save(*args, **kwargs)




class ProcessedEvent(models.Model):
    event_id = models.UUIDField(unique=True)
    event_type = models.CharField(max_length=100)
    processed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_type} : {self.event_id}"

