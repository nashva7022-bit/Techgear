import logging
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import transaction  # ADDED FOR SECURITY
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import IntegrityError,transaction
import hashlib
from .models import User, OTP, Address
from .forms import SignupForm, EditProfileForm, ChangePasswordForm, ChangeEmailForm, AddressForm
from .services import generate_and_send_otp
from django.core.cache import cache
from django.core.mail import BadHeaderError
from smtplib import SMTPException
from django.db.models import F
from products.models import Category,Product


logger = logging.getLogger(__name__)


# SECURE SESSION HELPER

def clear_auth_sessions(request):
    keys_to_remove =['otp_user_id', 'reset_user_id', 'otp_verified', 'resend_count', 'new_email_pending']
    for key in keys_to_remove:
        request.session.pop(key, None)



# PUBLIC PAGES & AUTH

@never_cache
def landing(request):
    if request.user.is_authenticated:
        return redirect('home')

    categories = Category.objects.filter(is_active=True)[:4]
    
    top_products = Product.objects.filter(
        is_active=True,
        is_featured=True,
        category__is_active=True
    ).prefetch_related('variants__images').order_by('-created_at')[:4]
    for product in top_products:
        product.first_variant = product.variants.first()

    # Fallback if no featured products yet
    if not top_products.exists():
        top_products = Product.objects.filter(
            is_active=True,
            category__is_active=True
        ).prefetch_related('variants__images').order_by('-created_at')[:4]
        for product in top_products:
            product.first_variant = product.variants.first()

    return render(request, 'landing.html', {
        'show_signup': True,
        'categories': categories,
        'top_products': top_products,
    })

#signup


def _safe_id(email):
    return hashlib.sha256(email.encode()).hexdigest()[:10]


@never_cache
def signup(request):
    if request.user.is_authenticated:
        return redirect('home')

    form = SignupForm(request.POST or None)

    if request.method == "POST" and form.is_valid():

        # 1. RATE LIMIT (only valid attempts counted)
        ip = request.META.get('REMOTE_ADDR')
        rate_key = f'signup_rate:{ip}'
        attempts = cache.get(rate_key, 0)

        if attempts >= 10:
            messages.error(request, "Too many attempts. Try again later.")
            return redirect('signup')

        cache.set(rate_key, attempts + 1, timeout=3600)

        email = form.cleaned_data['email']
        phone = form.cleaned_data['phone']
        password = form.cleaned_data['password']
        full_name = form.cleaned_data['full_name']

        #  SAFE NAME SPLIT
        parts = full_name.split()
        first_name = parts[0] if parts else "User"
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

        #  2. ACTIVE USER → LOGIN
        if User.objects.filter(email=email, is_active=True).exists():
            messages.info(request, "Account already exists. Please login.")
            return redirect('login')

        # 🔹 3. INACTIVE USER (SAFE RESUME)
        inactive_user = User.objects.filter(email=email, is_active=False).first()

        if inactive_user:
            # OTP RATE LIMIT (30 sec)
            recent_otp = OTP.objects.filter(
                user=inactive_user,
                created_at__gte=timezone.now() - timedelta(seconds=30)
            ).exists()

            if recent_otp:
                messages.error(request, "Please wait before requesting another code.")
                return redirect('signup')

            try:
                OTP.objects.filter(user=inactive_user,purpose='signup').delete()
                generate_and_send_otp(inactive_user, email,purpose='signup')

                request.session.cycle_key()
                request.session['otp_user_id'] = inactive_user.id
                request.session.set_expiry(600)

                messages.info(request, "Verification code sent.")
                return redirect('verify_otp')

            except (SMTPException, BadHeaderError, OSError) as e:
                logger.error("OTP failed sid=%s err=%s", _safe_id(email), str(e))
                messages.error(request, "Mail error. Try again.")
                return redirect('signup')

        #  4. NEW USER FLOW
        user = None

        # 4. NEW USER FLOW
        try:
            with transaction.atomic():
                # Create the user but keep them inactive
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    is_active=False,
                    is_verified=False
                )
                
                # Generate and save OTP record BEFORE sending the email
                # This ensures if the DB fails, no email is sent.
                generate_and_send_otp(user, email, purpose='signup')

            # 5. SESSION SETUP (Only happens if transaction succeeds)
            request.session.cycle_key()
            request.session['otp_user_id'] = user.id
            request.session.set_expiry(600) # Give them 10 mins to verify

            messages.info(request, "Verification code sent to " + email)
            return redirect('verify_otp')

        except (SMTPException, BadHeaderError, OSError) as e:
            logger.error(f"Mail failure for {email}: {str(e)}")
            # No need to manually delete user if transaction.atomic() 
            # rolled back the user creation!
            messages.error(request, "We couldn't send the code. Please check your email or try again.")
            return redirect('signup')
        
        except IntegrityError:
            messages.info(request, "This email is already pending verification. Please check your inbox.")
            return redirect('login')
    return render(request,'auth/signup.html', {'form': form})
