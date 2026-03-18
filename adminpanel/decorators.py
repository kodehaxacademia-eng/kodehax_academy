from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please login to access the admin panel.")
            return redirect("home")

        if request.user.is_superuser or getattr(request.user, "role", None) == "admin":
            return view_func(request, *args, **kwargs)

        messages.error(request, "You are not authorized to access the admin panel.")
        user_role = getattr(request.user, "role", "")
        if user_role == "teacher":
            return redirect("teacher_dashboard")
        if user_role == "student":
            return redirect("student_dashboard")
        return redirect("home")

    return _wrapped_view

