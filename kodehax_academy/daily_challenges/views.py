from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from adminpanel.decorators import admin_required

from .models import DailyChallenge
from .services import (
    challenge_dashboard_stats,
    get_today_challenge_set,
    preview_solution,
    regenerate_daily_challenges,
    refresh_challenge_set,
    submit_solution_for_challenge,
)

User = get_user_model()


def _ensure_student(request):
    if request.user.role != "student":
        messages.error(request, "Only students can access daily coding challenges.")
        return redirect("home")
    return None


@login_required
def today_challenges(request):
    redirect_response = _ensure_student(request)
    if redirect_response:
        return redirect_response

    challenge_set = get_today_challenge_set(request.user)
    refresh_challenge_set(challenge_set)
    challenge_set.refresh_from_db()
    challenge_set = (
        challenge_set.__class__.objects.filter(id=challenge_set.id)
        .prefetch_related("challenges__problem")
        .get()
    )
    solved_count = challenge_set.challenges.filter(status=DailyChallenge.STATUS_SOLVED).count()
    remaining_time = max(challenge_set.expires_at - timezone.now(), timedelta(0))

    return render(
        request,
        "daily_challenges/today.html",
        {
            "challenge_set": challenge_set,
            "solved_count": solved_count,
            "remaining_time": remaining_time,
        },
    )


@login_required
def submit_solution(request, challenge_id):
    redirect_response = _ensure_student(request)
    if redirect_response:
        return redirect_response

    challenge = get_object_or_404(
        DailyChallenge.objects.select_related("student", "problem", "challenge_set"),
        id=challenge_id,
        student=request.user,
    )
    refresh_challenge_set(challenge.challenge_set)

    preview_payload = None
    submission_payload = None
    editor_code = challenge.latest_code or challenge.problem.starter_code

    if request.method == "POST":
        code = request.POST.get("code", "").rstrip()
        editor_code = code or editor_code
        action = request.POST.get("action", "submit")
        if not code:
            messages.error(request, "Code cannot be empty.")
            return redirect("daily_challenge_workspace", challenge_id=challenge.id)

        if action == "run":
            preview_payload = preview_solution(challenge, code)
            if not preview_payload["allowed"]:
                messages.error(request, preview_payload["error"])
            else:
                messages.success(request, "Test run completed.")
        elif action == "submit":
            submission_payload = submit_solution_for_challenge(challenge, code)
            if not submission_payload["ok"]:
                messages.error(request, submission_payload["error"])
            else:
                messages.success(request, submission_payload["message"])
                challenge.refresh_from_db()
        else:
            return HttpResponseBadRequest("Invalid action.")

    challenge.refresh_from_db()
    remaining_time = max(challenge.challenge_set.expires_at - timezone.now(), timedelta(0))

    return render(
        request,
        "daily_challenges/workspace.html",
        {
            "challenge": challenge,
            "challenge_set": challenge.challenge_set,
            "remaining_time": remaining_time,
            "preview_payload": preview_payload,
            "submission_payload": submission_payload,
            "editor_code": editor_code,
        },
    )


@admin_required
def adminpanel_daily_challenges(request):
    stats = challenge_dashboard_stats()
    return render(
        request,
        "adminpanel/daily_challenges.html",
        {
            "current_section": "daily_challenges",
            **stats,
        },
    )


@admin_required
def adminpanel_regenerate_daily_challenges(request):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request method.")

    student_id = request.POST.get("student_id")
    if student_id:
        student = get_object_or_404(User, id=student_id, role="student")
        regenerate_daily_challenges(student=student)
        messages.success(request, f"Daily challenges regenerated for {student.username}.")
    else:
        regenerate_daily_challenges()
        messages.success(request, "Daily challenges regenerated for all students.")
    return redirect("adminpanel_daily_challenges")
