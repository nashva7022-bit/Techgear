# =============================================================================
# FILE: referrals/services.py   (COMPLETE REPLACEMENT)
#
# What changed vs your version:
#   * validate_referral_code() now silently refuses NEW referrals when the
#     admin has turned the program OFF (SiteSettings.referral_enabled = False).
#   * apply_referral_on_signup() now reads the reward amounts from SiteSettings
#     (admin-configurable) instead of the hard-coded constants, and SNAPSHOTS
#     them onto the ReferralUsage row so later admin changes never rewrite
#     history.
#   * reward_referrer_on_first_order() is UNCHANGED in behaviour: it still pays
#     using the amount snapshotted on the row, so existing referrals are always
#     honoured even if the program is later disabled.
#
# The hard-coded REFERRER_REWARD / REFERRED_REWARD constants in
# referrals/models.py now only act as the *fallback default* for the
# SiteSettings fields. They are no longer read directly here.
# =============================================================================
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import ReferralCode, ReferralUsage, generate_referral_code


def _get_referral_settings():
    """
    Returns the singleton SiteSettings row.
    Imported lazily to avoid any app-loading / circular-import surprises.
    """
    from admin_panel.models import SiteSettings
    return SiteSettings.get()


def get_or_create_referral_code(user):
    """
    Gets or creates a referral code for a user.
    Called after signup so every user always has a code.
    """
    code_obj, created = ReferralCode.objects.get_or_create(user=user)
    if created or not code_obj.code:
        # Generate a unique code with retry loop to handle collisions
        for _ in range(10):
            candidate = generate_referral_code()
            if not ReferralCode.objects.filter(code=candidate).exists():
                code_obj.code = candidate
                code_obj.save(update_fields=['code'])
                break
    return code_obj


def validate_referral_code(code, new_user_email):
    """
    Validates a referral code before signup completes.
    Returns (ReferralCode, error_message).
    Silent on invalid codes — never tells user why it failed (prevents enumeration).
    """
    if not code or not code.strip():
        return None, None  # No code provided — not an error

    # NEW: if the admin has switched the whole program off, silently ignore any
    # referral code so no new referral is ever recorded while it is disabled.
    if not _get_referral_settings().referral_enabled:
        return None, None

    code = code.strip().upper()

    try:
        referral_code = ReferralCode.objects.select_related('user').get(code=code)
    except ReferralCode.DoesNotExist:
        return None, None  # Invalid code — silently ignore

    # Prevent self-referral
    if referral_code.user.email.lower() == new_user_email.lower():
        return None, None

    # Referrer must be active and not blocked
    if not referral_code.user.is_active or getattr(referral_code.user, 'is_blocked', False):
        return None, None

    return referral_code, None


def apply_referral_on_signup(referred_user, referral_code_obj):
    """
    Called once when a referred user's account is fully verified.
    - Records the ReferralUsage (snapshotting both reward amounts)
    - Credits the referred user's wallet immediately (signup bonus)
    Referrer reward is handled separately when referred user places first order.
    """
    if not referral_code_obj:
        return

    # NEW: extra safety — never create a referral while the program is off.
    settings_obj = _get_referral_settings()
    if not settings_obj.referral_enabled:
        return

    referrer_reward = Decimal(settings_obj.referrer_reward_amount)
    referred_reward = Decimal(settings_obj.referred_reward_amount)

    with transaction.atomic():
        # Guard: only apply if not already referred (DB constraint also protects this)
        if ReferralUsage.objects.filter(referred_user=referred_user).exists():
            return

        referrer = referral_code_obj.user

        # Guard: prevent self-referral (double check at application level)
        if referrer == referred_user:
            return

        usage = ReferralUsage.objects.create(
            referrer=referrer,
            referred_user=referred_user,
            referrer_rewarded=False,
            # Snapshot the amounts as configured RIGHT NOW. Future admin changes
            # will not alter this row — matches real-world "amount promised at
            # signup" behaviour.
            referrer_reward_amount=referrer_reward,
            referred_reward_amount=referred_reward,
        )

        # Credit referred user wallet immediately (only if the bonus is > 0)
        if referred_reward > 0:
            from wallet.models import Wallet
            wallet, _ = Wallet.objects.get_or_create(user=referred_user)
            wallet.credit(
                amount=referred_reward,
                reason=f"Welcome bonus — signed up via referral from {referrer.email}",
                order=None,
            )

    return usage


def reward_referrer_on_first_order(order):
    """
    Called from orders/services.py when an order is placed.
    Checks if this is the referred user's first order and referrer not yet rewarded.
    If so, credits the referrer's wallet using the amount SNAPSHOTTED on the row.

    NOTE: must be called INSIDE the order-placement transaction, because it uses
    select_for_update(). Existing referrals are honoured even if the program was
    later disabled — we intentionally do NOT re-check referral_enabled here.
    """
    user = order.user
    if not user:
        return

    # Check if this user was referred (and not yet rewarded)
    try:
        usage = ReferralUsage.objects.select_for_update().get(
            referred_user=user,
            referrer_rewarded=False,
        )
    except ReferralUsage.DoesNotExist:
        return  # Not referred, or referrer already rewarded — do nothing

    # Check this is their first order (exclude the current one since it's being created)
    from orders.models import Order
    previous_orders = Order.objects.filter(
        user=user,
        status__in=['pending', 'shipped', 'out_for_delivery', 'delivered'],
    ).exclude(pk=order.pk).count()

    if previous_orders > 0:
        return  # Not their first order

    # Referrer must still exist and be active
    if not usage.referrer or not usage.referrer.is_active:
        return

    # Nothing to pay if the snapshotted amount is 0
    if Decimal(usage.referrer_reward_amount) <= 0:
        usage.referrer_rewarded = True
        usage.rewarded_at = timezone.now()
        usage.save(update_fields=['referrer_rewarded', 'rewarded_at'])
        return

    # Credit referrer wallet + mark rewarded (atomic savepoint inside caller txn)
    from wallet.models import Wallet
    wallet, _ = Wallet.objects.get_or_create(user=usage.referrer)
    with transaction.atomic():
        wallet.credit(
            amount=usage.referrer_reward_amount,
            reason=(
                f"Referral reward — {user.email} placed their first order "
                f"(Order {order.order_number})"
            ),
            order=order,
        )
        usage.referrer_rewarded = True
        usage.rewarded_at = timezone.now()
        usage.save(update_fields=['referrer_rewarded', 'rewarded_at'])