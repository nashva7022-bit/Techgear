from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def admin_required(view_func):

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_staff:
            return view_func(request, *args, **kwargs)
        else:
            messages.error(request, "Access denied. Admin privileges required.")
            return redirect("admin_login")

    return _wrapped_view
