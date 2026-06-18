from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from products.models import Product, Category


class ProductOffer(models.Model):
    product          = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='offer')
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2)
    is_active        = models.BooleanField(default=True)
    start_date       = models.DateField()
    end_date         = models.DateField()
    created_at       = models.DateTimeField(default=timezone.now)

    def clean(self):
        errors = {}

        if self.discount_percent is not None and not (0 < self.discount_percent <= 90):
            errors['discount_percent'] = 'Discount must be between 1% and 90%.'

        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                errors['end_date'] = 'End date must be after start date.'

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} — {self.discount_percent}% off"


class CategoryOffer(models.Model):
    category         = models.OneToOneField(Category, on_delete=models.CASCADE, related_name='offer')
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2)
    is_active        = models.BooleanField(default=True)
    start_date       = models.DateField()
    end_date         = models.DateField()
    created_at       = models.DateTimeField(default=timezone.now)

    def clean(self):
        errors = {}

        if self.discount_percent is not None and not (0 < self.discount_percent <= 90):
            errors['discount_percent'] = 'Discount must be between 1% and 90%.'

        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                errors['end_date'] = 'End date must be after start date.'

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.category.name} — {self.discount_percent}% off"