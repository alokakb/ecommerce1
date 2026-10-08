from decimal import Decimal

# Simple logic for now
def calculate_discount(total_price: Decimal, coupon_code: str) -> Decimal:
    if coupon_code is None:
        return Decimal(0.00)