from django.db import models


from django.contrib.auth import get_user_model


User = get_user_model() 

def user_list(request):
    users = User.objects.all() 
    


class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def display_status(self):
        if getattr(self, 'is_blocked', False):
            return "Blocked"
        if not getattr(self, 'is_verified', True):
            return "Pending"
        return "Active"
    
class SiteSettings(models.Model):
    """
    Singleton model — only ONE row ever exists (pk=1).
    Stores site-wide configurable settings.
    Admin can change these from the admin panel without touching code.
    """
    customization_fee = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=49,
        help_text='Fee charged when a customer adds custom text or image to a product.',
    )

    class Meta:
        verbose_name        = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return 'Site Settings'

    def save(self, *args, **kwargs):
        # Force pk=1 so only one row ever exists
        # If you try to create a second SiteSettings, it just updates the first
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        # Always use this to get settings — never SiteSettings.objects.first()
        # get_or_create ensures the row exists even if never saved before
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj