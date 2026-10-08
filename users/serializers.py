from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers
from users.models import Profile, Address


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = '__all__'

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        with transaction.atomic():
            # 1. Create user
            user = User.objects.create_user(**validated_data)

            # 2. Explicitly create customer profiler for the user
            Profile.objects.create(user=user)

        return user

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = '__all__'
