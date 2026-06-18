from django.db import models

# Create your models here.
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db import transaction as db_transaction


class Wallet(models.Model):
    """
    One wallet per user. Stores current usable balance.
    Never update balance directly — always use .credit() or .debit()
    so a transaction record is always created automatically.
    """
    user    = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wallet',
    )
    balance    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} — ₹{self.balance}"

    def credit(self, amount, reason, order=None):
        """
        Add money to wallet.
        Always use this — never update balance directly.
        Creates a WalletTransaction record automatically.
        """
        with db_transaction.atomic():
            self.balance += amount
            self.save(update_fields=['balance', 'updated_at'])
            WalletTransaction.objects.create(
                wallet           = self,
                amount           = amount,
                transaction_type = 'credit',
                reason           = reason,
                order            = order,
            )

    def debit(self, amount, reason, order=None):
        """
        Deduct money from wallet.
        Raises ValueError if balance is insufficient.
        """
        if amount > self.balance:
            raise ValueError(
                f"Insufficient wallet balance. "
                f"Available: ₹{self.balance}, Required: ₹{amount}"
            )
        with db_transaction.atomic():
            self.balance -= amount
            self.save(update_fields=['balance', 'updated_at'])
            WalletTransaction.objects.create(
                wallet           = self,
                amount           = amount,
                transaction_type = 'debit',
                reason           = reason,
                order            = order,
            )

    @property
    def total_credited(self):
        from django.db.models import Sum
        result = self.transactions.filter(
            transaction_type='credit'
        ).aggregate(total=Sum('amount'))['total']
        return result or 0

    @property
    def total_debited(self):
        from django.db.models import Sum
        result = self.transactions.filter(
            transaction_type='debit'
        ).aggregate(total=Sum('amount'))['total']
        return result or 0


class WalletTransaction(models.Model):
    """
    Every credit or debit creates one record here.
    Think of it as a bank passbook — never edit or delete these.
    """
    TRANSACTION_TYPE_CHOICES = [
        ('credit', 'Credit'),  # money IN  — refunds, referral rewards
        ('debit',  'Debit'),   # money OUT — used at checkout
    ]

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='transactions',
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wallet_transactions',
    )
    amount           = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    reason           = models.CharField(max_length=255)
    created_at       = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']  # newest first — like a bank statement

    def __str__(self):
        symbol = '+' if self.transaction_type == 'credit' else '-'
        return f"{symbol}₹{self.amount} — {self.reason}"