import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("orders", "0008_delete_paymentevent"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="PaymentEvent",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        (
                            "event_id",
                            models.CharField(
                                max_length=50,
                                unique=True,
                            ),
                        ),
                        (
                            "provider",
                            models.CharField(max_length=50),
                        ),
                        (
                            "event_type",
                            models.CharField(max_length=100),
                        ),
                        (
                            "processed_at",
                            models.DateTimeField(
                                blank=True,
                                null=True,
                            ),
                        ),
                        (
                            "created_at",
                            models.DateTimeField(
                                auto_now_add=True,
                            ),
                        ),
                        (
                            "order",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.PROTECT,
                                to="orders.order",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "orders_paymentevent",
                    },
                ),
            ],
        ),
    ]