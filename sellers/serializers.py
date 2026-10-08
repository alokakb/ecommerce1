from django.contrib.auth import get_user_model
from rest_framework import serializers
from django.db import transaction

from sellers.models import SellerProfile

User = get_user_model()

class SellerRegistrationSerializer(serializers.Serializer):
    # Core Authentication Account Fields
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    first_name = serializers.CharField(max_length=150, required=True)
    last_name = serializers.CharField(max_length=150, required=True)

    # Multi-Tenant Business Profile Fields
    business_name = serializers.CharField(max_length=255)
    tax_id_number = serializers.CharField(max_length=50)
    bank_account_token = serializers.CharField(max_length=255)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("Business Email is already registered")
        return value.lower()

    def validate_business_name(self, value):
        if SellerProfile.objects.filter(business_name=value).exists():
            raise serializers.ValidationError("Business Name is already registered")
        return value

    def create(self, validated_data):
        # Extract business fields away from the core account fields
        business_name = validated_data.pop('business_name')
        tax_id_number = validated_data.pop('tax_id_number')
        bank_account_token = validated_data.pop('bank_account_token')
        password = validated_data.pop('password')

        print(f"DEBUGGING VALUES -> Business Name: {business_name}")

        # Transaction safety lock
        with transaction.atomic():
            # 1. Create the core login credentials row
            user = User.objects.create_user(
                password=password,
                **validated_data
            )

            # 2. Create the business profile configuration details row
            SellerProfile.objects.create(
                user=user,
                business_name=business_name,
                tax_id_number=tax_id_number,
                bank_account_token=bank_account_token,
                is_verified=False,
            )
        return user