#verify otp

@never_cache
def verify_otp(request):
    # 1. IDENTIFY THE USER
    user_id = request.session.get('otp_user_id')
    user = User.objects.filter(id=user_id).first() if user_id else None

    if not user and request.user.is_authenticated:
        user = request.user

    if not user:
        messages.error(request, "Session expired. Please login to continue.")
        return redirect('login')

    # 2. STATUS CHECK
    if user.is_verified and user.is_active:
        return redirect('home')

    # 3. GET OTP DATA
    otp_obj = OTP.objects.filter(user=user, purpose='signup').order_by('-created_at').first()

    remaining_time = 0
    if otp_obj:
        elapsed = (timezone.now() - otp_obj.created_at).total_seconds()
        remaining_time = max(0, 120 - int(elapsed))

    # 4. HANDLE POST
    if request.method == "POST":

        # Case: Expired — auto resend
        if not otp_obj or remaining_time <= 0:
            if otp_obj:
                otp_obj.delete()

            rate_key = f'resend_limit:signup:{user.id}'
            count = cache.get(rate_key, 0)
            if count >= 5:
                messages.error(request, "Too many attempts. Please try again later.")
                return redirect('login')

            generate_and_send_otp(user, user.email, purpose='signup')
            cache.set(rate_key, count + 1, timeout=300)

            messages.error(request, "Code expired. A fresh one has been sent.")
            return render(request, 'auth/verify_otp.html', {
                'remaining_time': 120,
                'user_email': user.email
            })

        # Case: Format check
        otp = "".join(request.POST.getlist('otp_digit')).strip()
        if len(otp) != 6:
            messages.error(request, "Please enter the full 6-digit code.")
            return render(request, 'auth/verify_otp.html', {
                'remaining_time': remaining_time,
                'user_email': user.email
            })

        # Case: Correct code
        if check_password(otp, otp_obj.otp):
            with transaction.atomic():
                user.is_verified = True
                user.is_active = True
                user.save()
                otp_obj.delete()

            request.session.pop('otp_user_id', None)
            messages.success(request, "Email verified! Please login with your password.")
            return redirect('login')

        # Case: Wrong code
        messages.error(request, "Invalid code. Please try again.")
        return render(request, 'auth/verify_otp.html', {
            'remaining_time': remaining_time,
            'user_email': user.email
        })

    # 5. HANDLE GET
    return render(request, 'auth/verify_otp.html', {
        'remaining_time': remaining_time,
        'user_email': user.email
    })
#login
@never_cache
def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == "POST":
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password')

        # 1. Look up the user first to check status
        user_check = User.objects.filter(email=email).first()

        if user_check:
            # 2. Check if Blocked (Prioritize this)
            if getattr(user_check, 'is_blocked', False):
                messages.error(request, "This account has been suspended.")
                return render(request, 'auth/login.html', {'email': email})

            # 3. Check if Unverified 
            if not user_check.is_verified:
                request.session.cycle_key()
                request.session['otp_user_id'] = user_check.id
                # Check if we should resend or just redirect
                otp_exists = OTP.objects.filter(user=user_check, purpose='signup', 
                                              created_at__gte=timezone.now() - timedelta(minutes=2)).exists()
                if not otp_exists:
                    generate_and_send_otp(user_check, user_check.email, purpose='signup')
                    messages.warning(request, "Account not verified. A new code has been sent.")
                else:
                    messages.warning(request, "Please verify your account to continue.")
                
                return redirect('verify_otp')

        # 4. Standard Authentication for verified users
        user = authenticate(request, username=email, password=password)
        if not user:
            messages.error(request, "Invalid email or password.")
            return render(request, 'auth/login.html', {'email': email})

        # 5. Final Success
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f"Welcome back!")
        return redirect('home')

    return render(request, 'auth/login.html')
