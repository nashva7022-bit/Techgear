from django.db import models

# Create your models here.
from django.contrib.auth import get_user_model

# This pulls the User model from your 'users' app 
# so you can manage them without creating a new model here.
User = get_user_model() 

def user_list(request):
    users = User.objects.all() # Accessing the existing database
    
    ...

class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)