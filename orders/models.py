from django.db import models
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.crypto import get_random_string

User = get_user_model()

# Create your models here.

# New : Version 2 of Order Model
class Order(models.Model):

    ORDER_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('abandoned', 'Abandoned')
    )

    order_no = models.CharField(max_length=20, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # Order lifecycle
    order_status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')

    # Financial snapshot
    # Financial
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # discounts
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    # Promo
    coupon_code = models.CharField(max_length=50, blank=True, null=True)

    # Shipping snapshot
    shipping_full_name = models.CharField(max_length=255)
    shipping_phone_number = models.CharField(max_length=20)
    shipping_address_line_1 = models.CharField(max_length=255)
    shipping_address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_postal_code = models.CharField(max_length=20)
    shipping_country = models.CharField(max_length=100)

    # Fulfillment
    # Shipping/Logistics
    shipping_carrier = models.CharField(max_length=50, blank=True, null=True, help_text="DHL, FedEx, BlueDart etc")
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    estimated_delivery = models.DateField(blank=True, null=True)

    # 1. Currency Isolation
    currency = models.CharField(max_length=3, default='INR', help_text="ISO currency code")
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=6, default=1.000000,
                                        help_text="Exchange rate relative to base system currency at checkout")

    # 2. Tax Auditing Metadata
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax_identifier = models.CharField(max_length=50, blank=True, null=True,
                                      help_text="e.g., Customer's VAT registration number or Tax exemption ID")

    # 3. Security, Fraud, & Operations Tracking
    ip_address = models.GenericIPAddressField(blank=True, null=True,
                                              help_text="IP address used to place the order")
    user_agent = models.TextField(blank=True, null=True,
                                  help_text="Browser/Device used during checkout")

    # 4. Timeline Metrics (Beyond just created_at)
    # Essential for logistics tracking (e.g., SLA agreements, fulfillment speed analysis)
    payment_received_at = models.DateTimeField(blank=True, null=True)
    shipped_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    # Auto order_no generator
    def save(self, *args, **kwargs):
        if not self.order_no:
            from datetime import datetime
            year = datetime.now().year
            self.order_no = f"SHOP-{year}-{get_random_string(6).upper()}"

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.add("updated_at")
            kwargs["update_fields"] = update_fields

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.order_no} : {self.order_status}"



class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    # product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='order_items')
    variant = models.ForeignKey('products.ProductVariant', on_delete=models.PROTECT, related_name='order_item_variant')

    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)
    # quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    # Production Quantity counters
    quantity_ordered = models.PositiveIntegerField(default=1, help_text='units customer paid for')
    quantity_shipped = models.PositiveIntegerField(default=0, help_text='units actually left the fulfillment warehouse')
    quantity_returned = models.PositiveIntegerField(default=0, help_text='units sent back and processed for return')

    # Warehouse Metadata
    sku_at_purchase = models.CharField(max_length=100, blank=True, null=True)

    # Properties
    @property
    def is_partially_returned(self):
        return 0 < self.quantity_returned < self.quantity_ordered

    @property
    def is_fully_returned(self):
        return self.quantity_returned == self.quantity_ordered

    @property
    def net_quantity_retained(self):
        return self.quantity_ordered - self.quantity_returned

    @property
    def net_line_total(self):
        return self.net_quantity_retained * self.price_at_purchase


    def __str__(self):
        return f"{self.quantity_ordered} X {self.sku_at_purchase}"





