from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from products.models import Category, Product


class ProductOffer(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="offers"
    )
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2)
    is_active = models.BooleanField(default=True)
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(default=timezone.now)

    def clean(self):
        errors = {}

        if self.discount_percent is not None and not (0 < self.discount_percent <= 90):
            errors["discount_percent"] = "Discount must be between 1% and 90%."

        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                errors["end_date"] = "End date must be after start date."

        # Check for overlapping dates on same product
        if self.product and self.start_date and self.end_date:
            overlapping = ProductOffer.objects.filter(
                product=self.product, is_active=True
            ).exclude(pk=self.pk)

            for offer in overlapping:
                # Check if dates overlap
                if not (
                    self.end_date < offer.start_date or self.start_date > offer.end_date
                ):
                    errors["start_date"] = (
                        f"Offer dates overlap with existing offer from {offer.start_date} to {offer.end_date}."
                    )
                    break

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} — {self.discount_percent}% off ({self.start_date} to {self.end_date})"


class CategoryOffer(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="offers"
    )
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2)
    is_active = models.BooleanField(default=True)
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(default=timezone.now)

    def clean(self):
        errors = {}

        if self.discount_percent is not None and not (0 < self.discount_percent <= 90):
            errors["discount_percent"] = "Discount must be between 1% and 90%."

        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                errors["end_date"] = "End date must be after start date."

        # Check for overlapping dates on same category
        if self.category and self.start_date and self.end_date:
            overlapping = CategoryOffer.objects.filter(
                category=self.category, is_active=True
            ).exclude(pk=self.pk)

            for offer in overlapping:
                # Check if dates overlap
                if not (
                    self.end_date < offer.start_date or self.start_date > offer.end_date
                ):
                    errors["start_date"] = (
                        f"Offer dates overlap with existing offer from {offer.start_date} to {offer.end_date}."
                    )
                    break

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.category.name} — {self.discount_percent}% off ({self.start_date} to {self.end_date})"
