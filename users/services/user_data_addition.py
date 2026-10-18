from django.db import models
from rest_framework import status
from rest_framework.response import Response

from users.models import Address

def address_data_addition(user, shipping_address):
    # ---------------------------------------------------------
    # 2. Validate shipping address before starting transaction
    # ---------------------------------------------------------
    address_query_set = Address.objects.filter(
        user=user,
        is_default=True
    ).values(
        shipping_full_name=models.F("full_name"),
        shipping_phone_number=models.F("phone_number"),
        shipping_address_line_1=models.F("address_line1"),
        shipping_address_line_2=models.F("address_line2"),
        shipping_city=models.F("city"),
        shipping_state=models.F("state_province"),
        shipping_postal_code=models.F("postal_code"),
        shipping_country=models.F("country"),
    )

    address_data = address_query_set.first()

    if not address_data:
        address_data = shipping_address

    if not address_data:
        return Response(
            {"error": "Shipping address is required."},
            status=status.HTTP_400_BAD_REQUEST
        )
    return address_data
