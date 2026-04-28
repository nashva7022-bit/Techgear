from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    We use Email as the primary login identifier while keeping the username 
    field strictly under-the-hood for Django & Allauth compatibility.
    """
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True, null=True)

    # Security & Verification Flags
    is_blocked = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_active= models.BooleanField(default=False)
    # Profile Data
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    
    def __str__(self):
        return self.email


class Address(models.Model):
    LABEL_CHOICES = (
        ('Home', 'Home'),
        ('Work', 'Work'),
        ('Other', 'Other'),
    )

class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    # Add these fields specifically
    address_label = models.CharField(max_length=50, default="Home") 
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default="India")
    is_default = models.BooleanField(default=False)
    address_label = models.CharField(max_length=50, default="Home") # Add this
    address_line_1 = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)     
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Addresses"
        ordering =['-is_default', '-created_at'] # Puts default address at the top

    def __str__(self):
        return f"{self.address_label} - {self.city} ({self.user.email})"

    # Automatically handle the "Default" logic
    def save(self, *args, **kwargs):
        if self.is_default:
            # Set all other addresses for this user to is_default=False
            Address.objects.filter(user=self.user).update(is_default=False)
        super().save(*args, **kwargs)

class OTP(models.Model):
    """
    Stores hashed One Time Passwords for Account Verification and Password Resets.
    Includes brute-force and resend-limit tracking.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=128)  # Fits the Django hashed password format securely
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Security tracking
    attempts = models.IntegerField(default=0)
    resend_count = models.IntegerField(default=0)
    is_used = models.BooleanField(default=False)
    purpose = models.CharField(max_length=20, default='signup')

    class Meta:
        # DB Indexing makes looking up OTPs incredibly fast, even with 100,000+ users
        indexes = [
            models.Index(fields=['user', 'created_at'])
        ]
        verbose_name = "OTP"
        verbose_name_plural = "OTPs"

    def __str__(self):
        return f"OTP for {self.user.email} (Attempts: {self.attempts})"
    
    
from allauth.account.signals import user_signed_up
from django.dispatch import receiver

@receiver(user_signed_up)
def google_signup_handler(request, user, **kwargs):
    user.username = user.email
    user.is_verified = True
    user.is_active = True
    user.save()