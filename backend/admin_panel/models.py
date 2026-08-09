from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


def user_list(request):
    users = User.objects.all()


class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def display_status(self):
        if getattr(self, "is_blocked", False):
            return "Blocked"
        if not getattr(self, "is_verified", True):
            return "Pending"
        return "Active"


class SiteSettings(models.Model):

    customization_fee = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=49,
        help_text="Fee charged when a customer adds custom text or image to a product.",
    )

    referral_enabled = models.BooleanField(
        default=True,
        help_text="Master on/off switch for the referral program. "
        "When off, new signups do not earn referral credit and "
        "no new referrals are recorded. Existing referrals are "
        "still honoured.",
    )
    referrer_reward_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("50.00"),
        help_text="Wallet credit given to the REFERRER after the person "
        "they invited places their first order. Amount is locked "
        "onto each referral when it is created.",
    )
    referred_reward_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("100.00"),
        help_text="Wallet credit given to the NEW USER immediately when they "
        "sign up using a valid referral code.",
    )

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return "Site Settings"

    def save(self, *args, **kwargs):

        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):

        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
