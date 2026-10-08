from django.contrib import admin

from idempotency.models import IdempotencyRecord

# Register your models here.
@admin.register(IdempotencyRecord)
class IdempotencyRecordAdmin(admin.ModelAdmin):
    list_display = [field.name for field in IdempotencyRecord._meta.fields]
