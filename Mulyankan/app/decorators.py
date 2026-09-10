from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Checks custom role attribute on User model or superuser flag
        is_admin = getattr(request.user, 'role', None) == 'Admin' or request.user.is_superuser
        
        if is_admin:
            return view_func(request, *args, **kwargs)
            
        raise PermissionDenied
    return _wrapped_view