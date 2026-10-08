from django.contrib.postgres.indexes import GinIndex
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify


# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)

    # self-reference
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children', on_delete=models.SET_NULL)
    filterable_attributes = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            if self.parent:
                self.slug = slugify(f"{self.parent.slug}-{self.name}")
            else:
                self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.parent.name} > {self.name}" if self.parent else self.name


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)

    # Baseline price
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    main_image = models.URLField(max_length=500, blank=True, null=True)

    # Global Attribute
    specifications = models.JSONField(default=dict, blank=True)

    seller = models.ForeignKey(
        'sellers.SellerProfile',
        on_delete=models.PROTECT, related_name='products',
        help_text="Tracks which Independent Store owns this listing",
        null=True,
        blank=True
    )

    # Soft Deletion
    is_active = models.BooleanField(default=True, help_text='uncheck to hide from Store')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variations')

    # physical stock Identifier
    sku = models.CharField(max_length=200, unique=True)
    attributes = models.JSONField(default=dict, blank=True)

    # Price Configuration of variant
    price_override = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text='Mention to Override price or leave blank to inherit the base price')

    # Inventory
    stock_quantity = models.PositiveIntegerField(default=0, validators = [MinValueValidator(0)])
    low_stock_threshold = models.PositiveIntegerField(default=5)

    class Meta:
        indexes = [
            GinIndex(fields=['attributes'], name='variant_attributes_gin_index'),
        ]
    @property
    def price(self):
        return self.price_override if self.price_override else self.product.base_price

    @property
    def is_in_stock(self):
        return self.stock_quantity > 0

    def __str__(self):
        return f"{self.product.name} {self.sku}"