from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

# Create your models here.
class IdempotencyRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    idempotency_key = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=[
            ("processing", "Processing"),
            ("completed", "Completed"),
        ],
    )
    order = models.OneToOneField(
        'orders.Order',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "idempotency_key"],
                name="unique_user_idempotency_key",
            )
        ]
