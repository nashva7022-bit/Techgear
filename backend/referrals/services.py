
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import ReferralCode, ReferralUsage, generate_referral_code


def _get_referral_settings():
    
    from admin_panel.models import SiteSettings
    return SiteSettings.get()


def get_or_create_referral_code(user):
    
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
    
    if not code or not code.strip():
        return None, None  
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
    
    if not referral_code_obj:
        return

    # never create a referral while the program is off.
    settings_obj = _get_referral_settings()
    if not settings_obj.referral_enabled:
        return

    referrer_reward = Decimal(settings_obj.referrer_reward_amount)
    referred_reward = Decimal(settings_obj.referred_reward_amount)

    with transaction.atomic():
        
        if ReferralUsage.objects.filter(referred_user=referred_user).exists():
            return

        referrer = referral_code_obj.user

        
        if referrer == referred_user:
            return

        usage = ReferralUsage.objects.create(
            referrer=referrer,
            referred_user=referred_user,
            referrer_rewarded=False,
            
            referrer_reward_amount=referrer_reward,
            referred_reward_amount=referred_reward,
        )

        
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
        return  

   
    from orders.models import Order
    previous_orders = Order.objects.filter(
        user=user,
        status__in=['pending', 'shipped', 'out_for_delivery', 'delivered'],
    ).exclude(pk=order.pk).count()

    if previous_orders > 0:
        return  # Not their first order

    
    if not usage.referrer or not usage.referrer.is_active:
        return

    
    if Decimal(usage.referrer_reward_amount) <= 0:
        usage.referrer_rewarded = True
        usage.rewarded_at = timezone.now()
        usage.save(update_fields=['referrer_rewarded', 'rewarded_at'])
        return

    
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