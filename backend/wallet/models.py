from django.conf import settings
from django.db import models
from django.utils import timezone


class Wallet(models.Model):

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet",
    )
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} — ₹{self.balance}"

    def credit(self, amount, reason, order=None):

        self.balance += amount
        self.save(update_fields=["balance", "updated_at"])
        WalletTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type="credit",
            reason=reason,
            order=order,
        )

    def debit(self, amount, reason, order=None):

        if amount > self.balance:
            raise ValueError(
                f"Insufficient wallet balance. "
                f"Available: ₹{self.balance}, Required: ₹{amount}"
            )
        self.balance -= amount
        self.save(update_fields=["balance", "updated_at"])
        WalletTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type="debit",
            reason=reason,
            order=order,
        )

    @property
    def total_credited(self):
        from django.db.models import Sum

        result = self.transactions.filter(transaction_type="credit").aggregate(
            total=Sum("amount")
        )["total"]
        return result or 0

    @property
    def total_debited(self):
        from django.db.models import Sum

        result = self.transactions.filter(transaction_type="debit").aggregate(
            total=Sum("amount")
        )["total"]
        return result or 0


class WalletTransaction(models.Model):

    TRANSACTION_TYPE_CHOICES = [
        ("credit", "Credit"),  # money IN  — refunds, referral rewards
        ("debit", "Debit"),  # money OUT — used at checkout
    ]

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wallet_transactions",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    reason = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        symbol = "+" if self.transaction_type == "credit" else "-"
        return f"{symbol}₹{self.amount} — {self.reason}"
