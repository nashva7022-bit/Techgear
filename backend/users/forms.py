import re
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from .models import User, Address

# Regex for real-world names (allows spaces, hyphens, and apostrophes, but NO numbers/symbols)
NAME_REGEX = r"^[A-Za-z\s\-\']+$"

#SIGNUP FORM 
class SignupForm(forms.ModelForm):
    full_name = forms.CharField(max_length=100)
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    referral_code = forms.CharField(
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Referral code (optional)'}),
    )

    class Meta:
        model = User
        fields = ['email', 'full_name', 'phone']

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower().strip()
        if not email:
            raise ValidationError("Email is required.")
        # Secure case-insensitive check
        if User.objects.filter(email__iexact=email,is_active=True).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean_phone(self):
        phone = (self.cleaned_data.get ('phone') or '').strip()
        if not phone.isdigit():
            raise ValidationError("Phone number must contain only digits.")
        if len(phone) != 10:
            raise ValidationError("Please enter a valid phone number.")
        if phone[0]=='0':
            raise ValidationError("Phone number cannot start with zero.")
        if len(set(phone)) == 1:
            raise ValidationError("Please enter a valid phone number.")
    
        return phone

    def clean_full_name(self):
        name = self.cleaned_data.get('full_name', '').strip()
        if not name:
            raise ValidationError("Full name is required.")
        if not re.match(NAME_REGEX, name):
            raise ValidationError("Name contains invalid characters.")
        return name

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm = cleaned_data.get('confirm_password')

        if password and confirm:
            if password != confirm:
                self.add_error('confirm_password', "Passwords do not match.")
            else:
                try:
                    
                    validate_password(password)
                except ValidationError as e:
                   
                    self.add_error('password', e)
        return cleaned_data

#EDIT PROFILE FORM
class EditProfileForm(forms.ModelForm):
    
    first_name = forms.CharField(required=True, error_messages={'required': 'First name is required.'})
    last_name = forms.CharField(required=False)
    phone = forms.CharField(required=False)

    class Meta:
        model = User
        fields =['first_name', 'last_name', 'phone', 'profile_image']

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name', '').strip()
        if first_name and not re.match(NAME_REGEX, first_name):
            raise ValidationError("First name contains invalid characters.")
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name', '').strip()
        if last_name and not re.match(NAME_REGEX, last_name):
            raise ValidationError("Last name contains invalid characters.")
        return last_name

    def clean_phone(self):
        phone = (self.cleaned_data.get('phone') or '').strip()
        if len(phone) !=10:
            raise ValidationError('phone number must be 10 digits')
        if phone and not phone.isdigit():
            raise ValidationError("Phone must contain only numbers.")
        return phone
        
    

    def clean_profile_image(self):
        image = self.cleaned_data.get('profile_image')
        if image:
            # Check if this is a NEWLY uploaded file
            if hasattr(image, 'file'):
                if image.size > 2 * 1024 * 1024:
                    raise ValidationError("Image must be smaller than 2MB.")
                if hasattr(image, 'content_type') and not image.content_type.startswith('image/'):
                    raise ValidationError("File must be a valid image format.")
        return image
    

    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'w-full px-5 py-3.5 rounded-xl border border-ink/15 bg-white text-ink focus:ring-2 focus:ring-accent-hover/30 outline-none transition'})

#  CHANGE PASSWORD FORM 
class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput)
    new_password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        
        self.user = user
        super().__init__(*args, **kwargs)
        
        
        input_style = "w-full px-5 py-4 rounded-xl border border-ink/15 bg-white text-ink placeholder-ink/30 focus:outline-none focus:ring-2 focus:ring-accent-hover"
        for field in self.fields.values():
            field.widget.attrs.update({'class': input_style})

    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
       
        if not self.user.check_password(old_password):
            raise ValidationError("Incorrect old password.")
        return old_password

    def clean_new_password(self):
        new_password = self.cleaned_data.get('new_password')
        
        validate_password(new_password, self.user)
        
        return new_password

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm = cleaned_data.get('confirm_password')

        if new_password and confirm and new_password != confirm:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data


# CHANGE EMAIL FORM 
class ChangeEmailForm(forms.Form):
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={
            'placeholder': 'name@company.com',
            
           'class': 'w-full px-5 py-4 rounded-xl border border-ink/15 bg-white text-ink focus:ring-2 focus:ring-accent-hover outline-none transition duration-200 text-lg'
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower().strip()
        if not email:
            raise ValidationError("Email is required.")
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("This email is already in use by another account.")
        return email


# ADDRESS FORM 
class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields =[
            'full_name', 'phone', 'address_line_1', 
            'city', 'state', 'postal_code', 'country', 'address_label', 'is_default'
        ]
    address_label = forms.ChoiceField(choices=[
        ('Home', 'Home'),
        ('Work', 'Work'),
        ('Other', 'Other'),
    ])
    def clean_full_name(self):
        name = self.cleaned_data.get('full_name', '').strip()
        if not name:
            raise ValidationError("Name is required.")
        if not re.match(NAME_REGEX, name):
            raise ValidationError("Name contains invalid characters.")
        return name

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if phone and not phone.isdigit():
            raise ValidationError("Phone number must contain only digits.")
        if len(phone) !=10:
            raise ValidationError('phone number must be 10 digits')
        return phone

        
    def clean_postal_code(self):
        postal_code = self.cleaned_data.get('postal_code', '').strip()
        
        # 1. Check for non-digits
        if postal_code and not postal_code.isdigit():
            raise ValidationError("Postal code must contain only digits.")
        
        # 2. Check length (India uses 6 digits)
        if len(postal_code) != 6:
            raise ValidationError("Postal code must be exactly 6 digits.")
            
        return postal_code   
    

        