from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from adminpanel.decorators import admin_required

from .models import DailyChallenge
from .services import (
    challenge_attempt_limit,
    challenge_dashboard_stats,
    can_access_challenge,
    get_today_challenge_set,
    level_unlock_state,
    preview_solution,
    regenerate_daily_challenges,
    refresh_challenge_set,
    submit_solution_for_challenge,
    unlock_hint,
)

User = get_user_model()


def _ensure_student(request):
    if request.user.role != "student":
        messages.error(request, "Only students can access daily coding challenges.")
        return redirect("home")
    return None


def _challenge_groups(challenge_set):
    unlocks = level_unlock_state(challenge_set)
    labels = {
        1: ("Level 1", "Easy"),
        2: ("Level 2", "Medium"),
        3: ("Level 3", "Hard"),
    }
    items = []
    ordered = list(challenge_set.challenges.select_related("problem").order_by("level", "question_number", "id"))
    for level in (1, 2, 3):
        items.append(
            {
                "level": level,
                "title": labels[level][0],
                "difficulty": labels[level][1],
                "unlocked": unlocks[level],
                "required_text": "Available now" if unlocks[level] else (
                    "Unlocks after solving 2 Easy questions" if level == 2 else "Unlocks after solving 2 Medium questions"
                ),
                "challenges": [challenge for challenge in ordered if challenge.level == level],
            }
        )
    return items


def _workspace_navigation(challenge_set, current_challenge):
    ordered = list(challenge_set.challenges.order_by("level", "question_number", "id"))
    previous_item = None
    next_item = None
    for index, item in enumerate(ordered):
        if item.id != current_challenge.id:
            continue
        if index > 0:
            previous_item = ordered[index - 1]
        if index + 1 < len(ordered):
            next_item = ordered[index + 1]
        break
    return previous_item, next_item


def _next_accessible_challenge(challenge_set, current_challenge):
    ordered = list(challenge_set.challenges.order_by("level", "question_number", "id"))
    current_index = None
    for index, item in enumerate(ordered):
        if item.id == current_challenge.id:
            current_index = index
            break
    if current_index is None:
        return None

    for item in ordered[current_index + 1:]:
        if can_access_challenge(item):
            return item
    return None


def _workspace_nav_items(challenge_set, current_challenge):
    unlocks = level_unlock_state(challenge_set)
    return [
        {
            "challenge": item,
            "current": item.id == current_challenge.id,
            "unlocked": unlocks.get(item.level, False),
        }
        for item in challenge_set.challenges.order_by("level", "question_number", "id")
    ]


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
    remaining_time = max(challenge_set.expires_at - timezone.now(), timedelta(0))

    return render(
        request,
        "daily_challenges/today.html",
        {
            "challenge_set": challenge_set,
            "remaining_time": remaining_time,
            "challenge_groups": _challenge_groups(challenge_set),
            "level_unlocks": level_unlock_state(challenge_set),
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
    if not can_access_challenge(challenge):
        messages.error(request, "This level is locked. Solve the required earlier questions first.")
        return redirect("daily_challenges_today")

    preview_payload = None
    submission_payload = None
    editor_code = challenge.latest_code or challenge.starter_code or challenge.problem.starter_code

    if request.method == "POST":
        action = request.POST.get("action", "submit")

        if action == "hint":
            hint_payload = unlock_hint(challenge)
            if not hint_payload["ok"]:
                messages.error(request, hint_payload["error"])
            else:
                messages.success(request, f"Hint {hint_payload['hints_used']} unlocked.")
            return redirect("daily_challenge_workspace", challenge_id=challenge.id)

        code = request.POST.get("code", "").rstrip()
        editor_code = code or editor_code

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
                challenge.challenge_set.refresh_from_db()
                if submission_payload["solved"]:
                    next_challenge = _next_accessible_challenge(challenge.challenge_set, challenge)
                    if next_challenge is not None:
                        return redirect("daily_challenge_workspace", challenge_id=next_challenge.id)
                    return redirect("daily_challenges_today")
        else:
            return HttpResponseBadRequest("Invalid action.")

    challenge.refresh_from_db()
    refresh_challenge_set(challenge.challenge_set)
    challenge.challenge_set.refresh_from_db()
    remaining_time = max(challenge.challenge_set.expires_at - timezone.now(), timedelta(0))
    previous_challenge, next_challenge = _workspace_navigation(challenge.challenge_set, challenge)
    unlocks = level_unlock_state(challenge.challenge_set)

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
            "level_unlocks": unlocks,
            "challenge_groups": _challenge_groups(challenge.challenge_set),
            "previous_challenge": previous_challenge,
            "next_challenge": next_challenge,
            "next_challenge_unlocked": bool(next_challenge and unlocks.get(next_challenge.level, False)),
            "workspace_nav_items": _workspace_nav_items(challenge.challenge_set, challenge),
            "visible_hints": [hint for hint in (challenge.hint1, challenge.hint2)[: challenge.hints_used] if hint],
            "attempt_limit": challenge_attempt_limit(challenge),
            "attempts_remaining": max(0, challenge_attempt_limit(challenge) - challenge.attempts),
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
