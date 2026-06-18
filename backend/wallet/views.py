from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.cache import never_cache
from django.core.paginator import Paginator

from .models import Wallet, WalletTransaction


def get_or_create_wallet(user):
    """
    Gets the user's wallet, creating one with ₹0 balance if it doesn't exist.
    Use this everywhere instead of Wallet.objects.get() or .first()
    """
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


# ── USER WALLET PAGE ──────────────────────────────────────────────────────────

@login_required
@never_cache
def wallet_view(request):
    """
    Shows the user their wallet balance and full transaction history.
    Paginated at 10 per page — newest first.
    """
    wallet       = get_or_create_wallet(request.user)
    transactions = wallet.transactions.select_related('order').all()

    paginator   = Paginator(transactions, 10)
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)

    context = {
        'wallet':   wallet,
        'page_obj': page_obj,
    }
    return render(request, 'wallet/wallet.html', context)


