from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models

User = get_user_model()

# Create your models here.
class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='cart')

    # Guest Session Tracking
    session_id = models.CharField(max_length=255, null=True, blank=True, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_price(self):
        """Dynamic current total price"""
        return sum(item.subtotal for item in self.items.all())

    def __str__(self):
        return f"Cart for {self.user.email if self.user else f'Guest Session {self.session_id}'}"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey('products.ProductVariant', on_delete=models.CASCADE, related_name='cart_items')

    quantity = models.PositiveIntegerField(default=1, validators = [MinValueValidator(1)])

    class Meta:
        unique_together = ('cart', 'variant')

    @property
    def subtotal(self):
        return self.variant.price * self.quantity

    def __str__(self):
        return f"{self.quantity} X {self.variant.sku}"
