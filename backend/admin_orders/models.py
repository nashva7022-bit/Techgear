from django.db import models



from django.db import models
from django.conf import settings
from django.utils import timezone


class ActivityLog(models.Model):

    #  ACTION TYPE CHOICES
    ACTION_CHOICES = [
        ('order_status_change', 'Order Status Changed'),
        ('stock_update',        'Stock Updated'),
        ('order_cancel',        'Order Cancelled'),
        ('order_view',          'Order Viewed'),
    ]
    

    # WHO DID IT
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs',
    )
    # The admin user who performed the action.
    

    # WHAT WAS DONE 
    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
    )
    # The type of action performed.
    

    description = models.TextField()
    # Human-readable description of what happened.
    

    # WHAT IT AFFECTED 

    order_number = models.CharField(
        max_length=20,
        blank=True,
        default='',
    )
    # If the action was order-related, store the order number here.
    

    variant_id = models.IntegerField(
        null=True,
        blank=True,
    )
    # If the action was stock-related, store the variant ID here.
    

    # WHEN 
    created_at = models.DateTimeField(default=timezone.now)
    # When the action was performed.
   

    class Meta:
        ordering = ['-created_at']
        # Newest actions first — most relevant for admin reviewing recent activity.

        verbose_name        = 'Activity Log'
        verbose_name_plural = 'Activity Logs'

    def __str__(self):
        admin_name = self.admin.email if self.admin else 'System'
        return f"[{self.get_action_display()}] by {admin_name} at {self.created_at:%d %b %Y %H:%M}"
    # e.g. "[Order Status Changed] by admin@techgear.com at 12 May 2026 10:30"


#  HELPER FUNCTION 

def log_activity(admin, action, description, order_number='', variant_id=None):
    
    ActivityLog.objects.create(
        admin        = admin,
        action       = action,
        description  = description,
        order_number = order_number,
        variant_id   = variant_id,
    )