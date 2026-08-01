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
    
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs',
    )
    
    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
    )
   
    description = models.TextField()
   
    order_number = models.CharField(
        max_length=20,
        blank=True,
        default='',
    )
   
    variant_id = models.IntegerField(
        null=True,
        blank=True,
    )
   
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
       
        verbose_name        = 'Activity Log'
        verbose_name_plural = 'Activity Logs'

    def __str__(self):
        admin_name = self.admin.email if self.admin else 'System'
        return f"[{self.get_action_display()}] by {admin_name} at {self.created_at:%d %b %Y %H:%M}"
    

def log_activity(admin, action, description, order_number='', variant_id=None):
    
    ActivityLog.objects.create(
        admin        = admin,
        action       = action,
        description  = description,
        order_number = order_number,
        variant_id   = variant_id,
    )