from django.contrib import admin
from sellers.models import SellerProfile

from django.contrib import messages


# Register your models here.
@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = [field.name for field in SellerProfile._meta.fields]

    actions = ['verify_sellers', 'unverify_sellers', 'mark_as_internal']

    @admin.action(description='Verify selected Sellers')
    def verify_sellers(self, request, queryset):
        updated_count = queryset.update(is_verified=True)

        # Display success alert banner
        self.message_user(
            request,
            f"Successfully verified {updated_count} seller profiles",
            messages.SUCCESS
        )

    @admin.action(description='Unverify selected Sellers')
    def unverify_sellers(self, request, queryset):
        updated_count = queryset.update(is_verified=False)
        self.message_user(
            request,
            f"Successfully unverified {updated_count} seller profiles",
            messages.SUCCESS
        )

    @admin.action(description='Mark selected Internal Corporate Account')
    def mark_as_internal(self, request, queryset):
        updated_count = queryset.update(mark_as_internal=True)
        self.message_user(
            request,
            f"Successfully marked {updated_count} seller profiles as internal",
            messages.SUCCESS
        )


