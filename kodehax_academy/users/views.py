from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import User

def home(request):
    return render(request, "user/base.html")


def _redirect_for_role(role):
    return "teacher_dashboard" if role == "teacher" else "student_dashboard"


def _block_cross_role_login(request, target_role):
    if not request.user.is_authenticated:
        return None

    if request.user.role == target_role:
        return redirect(_redirect_for_role(target_role))

    messages.error(
        request,
        (
            f"You are already logged in as {request.user.role} in this browser session. "
            "Use Logout first, or open the other role in an incognito window / different browser profile."
        ),
    )
    return redirect(_redirect_for_role(request.user.role))
# -------------------------
# Student Register
# -------------------------
def student_register(request):

    if request.method == "POST":

        username = request.POST.get("username")
        email = request.POST.get("email")
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")

        if password1 != password2:
            messages.error(request, "Passwords do not match")
            return redirect("student_register")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect("student_register")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect("student_register")

        User.objects.create_user(
            username=username,
            email=email,
            password=password1,
            role="student"
        )

        messages.success(request, "Student account created successfully")
        return redirect("student_login")

    return render(request, "user/register/std_register.html")


# -------------------------
# Teacher Register
# -------------------------
def teacher_register(request):

    if request.method == "POST":

        username = request.POST.get("username")
        email = request.POST.get("email")
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")

        if password1 != password2:
            messages.error(request, "Passwords do not match")
            return redirect("teacher_register")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect("teacher_register")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect("teacher_register")

        User.objects.create_user(
            username=username,
            email=email,
            password=password1,
            role="teacher"
        )

        messages.success(request, "Teacher account created successfully")
        return redirect("teacher_login")

    return render(request, "user/register/teacher_register.html")


# -------------------------
# Student Login
# -------------------------
def student_login(request):
    block_response = _block_cross_role_login(request, "student")
    if block_response:
        return block_response

    if request.method == "POST":

        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, "Invalid username or password")
            return redirect("student_login")

        if user.role != "student":
            messages.error(request, "This account is not a student account")
            return redirect("student_login")

        login(request, user)
        return redirect("student_dashboard")

    return render(request, "user/login/std_login.html")


# -------------------------
# Teacher Login
# -------------------------
def teacher_login(request):
    block_response = _block_cross_role_login(request, "teacher")
    if block_response:
        return block_response

    if request.method == "POST":

        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, "Invalid username or password")
            return redirect("teacher_login")

        if user.role != "teacher":
            messages.error(request, "This account is not a teacher account")
            return redirect("teacher_login")

        login(request, user)
        return redirect("/teacher/dashboard/")

    return render(request, "user/login/teacher_login.html")


def user_logout(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect("home")
