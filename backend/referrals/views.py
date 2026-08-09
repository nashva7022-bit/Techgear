from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from .models import ReferralUsage
from .services import get_or_create_referral_code


@login_required
@never_cache
def referral_dashboard(request):

    code_obj = get_or_create_referral_code(request.user)

    referral_link = request.build_absolute_uri(f"/signup/?ref={code_obj.code}")

    referrals_made = (
        ReferralUsage.objects.filter(referrer=request.user)
        .select_related("referred_user")
        .order_by("-created_at")
    )

    total_referred = referrals_made.count()
    total_rewarded = referrals_made.filter(referrer_rewarded=True).count()
    pending_rewards = referrals_made.filter(referrer_rewarded=False).count()

    paginator = Paginator(referrals_made, getattr(settings, "REFERRALS_PER_PAGE"))
    page_obj = paginator.get_page(request.GET.get("page"))
    context = {
        "code_obj": code_obj,
        "referral_link": referral_link,
        "page_obj": page_obj,
        "total_referred": total_referred,
        "total_rewarded": total_rewarded,
        "pending_rewards": pending_rewards,
    }
    return render(request, "referrals/referral_dashboard.html", context)
