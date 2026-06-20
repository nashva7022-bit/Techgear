

# Create your views here.
from django.shortcuts import render, get_object_or_404,redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.cache import never_cache
from django.core.paginator import Paginator

from .models import Wallet, WalletTransaction
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from decimal import Decimal

def get_or_create_wallet(user):
    
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


#  USER WALLET PAGE 

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




@login_required
@never_cache
def wallet_topup_initiate(request):
    """
    Creates a Razorpay order for wallet top-up.
    Called via POST with amount from the wallet page.
    """
    if request.method != 'POST':
        return redirect('wallet:wallet')

    import razorpay
    from django.conf import settings

    amount_str = request.POST.get('amount', '').strip()
    try:
        amount = Decimal(amount_str)
        if amount < 1:
            from django.contrib import messages
            messages.error(request, "Minimum top-up amount is ₹1.")
            return redirect('wallet:wallet')
        if amount > 100000:
            from django.contrib import messages
            messages.error(request, "Maximum top-up amount is ₹1,00,000.")
            return redirect('wallet:wallet')
    except Exception:
        from django.contrib import messages
        messages.error(request, "Please enter a valid amount.")
        return redirect('wallet:wallet')

    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )
    razorpay_order = client.order.create({
        'amount':          int(amount * 100),  # paise
        'currency':        'INR',
        'payment_capture': 1,
    })

    # Store in session
    request.session['pending_wallet_topup'] = {
        'amount':           str(amount),
        'razorpay_order_id': razorpay_order['id'],
    }

    return render(request, 'wallet/topup_payment.html', {
        'razorpay_order': razorpay_order,
        'razorpay_key':   settings.RAZORPAY_KEY_ID,
        'amount':         int(amount * 100),
        'amount_display': amount,
        'user_name':      request.user.get_full_name() or request.user.email,
        'user_email':     request.user.email,
        'user_phone':     getattr(request.user, 'phone', ''),
    })


@csrf_exempt
@login_required
def wallet_topup_callback(request):
    
    import razorpay
    from django.conf import settings

    data = request.POST if request.method == 'POST' else request.GET
    razorpay_payment_id = data.get('razorpay_payment_id', '')
    razorpay_order_id   = data.get('razorpay_order_id', '')
    razorpay_signature  = data.get('razorpay_signature', '')

    pending = request.session.get('pending_wallet_topup')
    if not pending or pending.get('razorpay_order_id') != razorpay_order_id:
        from django.contrib import messages
        messages.error(request, "Invalid or expired payment session.")
        return redirect('wallet:wallet')

    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )

    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id':   razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature':  razorpay_signature,
        })
    except razorpay.errors.SignatureVerificationError:
        from django.contrib import messages
        messages.error(request, "Payment verification failed. Please contact support.")
        request.session.pop('pending_wallet_topup', None)
        return redirect('wallet:wallet')

    amount = Decimal(pending['amount'])
    wallet = get_or_create_wallet(request.user)
    wallet.credit(
        amount=amount,
        reason=f"Wallet top-up via Razorpay (₹{amount})",
        order=None,
    )

    request.session.pop('pending_wallet_topup', None)
    from django.contrib import messages
    messages.success(request, f"₹{amount} added to your wallet successfully!")
    return redirect('wallet:wallet')


@login_required
@require_POST
def wallet_topup_failed(request):
    """Called by JS when Razorpay modal is dismissed."""
    request.session.pop('pending_wallet_topup', None)
    return JsonResponse({'ok': True})