#logout
@require_POST
def logout_view(request):
    logout(request)
    request.session.flush()
    return redirect('login')


# FORGOT PASSWORD
@never_cache
def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get('email').lower().strip()
        user = User.objects.filter(email=email).first()

        if user:
            # 1. Clear old OTPs and send new one
            OTP.objects.filter(user=user).delete()
            generate_and_send_otp(user, email, purpose='password_reset')

            # 2. Set the session securely
            request.session['reset_user_id'] = user.id
            request.session.set_expiry(300)
            
            # 3. Redirect to the OTP page
            messages.success(request, "An OTP has been sent to your email.")
            return redirect('forgot_otp')
        else:
            #  FIX: Tell the user if the email is wrong!
            messages.error(request, "No account found with this email address.")
            return redirect('forgot_password')

    return render(request, 'auth/forgot_password.html')


@never_cache
def forgot_otp(request):
    user_id = request.session.get('reset_user_id')
    if not user_id:
        return redirect('forgot_password')

    user = get_object_or_404(User, id=user_id)
    
    otp_obj = OTP.objects.filter(
        user=user,
        purpose='password_reset'
    ).order_by('-created_at').first()

    if not otp_obj:
        return redirect('forgot_password')

    OTP_EXPIRY_SECONDS = 60
    elapsed = (timezone.now() - otp_obj.created_at).total_seconds()
    remaining_time = max(0, OTP_EXPIRY_SECONDS - int(elapsed))

    if elapsed > OTP_EXPIRY_SECONDS:
        otp_obj.delete()
        clear_auth_sessions(request)
        messages.error(request, "OTP expired. Request a new one.")
        return redirect('forgot_password')

    if request.method == "POST":
        otp = request.POST.get('otp', '').strip()

        if otp_obj.attempts >= 5:
            otp_obj.delete()
            clear_auth_sessions(request)
            messages.error(request, "Too many attempts.")
            return redirect('forgot_password')

        if check_password(otp, otp_obj.otp):
            otp_obj.delete()
            request.session['otp_verified'] = True
            request.session['reset_user_id'] = user.id
            return redirect('reset_password')

        otp_obj.attempts += 1
        otp_obj.save()
        messages.error(request, "Invalid OTP.")

    return render(request, 'auth/forgot_otp.html', {'remaining_time': remaining_time})


@never_cache
def reset_password(request):
    if not request.session.get('otp_verified'):
        return redirect('forgot_password')

    user_id = request.session.get('reset_user_id')
    if not user_id:
        return redirect('forgot_password')
        
    user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        password = request.POST.get('password')
        confirm = request.POST.get('confirm_password')

        if password != confirm:
            messages.error(request, "Passwords do not match.")
            return redirect(request.path)

        try:
            validate_password(password)
        except ValidationError as e:
            messages.error(request, ', '.join(e.messages))
            return redirect(request.path)

        user.set_password(password)
        user.save()
        clear_auth_sessions(request)
        
        return redirect('password_reset_sent')

    return render(request, 'auth/reset_password.html')

@never_cache
def password_reset_sent(request):
    return render(request, 'auth/reset_sent.html')


# SEPARATED DASHBOARD & PROFILE

@login_required
@never_cache
def home(request):
    if request.user.is_blocked:
        logout(request)
        messages.error(request, "Your account was suspended.")
        return redirect('login')
    categories = Category.objects.filter(is_active=True)[:4]
  
    featured_products = Product.objects.filter(
        is_active=True,
        is_featured=True,
        category__is_active=True
    ).prefetch_related('variants__images').order_by('-created_at')[:4]

# Fallback if no featured products marked yet
    if not featured_products.exists():
        featured_products = Product.objects.filter(
            is_active=True,
            category__is_active=True
        ).prefetch_related('variants__images').order_by('-created_at')[:4]

    trending_products = Product.objects.filter(
        is_active=True,
        is_trending=True,
        category__is_active=True
    ).prefetch_related('variants__images').order_by('-created_at')[:4]

# Fallback if no trending products marked yet
    if not trending_products.exists():
        trending_products = Product.objects.filter(
            is_active=True,
            category__is_active=True
        ).prefetch_related('variants__images').order_by('-created_at')[:4]

    return render(request, 'home/home.html', {
        'categories': categories,
        'featured_products': featured_products,
        'trending_products': trending_products,
})


