from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0007_paymentevent"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(
                    name="PaymentEvent",
                ),
            ],
        ),
    ]