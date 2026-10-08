from django.db import models
# from django.contrib.auth.models import User
from django.contrib.auth import get_user_model

User = get_user_model()

# Create your models here.
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, blank=True, null=True)
    dob = models.DateField(blank=True,null=True)
    contact_number = models.CharField(blank=True, null=True)

class Address(models.Model):
    ADDRESS_TYPES = (('shipping', 'Shipping Address'), ('billing', 'Billing Address'))

    # Relation
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # Details
    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPES, default='shipping')
    full_name = models.CharField(max_length=255, help_text='Recipient Name')
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state_province = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=100)
    country = models.CharField(max_length=100)

    # Prod
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Addresses'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name}{self.city}{self.country}"