@login_required
@never_cache
def dashboard(request):
    """ DISPLAY ONLY - Shows profile details and primary address """
    primary_address = request.user.addresses.all().order_by('-created_at').first()
    return render(request, "profile/dashboard.html", {
        "user": request.user,
        "primary_address": primary_address
    })

@login_required
@never_cache
def edit_profile(request):
    """ SEPARATE PAGE - Handle Full Name, Phone, and Photo """
    if request.method == "POST":
        form = EditProfileForm(request.POST, request.FILES, instance=request.user)
        #profile remove
        if form.is_valid():
            if request.POST.get("remove_image") == "true" and request.user.profile_image:
                request.user.profile_image.delete(save=False)
                request.user.profile_image = None
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("dashboard")
        else:
            for error in form.errors.values():
                messages.error(request, error)
                #the current datas will be there,no need to retype
    else:
        form = EditProfileForm(instance=request.user)
        
    return render(request, "profile/edit_profile.html", {"form": form})



# SEPARATED EMAIL & PASSWORD PAGES

@login_required
@never_cache
def change_password(request):
  
    if request.method == "POST":
        form = ChangePasswordForm(request.user, request.POST)
        if form.is_valid():
            request.user.set_password(form.cleaned_data['new_password'])
            request.user.save()
            update_session_auth_hash(request, request.user) # Keeps user logged in
            messages.success(request, "Password updated successfully.")
            return redirect("dashboard")
        
    else:
        form = ChangePasswordForm(request.user)
        
    return render(request, "profile/change_password.html", {"form": form})


@login_required
@never_cache
def change_email_request(request):
    if request.method == "POST":
        form = ChangeEmailForm(request.POST)
        if form.is_valid():
            new_email = form.cleaned_data['email']
            
            # Reset OTP attempts and generate new one
            OTP.objects.filter(user=request.user, purpose='email_change').delete()
            generate_and_send_otp(request.user, new_email,purpose='email_change')
            all_otps = OTP.objects.filter(user=request.user)
            print(f"DEBUG all OTPs for user: {list(all_otps.values('id', 'purpose', 'created_at'))}")
            
            # Setup session for verification
            request.session['otp_user_id'] = request.user.id 
#It saves the new email in a temporary spot (session) 
            request.session['new_email_pending'] = new_email
            
            return redirect("verify_email")
    else:
        # If it's a GET request, we need to provide a form
        form = ChangeEmailForm()

    
    return render(request, 'profile/change_email.html', {'form': form})
        


@login_required
@never_cache
def verify_email(request):
    new_email = request.session.get("new_email_pending")
    if not new_email:
        return redirect("dashboard")

    otp_obj = OTP.objects.filter(user=request.user, purpose='email_change').order_by('-created_at').first()

    # Calculate remaining time for the template timer
    remaining_time = 0
    
    if otp_obj:
        
        elapsed = (timezone.now() - otp_obj.created_at).total_seconds()
        remaining_time = max(0, 60 - int(elapsed))

    if request.method == "POST":
        otp_list = request.POST.getlist('otp_digit')
        otp = "".join(otp_list).strip()

        if not otp_obj:
            messages.error(request, "No verification code found. Please request a new one.")
            return redirect("change_email")

        # Expiry check
        age_seconds = (timezone.now() - otp_obj.created_at).total_seconds()
        if age_seconds > 60:
            otp_obj.delete()
            # Auto-send a fresh OTP instead of making them go back
            generate_and_send_otp(request.user, new_email, purpose='email_change')
            
            
            messages.error(request, "Your code expired. A fresh one has been sent to your email.")
            return render(request, "profile/verify_email.html", {
                "email": new_email,
                "remaining_time": 60
            })

        # Attempt limit check
        if otp_obj.attempts >= 5:
            otp_obj.delete()
            messages.error(request, "Too many incorrect attempts. Please request a new code.")
            return redirect("change_email")

        if len(otp) != 6:
            messages.error(request, "Please enter the full 6-digit code.")
            return render(request, "profile/verify_email.html", {
                "email": new_email,
                "remaining_time": remaining_time
            })

        if check_password(otp, otp_obj.otp):
            with transaction.atomic():
                request.user.email = new_email
                request.user.username = new_email
                request.user.save()
            otp_obj.delete()
            request.session.pop("new_email_pending", None)
            messages.success(request, "Email updated successfully.")
            return redirect("dashboard")
        else:
            otp_obj.attempts += 1
            otp_obj.save()
            messages.error(request, "Invalid code. Please try again.")
            
            return render(request, "profile/verify_email.html", {
                "email": new_email,
                "remaining_time": remaining_time
            })

    return render(request, "profile/verify_email.html", {
        "email": new_email,
        "remaining_time": remaining_time
    })


