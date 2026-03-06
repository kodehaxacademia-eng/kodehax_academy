from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required


@login_required(login_url="login")
def teacher_dashboard(request):
    if getattr(request.user, "role", None) != "teacher":
        return redirect("login")
    return render(request, "teacher/dashboard.html")