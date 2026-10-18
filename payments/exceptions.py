
class InsufficientStockError(Exception):

    def __init__(self, variant_id, requested_quantity):
        self.variant_id = variant_id
        self.requested_quantity = requested_quantity
        super().__init__(f"Insufficient stock for {self.variant_id}")

class ConfigurationError(Exception):
    """Raised when required payment gateway configuration is missing."""
    pass