# Older : Version 1 of Order Model
# class Order(models.Model):
#     ORDER_STATUS_CHOICES = (
#         ('pending', 'Pending'),
#         ('paid','Paid'),
#         ('shipped', 'Shipped'),
#         ('delivered', 'Delivered'),
#         ('cancelled', 'Cancelled'),
#     )
#
#     PAYMENT_STATUS_CHOICES = (
#         ('unpaid', 'Unpaid'),
#         ('authorized', 'Authorized'),
#         ('captured', 'Captured / Success'),
#         ('failed', 'Failed'),
#     )
#
#     REFUND_STATUS_CHOICES = (
#         ('not_requested', 'Not Requested'),
#         ('created', 'Created'),
#         ('success', 'Success'),
#         ('failed', 'Failed'),
#     )
#
#     order_no = models.CharField(max_length=20, unique=True, editable=False)
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     order_status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')
#
#     # Financial
#     subtotal = models.DecimalField(max_digits=10, decimal_places=2)
#     shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
#
#     # discounts
#     discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
#     total_amount = models.DecimalField(max_digits=10, decimal_places=2)
#
#     # Promo
#     coupon_code = models.CharField(max_length=50, blank=True, null=True)
#
#     # Payment
#     payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
#     payment_method = models.CharField(max_length=50, blank=True, null=True, help_text="e.g., Stripe, PayPal, Razorpay")
#     gateway_order_id = models.CharField(max_length=50, blank=True, null=True, unique=True, help_text="The ID returned by payment gateway like razorpay, stripe for this transaction")
#     gateway_payment_id = models.CharField(max_length=50, blank=True, null=True, unique=True, help_text="The Payment ID returned by payment gateway like razorpay, stripe for this transaction")
#
#     # Refund
#     refund_status = models.CharField(max_length=20, choices=REFUND_STATUS_CHOICES, default='not_requested')
#     refund_id = models.CharField(max_length=50, blank=True, null=True, unique=True, help_text="The Refund ID returned by payment gateway like razorpay, stripe for this transaction")
#
#     # Shipping/Logistics
#     shipping_carrier = models.CharField(max_length=50, blank=True, null=True, help_text="DHL, FedEx, BlueDart etc")
#     tracking_number = models.CharField(max_length=100, blank=True, null=True)
#     estimated_delivery = models.DateField(blank=True, null=True)
#
#     # Existing Address
#     shipping_full_name = models.CharField(max_length=255)
#     shipping_phone_number = models.CharField(max_length=20)
#     shipping_address_line_1 = models.CharField(max_length=255)
#     shipping_address_line_2 = models.CharField(max_length=255, blank=True, null=True)
#     shipping_city = models.CharField(max_length=100)
#     shipping_state = models.CharField(max_length=100)
#     shipping_postal_code = models.CharField(max_length=20)
#     shipping_country = models.CharField(max_length=100)
#
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#
#     # 1. Currency Isolation
#     currency = models.CharField(max_length=3, default='INR', help_text="ISO currency code")
#     exchange_rate = models.DecimalField(max_digits=10, decimal_places=6, default=1.000000,
#                                         help_text="Exchange rate relative to base system currency at checkout")
#
#     # 2. Tax Auditing Metadata
#     tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
#     tax_identifier = models.CharField(max_length=50, blank=True, null=True,
#                                       help_text="e.g., Customer's VAT registration number or Tax exemption ID")
#
#     # 3. Security, Fraud, & Operations Tracking
#     ip_address = models.GenericIPAddressField(blank=True, null=True,
#                                               help_text="IP address used to place the order")
#     user_agent = models.TextField(blank=True, null=True,
#                                   help_text="Browser/Device used during checkout")
#
#     # 4. Timeline Metrics (Beyond just created_at)
#     # Essential for logistics tracking (e.g., SLA agreements, fulfillment speed analysis)
#     payment_received_at = models.DateTimeField(blank=True, null=True)
#     shipped_at = models.DateTimeField(blank=True, null=True)
#     delivered_at = models.DateTimeField(blank=True, null=True)
#     cancelled_at = models.DateTimeField(blank=True, null=True)
#
#     class Meta:
#         ordering = ['-created_at']
#
#     # Auto order_no generator
#     def save(self, *args, **kwargs):
#         if not self.order_no:
#             from datetime import datetime
#             year = datetime.now().year
#             self.order_no = f"SHOP-{year}-{get_random_string(6).upper()}"
#         super().save(*args, **kwargs)
#
#     def __str__(self):
#         return f"Order {self.order_no} : {self.order_status}"








