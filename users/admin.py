from django.contrib import admin

from users.models import Profile, Address


# Register your models here.
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Profile._meta.fields]

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Address._meta.fields]