@require_POST
def resend_otp(request):
    # 1. IDENTIFY BY PRIORITY (Fixes the "Crossover" bug)
    # Check for Email Change first because the user is AUTHENTICATED here
    if 'new_email_pending' in request.session:
        user = request.user
        purpose = 'email_change'
        target_email = request.session['new_email_pending']
        redirect_url = 'verify_email'
        
    # Check for Forgot Password second
    elif 'reset_user_id' in request.session:
        user_id = request.session.get('reset_user_id')
        user = get_object_or_404(User, id=user_id)
        purpose = 'password_reset'
        target_email = user.email
        redirect_url = 'forgot_otp'
        
    # Check for Signup last (Session-based)
    elif 'otp_user_id' in request.session:
        user_id = request.session.get('otp_user_id')
        user = get_object_or_404(User, id=user_id)
        purpose = 'signup'
        target_email = user.email
        redirect_url = 'verify_otp'
        
    else:
        messages.error(request, "Session expired. Please try again.")
        return redirect('login')

    # 2. SECURITY: COOLDOWN CHECK
    otp_obj = OTP.objects.filter(user=user, purpose=purpose).order_by('-created_at').first()
    if otp_obj and (timezone.now() - otp_obj.created_at).total_seconds() < 60:
        messages.warning(request, "Please wait 60 seconds before requesting a new code.")
        return redirect(redirect_url)

    # 3. SECURITY: RATE LIMIT
    rate_key = f'resend_limit:{purpose}:{user.id}'
    count = cache.get(rate_key, 0)
    if count >= 5:
        messages.error(request, "Too many requests. Try again later.")
        return redirect(redirect_url)

    # 4. EXECUTION
    # Use a transaction to ensure old OTP is gone and new one is sent
    with transaction.atomic():
        OTP.objects.filter(user=user, purpose=purpose).delete()
        generate_and_send_otp(user, target_email, purpose=purpose)

    cache.set(rate_key, count + 1, timeout=300)
    messages.success(request, f"A fresh code has been sent to {target_email}.")
    return redirect(redirect_url)

#  ADDRESS MANAGEMENT

@login_required
def manage_addresses(request):
    addresses = request.user.addresses.all() # Ordering is handled by Model Meta
    return render(request, "profile/manage_addresses.html", {
        "addresses": addresses,
        "form": AddressForm()
    })


@login_required
@require_POST
def set_default_address(request, pk):
    #this finds the specific address you clicked on
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.is_default = True
    address.save() # The model save method handles unsetting the old one
    messages.success(request, f"{address} is now your default address.")
    return redirect('manage_addresses')


@login_required
def add_address(request):
    if request.method == "POST":
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            if not request.user.addresses.exists():
                address.is_default = True
            address.save()
            messages.success(request, "New address added!")
            return redirect("manage_addresses")
        
        # If invalid, keep drawer open
        addresses = request.user.addresses.all()
        return render(request, "profile/manage_addresses.html", {
            "addresses": addresses,
            "form": form,
            "drawer_mode": "add"
        })
    return redirect("manage_addresses")


@login_required
def edit_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    if request.method == "POST":
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, "Address updated successfully.")
            return redirect("manage_addresses")
        
        # If invalid, pass address_instance to keep the drawer identifying the correct ID
        addresses = request.user.addresses.all()
        return render(request, "profile/manage_addresses.html", {
            "addresses": addresses,
            "form": form,
            "address_instance": address, 
            "drawer_mode": "edit"
        })
    return redirect("manage_addresses")

@login_required
@require_POST
def delete_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    was_default = address.is_default
    address.delete()
    if was_default:
        next_address = request.user.addresses.order_by('created_at').first()
        if next_address:
            next_address.is_default = True
            next_address.save()
    messages.success(request, "Address deleted successfully.")
    return redirect("manage_addresses")


