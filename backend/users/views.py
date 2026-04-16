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

from .models import User, OTP, Address
from .forms import SignupForm, EditProfileForm, ChangePasswordForm, ChangeEmailForm, AddressForm
from .services import generate_and_send_otp


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

    return render(request, 'landing.html', {
        'show_signup': True   
    })

#signup
@never_cache
def signup(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            phone = form.cleaned_data['phone']
            password = form.cleaned_data['password']
            full_name = form.cleaned_data['full_name']

            first_name = full_name.split()[0]
            last_name = " ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else ""

            user = User.objects.create_user(
                username=email,  
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                phone=phone,

#must verify otp 
                is_active=False,
                is_verified=False
            )

            OTP.objects.filter(user=user).delete()
            generate_and_send_otp(user, email)

            clear_auth_sessions(request)
            request.session['otp_user_id'] = user.id#otp needs to know which user
            request.session.set_expiry(300)#5 minutes 

            return redirect('verify_otp')
    else:
        form = SignupForm()

    return render(request, 'auth/signup.html', {'form': form})

#verify_otp

@never_cache
def verify_otp(request):
    user_id = request.session.get('otp_user_id')
    if not user_id:
        return redirect('signup')

    user = get_object_or_404(User, id=user_id)
    otp_obj = OTP.objects.filter(user=user).order_by('-created_at').first()

    if not otp_obj:
        return redirect('signup')
    
    #expiry logic (the timer)
    
    elapsed = (timezone.now() - otp_obj.created_at).seconds
    remaining_time = max(0, 60 - elapsed)

    if timezone.now() > otp_obj.created_at + timedelta(minutes=5):
        otp_obj.delete()
        messages.error(request, "OTP expired. Please sign up again.")
        return redirect('signup')

    if request.method == "POST":
        #  Collect the 6 digits and join them together
        otp_digits = request.POST.getlist('otp_digit')
        otp = "".join(otp_digits).strip()

        if otp_obj.attempts >= 5:
            otp_obj.delete()
            messages.error(request, "Too many failed attempts. Try again.")
            return redirect('signup')

        #  checking password of user with db
        if check_password(otp, otp_obj.otp):
            user.is_verified = True
            user.is_active = True
            user.save()
            otp_obj.delete()
            # Remove session data after success
            request.session.pop('otp_user_id', None)
            messages.success(request, "Account verified! Please sign in.")
            return redirect('login')
#count failed attempts
        otp_obj.attempts += 1
        otp_obj.save()
        messages.error(request, "Invalid OTP code.")

    return render(request, 'auth/verify_otp.html', {
        'remaining_time': remaining_time,
        'user_email': user.email
    })

#resend
@require_POST
def resend_otp(request):
    user_id = request.session.get('otp_user_id') or request.session.get('reset_user_id')
    if not user_id:
        messages.error(request, "Session expired.")
        return redirect('login')

    user = get_object_or_404(User, id=user_id)
    otp_obj = OTP.objects.filter(user=user).order_by('-created_at').first()
#waiting rule
    if otp_obj and timezone.now() < otp_obj.created_at + timedelta(seconds=60):
        messages.error(request, "Please wait 60 seconds before requesting again.")
        return redirect(request.META.get('HTTP_REFERER'))
#limit rule
    resend_count = request.session.get('resend_count', 0)
    if resend_count >= 3:
        messages.error(request, "Maximum resend limit reached.")
        return redirect(request.META.get('HTTP_REFERER'))

    OTP.objects.filter(user=user).delete()
    generate_and_send_otp(user, user.email)

    request.session['resend_count'] = resend_count + 1
    messages.success(request, "New OTP sent successfully.")
    return redirect(request.META.get('HTTP_REFERER'))

#login
@never_cache
def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == "POST":
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password')
#compares them against the encrypted password in the db
        user = authenticate(request, username=email, password=password)

        if not user:
            User = get_user_model()
            exists = User.objects.filter(email=email).exists()
            print(f"DEBUG: Email exists in database: {exists}")
            
            messages.error(request, "Invalid credentials.")
            return render(request, 'auth/login.html')
        
        if user.is_blocked:
            messages.error(request, "This account has been suspended.")
            return render(request, 'auth/login.html')
            

        if not user.is_verified:
            request.session['otp_user_id'] = user.id
            generate_and_send_otp(user, user.email)
            messages.warning(request, "Please verify your email first.")
            return redirect('verify_otp')

        

        # SUCCESS
        login(request, user)
        
       
        request.session.set_expiry(1209600) 
        
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
            generate_and_send_otp(user, email)

            # 2. Set the session securely
            request.session['reset_user_id'] = user.id
            request.session.set_expiry(300)
            
            # 3. Redirect to the OTP page
            messages.success(request, "An OTP has been sent to your email.")
            return redirect('forgot_otp')
        else:
            #  FIX: Tell the user if the email is wrong!
            messages.error(request, "If an account exists, you will receive an email.")
            return redirect('forgot_password')

    return render(request, 'auth/forgot_password.html')



@never_cache
def forgot_otp(request):
    user_id = request.session.get('reset_user_id')
    if not user_id:
        return redirect('forgot_password')

    user = get_object_or_404(User, id=user_id)
    otp_obj = OTP.objects.filter(user=user).order_by('-created_at').first()

    if not otp_obj:
        return redirect('forgot_password')

    elapsed = (timezone.now() - otp_obj.created_at).seconds
    remaining_time = max(0, 60 - elapsed)

    if timezone.now() > otp_obj.created_at + timedelta(minutes=5):
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
        messages.error(request, "Invalid OTP")

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
        logout(request) # Kick him out immediately
        messages.error(request, "Your account was suspended.")
        return redirect('login')
    return render(request, 'home/home.html')

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
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = ChangePasswordForm(request.user)
        
    return render(request, "profile/change_password.html", {"form": form})


@login_required

def change_email_request(request):
    if request.method == "POST":
        form = ChangeEmailForm(request.POST)
        if form.is_valid():
            new_email = form.cleaned_data['email']
            
            # Reset OTP attempts and generate new one
            OTP.objects.filter(user=request.user).delete()
            generate_and_send_otp(request.user, new_email)
            
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

    otp_obj = OTP.objects.filter(user=request.user).order_by('-created_at').first()

    if request.method == "POST":
        otp = request.POST.get("otp", "").strip()
        #checks the otp matches with the code in db
        
        if otp_obj and check_password(otp, otp_obj.otp):
            # Atomic transaction ensures both change successfully, or neither do
            with transaction.atomic():
                request.user.email = new_email
                request.user.username = new_email 
                request.user.save()
            
            otp_obj.delete()
            #empties the temp folder
            request.session.pop("new_email_pending", None)
            messages.success(request, "Email updated successfully.")
            return redirect("dashboard")
            
        messages.error(request, "Invalid or expired OTP.")

    return render(request, "profile/verify_email.html", {"email": new_email})


@require_POST
def resend_otp(request):
    # 1. Look for the user in the session (Signup/Forgot Password flow)
    user_id = request.session.get('otp_user_id') or request.session.get('reset_user_id')
    
    # 2. Look for the user via current login (Email Change flow)
    if not user_id and request.user.is_authenticated:
        user_id = request.user.id

    # 3. If no ID is found anywhere, the session is truly dead
    if not user_id:
        messages.error(request, "Session expired. Please start the process again.")
        # Determine where to send them based on login status
        return redirect('login') if not request.user.is_authenticated else redirect('dashboard')

    user = get_object_or_404(User, id=user_id)
    
    # Rate Limiting: Don't allow spamming every second
    otp_obj = OTP.objects.filter(user=user).order_by('-created_at').first()
    if otp_obj and (timezone.now() - otp_obj.created_at).seconds < 30:
        messages.warning(request, "Please wait before requesting a new code.")
        return redirect(request.META.get('HTTP_REFERER', 'login'))

    # Generate and send new OTP
    # For email change, use the pending email; otherwise use the user's primary email
    target_email = request.session.get('new_email_pending') or user.email
    
    OTP.objects.filter(user=user).delete()
    generate_and_send_otp(user, target_email)

    messages.success(request, f"A new code has been sent to {target_email}.")
    
    # Redirect back to the page they came from
    return redirect(request.META.get('HTTP_REFERER', 'login'))

#  ADDRESS MANAGEMENT

@login_required
@never_cache
def manage_addresses(request):
    """ SEPARATE PAGE - Lists all addresses """
    addresses = request.user.addresses.all().order_by('-created_at')
    return render(request, "profile/manage_addresses.html", {"addresses": addresses})

@login_required
@require_POST
def set_default_address(request, pk):
    #this finds the specific address you clicked on
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.is_default = True
    address.save() # The model save method handles unsetting the old one
    messages.success(request, f"{address.label} is now your default address.")
    return redirect('manage_addresses')




@login_required
def add_address(request):
    if request.method == "POST":
        form = AddressForm(request.POST)
        if form.is_valid():
            #creates a draft of the address
            address = form.save(commit=False)
            #tags address with the user
            address.user = request.user
            
            address.is_default = request.POST.get('is_default') == 'on'
            address.save()
            messages.success(request, "Address added successfully!")
            return redirect("manage_addresses")
        else:
            # If it fails, this will show you WHY (e.g., "Phone number too long")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.replace('_', ' ').title()}: {error}")
    
    #  Fetch addresses so they don't disappear on a failed save
    addresses = request.user.addresses.all().order_by('-is_default', '-id')
    return render(request, "profile/manage_addresses.html", {
        "addresses": addresses,
        "form": AddressForm()
    })
@login_required
@never_cache
def edit_address(request, address_id):
    #finds the address that you want to change
    address = get_object_or_404(Address, id=address_id, user=request.user)
    if request.method == "POST":
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, "Address updated successfully.")
            return redirect("manage_addresses")
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = AddressForm(instance=address)
        
    return render(request, "profile/manage_addresses.html", {"form": form, "address": address})


@login_required
@require_POST
def delete_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    address.delete()
    messages.success(request, "Address deleted successfully.")
    return redirect("manage_addresses")


