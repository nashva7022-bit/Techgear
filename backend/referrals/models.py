from django.db import models

# Create your models here.
import random
import string
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

REFERRER_REWARD = Decimal('50.00')
REFERRED_REWARD = Decimal('100.00')

def generate_referral_code():
   
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=8))

class ReferralCode(models.Model):
   
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_code',
    )
    code = models.CharField(max_length=10, unique=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Referral Code'
        verbose_name_plural = 'Referral Codes'

    def __str__(self):
        return f"{self.user.email} — {self.code}"


class ReferralUsage(models.Model):
    
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_made',
    )
    referred_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_usage',
    )
    referrer_rewarded = models.BooleanField(default=False)
    referrer_reward_amount = models.DecimalField(
        max_digits=8, decimal_places=2, default=REFERRER_REWARD
    )
    referred_reward_amount = models.DecimalField(
        max_digits=8, decimal_places=2, default=REFERRED_REWARD
    )
    created_at = models.DateTimeField(default=timezone.now)
    rewarded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Referral Usage'
        verbose_name_plural = 'Referral Usages'

    def __str__(self):
        referrer_email = self.referrer.email if self.referrer else 'Deleted User'
        return f"{referrer_email} → {self.referred_user.email}"