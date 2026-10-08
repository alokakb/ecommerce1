from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()
# Create your models here.
class SellerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='seller_profile')
    business_name = models.CharField(max_length=255, unique=True)
    store_description = models.TextField(blank=True, null=True)
    tax_id_number = models.CharField(max_length=100, help_text="EIN, VAT or local business registration ID")
    bank_account_token = models.CharField(max_length=255, help_text="payout routing anchor (e.g., Stripe connect ID")

    # Set -> true for own administrative profile / false for 3rd party vendors
    is_internal = models.BooleanField(default=False)

    is_verified = models.BooleanField(default=False, help_text="Is the seller's account verified")
    created_at = models.DateTimeField(auto_now_add=True)

    # check if we can update some info in this model as well

    def __str__(self):
        return self.business_name

