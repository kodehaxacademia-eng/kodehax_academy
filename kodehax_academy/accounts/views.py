from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode

from .forms import (
    ForgotPasswordForm,
    LoginForm,
    ResetPasswordForm,
    StudentRegistrationForm,
    TeacherInviteRegistrationForm,
    send_password_reset_email,
    send_verification_email,
)
from .models import TeacherInvitation
from .tokens import email_verification_token, teacher_invitation_token

User = get_user_model()


def _decode_uid(uid):
    try:
        return force_str(urlsafe_base64_decode(uid))
    except (TypeError, ValueError, OverflowError):
        return None


def _render(request, template_name, context=None, status=200):
    return render(request, template_name, context or {}, status=status)


def register(request):
    form = StudentRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        send_verification_email(request, user)
        messages.success(request, "Account created. Check your email to verify your account before logging in.")
        return redirect("student_login")
    return _render(request, "accounts/register.html", {"form": form, "page_title": "Student registration"})


def verify_email(request, uid, token):
    user_id = _decode_uid(uid)
    user = User.objects.filter(pk=user_id).first() if user_id else None
    verified = False

    if user and email_verification_token.check_token(user, token):
        if not user.is_email_verified or not user.is_active:
            user.is_active = True
            user.is_email_verified = True
            user.save(update_fields=["is_active", "is_email_verified"])
        verified = True
        messages.success(request, "Email verified. You can log in now.")
    elif user and user.is_email_verified:
        verified = True

    return _render(
        request,
        "accounts/verify_email.html",
        {"verified": verified, "login_url": reverse("student_login")},
        status=200 if verified else 400,
    )


def _login_user(request, role, template_name):
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if request.user.is_authenticated:
            current_role = "admin" if request.user.is_superuser or request.user.role == "admin" else request.user.role
            logout(request)
            messages.info(request, f"Previous {current_role} session cleared. Signing you into the requested portal.")

        username = form.cleaned_data["username"].strip()
        password = form.cleaned_data["password"]
        user = User.objects.filter(username__iexact=username).first()

        if not user or not user.check_password(password):
            messages.error(request, "Invalid username or password")
            return redirect(request.resolver_match.view_name)

        if role == "student" and user.role != "student":
            messages.error(request, "This account is not a student account")
            return redirect("student_login")

        if role == "teacher" and not (user.role == "teacher" or user.role == "admin" or user.is_superuser):
            messages.error(request, "This account is not a teacher or admin account")
            return redirect("teacher_login")

        if not user.is_email_verified and not user.is_superuser and user.role != "admin":
            messages.error(request, "Please verify your email before logging in.")
            return redirect(request.resolver_match.view_name)

        if not user.is_active and not user.is_superuser and user.role != "admin":
            messages.error(request, "Your account is inactive. Please contact support.")
            return redirect(request.resolver_match.view_name)

        authenticated_user = authenticate(request, username=user.username, password=password)
        if authenticated_user is None:
            messages.error(request, "Invalid username or password")
            return redirect(request.resolver_match.view_name)

        login(request, authenticated_user)
        if authenticated_user.is_superuser or authenticated_user.role == "admin":
            return redirect("adminpanel_dashboard")
        return redirect("teacher_dashboard" if authenticated_user.role == "teacher" else "student_dashboard")

    return _render(request, template_name, {"form": form})


def student_login(request):
    return _login_user(request, "student", "user/login/std_login.html")


def teacher_login(request):
    return _login_user(request, "teacher", "user/login/teacher_login.html")


def teacher_register_disabled(request):
    messages.error(request, "Teacher accounts are created through an admin invitation only.")
    return redirect("teacher_login")


def forgot_password(request):
    form = ForgotPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        user = User.objects.filter(email__iexact=email).first()
        if user:
            send_password_reset_email(request, user)
        messages.success(request, "If that email exists in our system, a password reset link has been sent.")
        return redirect("forgot_password")
    return _render(request, "accounts/forgot_password.html", {"form": form})


def reset_password(request, uid, token):
    user_id = _decode_uid(uid)
    user = User.objects.filter(pk=user_id).first() if user_id else None
    token_valid = bool(user and default_token_generator.check_token(user, token))
    form = ResetPasswordForm(user=user, data=request.POST or None) if token_valid else None

    if request.method == "POST" and token_valid and form and form.is_valid():
        user.set_password(form.cleaned_data["password1"])
        user.save(update_fields=["password"])
        messages.success(request, "Password updated successfully. You can log in now.")
        return redirect("student_login" if user.role == "student" else "teacher_login")

    return _render(
        request,
        "accounts/reset_password.html",
        {
            "form": form,
            "token_valid": token_valid,
        },
        status=200 if token_valid else 400,
    )


def teacher_invite_register(request, uid, token):
    invitation_id = _decode_uid(uid)
    invitation = TeacherInvitation.objects.filter(pk=invitation_id).first() if invitation_id else None
    token_valid = bool(invitation and not invitation.is_used and teacher_invitation_token.check_token(invitation, token))
    form = TeacherInviteRegistrationForm(invitation=invitation, data=request.POST or None) if token_valid else None

    if request.method == "POST" and token_valid and form and form.is_valid():
        form.save()
        messages.success(request, "Teacher account created. You can log in now.")
        return redirect("teacher_login")

    return _render(
        request,
        "accounts/teacher_invite_register.html",
        {
            "form": form,
            "token_valid": token_valid,
            "invitation": invitation,
        },
        status=200 if token_valid else 400,
    )
