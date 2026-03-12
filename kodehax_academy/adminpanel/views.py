import json
import socket
from smtplib import SMTPException
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.forms import TeacherInvitationAdminForm, resend_teacher_invitation
from accounts.models import TeacherInvitation
from teacher.models import (
    Assignment,
    CodeSubmission,
    PerformanceRecord,
    QuizAnswer,
    Submission,
)

from .decorators import admin_required
from .models import AdminUserState

User = get_user_model()


def _render_admin(request, template_name, context):
    base_context = {
        "current_section": context.get("current_section", "dashboard"),
    }
    base_context.update(context)
    return render(request, template_name, base_context)


def _to_json(value):
    return json.dumps(value)


def _seven_day_labels(today):
    return [
        (today - timedelta(days=offset)).strftime("%d %b")
        for offset in range(6, -1, -1)
    ]


def _build_daily_map(queryset, date_key="day", value_key="total"):
    return {entry[date_key]: entry[value_key] for entry in queryset}


@admin_required
def admin_entry(request):
    return redirect("adminpanel_dashboard")


@admin_required
def dashboard(request):
    today = timezone.localdate()
    seven_days_ago = today - timedelta(days=6)
    labels = _seven_day_labels(today)

    total_students = User.objects.filter(role="student").count()
    total_teachers = User.objects.filter(role="teacher").count()
    total_assignments = Assignment.objects.count()
    active_users_today = User.objects.filter(last_login__date=today).count()

    file_submissions = Submission.objects.count()
    code_submissions = CodeSubmission.objects.count()
    quiz_submission_attempts = QuizAnswer.objects.values(
        "question__assignment_id",
        "student_id",
    ).distinct().count()
    total_submissions = file_submissions + code_submissions + quiz_submission_attempts

    expected_submissions = (
        Assignment.objects.annotate(
            enrolled_count=Count("classroom__students", distinct=True),
        ).aggregate(total=Sum("enrolled_count"))["total"]
        or 0
    )
    completion_rate = (
        round((total_submissions / expected_submissions) * 100, 2)
        if expected_submissions
        else 0
    )

    joined_qs = (
        User.objects.filter(role="student", date_joined__date__gte=seven_days_ago)
        .annotate(day=TruncDate("date_joined"))
        .values("day")
        .annotate(total=Count("id"))
    )
    student_growth_map = _build_daily_map(joined_qs)
    student_activity_values = [
        student_growth_map.get(today - timedelta(days=offset), 0)
        for offset in range(6, -1, -1)
    ]

    file_qs = (
        Submission.objects.filter(submitted_at__date__gte=seven_days_ago)
        .annotate(day=TruncDate("submitted_at"))
        .values("day")
        .annotate(total=Count("id"))
    )
    code_qs = (
        CodeSubmission.objects.filter(submitted_at__date__gte=seven_days_ago)
        .annotate(day=TruncDate("submitted_at"))
        .values("day")
        .annotate(total=Count("id"))
    )
    quiz_qs = (
        QuizAnswer.objects.filter(answered_at__date__gte=seven_days_ago)
        .annotate(day=TruncDate("answered_at"))
        .values("day", "student_id", "question__assignment_id")
        .distinct()
    )
    file_map = _build_daily_map(file_qs)
    code_map = _build_daily_map(code_qs)
    quiz_map = {}
    for row in quiz_qs:
        quiz_map[row["day"]] = quiz_map.get(row["day"], 0) + 1

    assignment_submission_values = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        assignment_submission_values.append(
            file_map.get(day, 0) + code_map.get(day, 0) + quiz_map.get(day, 0)
        )

    performance_qs = (
        PerformanceRecord.objects.filter(recorded_at__date__gte=seven_days_ago)
        .annotate(day=TruncDate("recorded_at"))
        .values("day")
        .annotate(avg_score=Avg("score"))
    )
    performance_map = {
        row["day"]: round(row["avg_score"] or 0, 2)
        for row in performance_qs
    }
    performance_values = [
        performance_map.get(today - timedelta(days=offset), 0)
        for offset in range(6, -1, -1)
    ]

    recent_users = User.objects.order_by("-date_joined")[:8]
    recent_assignments = Assignment.objects.select_related(
        "classroom",
        "classroom__teacher",
    ).order_by("-created_at")[:8]

    context = {
        "current_section": "dashboard",
        "total_students": total_students,
        "total_teachers": total_teachers,
        "total_assignments": total_assignments,
        "active_users_today": active_users_today,
        "submission_stats": {
            "total": total_submissions,
            "file": file_submissions,
            "code": code_submissions,
            "quiz": quiz_submission_attempts,
            "completion_rate": completion_rate,
        },
        "chart_labels": _to_json(labels),
        "student_activity_values": _to_json(student_activity_values),
        "assignment_submission_values": _to_json(assignment_submission_values),
        "performance_values": _to_json(performance_values),
        "recent_users": recent_users,
        "recent_assignments": recent_assignments,
    }
    return _render_admin(request, "adminpanel/dashboard.html", context)


@admin_required
def users(request):
    query = request.GET.get("q", "").strip()
    role_filter = request.GET.get("role", "").strip()
    status_filter = request.GET.get("status", "").strip()
    page_number = request.GET.get("page")
    activity_user_id = request.GET.get("activity_user")
    edit_user_id = request.GET.get("edit_user")

    user_qs = User.objects.all().order_by("-date_joined")

    if query:
        user_qs = user_qs.filter(
            Q(username__icontains=query) | Q(email__icontains=query)
        )
    if role_filter:
        user_qs = user_qs.filter(role=role_filter)
    if status_filter == "active":
        user_qs = user_qs.filter(is_active=True)
    elif status_filter == "suspended":
        user_qs = user_qs.filter(is_active=False)

    paginator = Paginator(user_qs, 15)
    page_obj = paginator.get_page(page_number)

    selected_activity_user = None
    selected_activity_records = []
    if activity_user_id:
        selected_activity_user = User.objects.filter(id=activity_user_id).first()
        if selected_activity_user:
            selected_activity_records = (
                PerformanceRecord.objects.select_related("assignment", "classroom")
                .filter(student=selected_activity_user)
                .order_by("-recorded_at")[:6]
            )

    selected_edit_user = None
    if edit_user_id:
        selected_edit_user = User.objects.filter(id=edit_user_id).first()

    context = {
        "current_section": "users",
        "page_obj": page_obj,
        "query": query,
        "role_filter": role_filter,
        "status_filter": status_filter,
        "selected_activity_user": selected_activity_user,
        "selected_activity_records": selected_activity_records,
        "selected_edit_user": selected_edit_user,
    }
    return _render_admin(request, "adminpanel/users.html", context)


@admin_required
def user_action(request, user_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request method.")

    target_user = get_object_or_404(User, id=user_id)
    action = request.POST.get("action", "").strip()

    if target_user == request.user and action in {"suspend", "delete"}:
        messages.error(request, "You cannot suspend or delete your own account.")
        return redirect("adminpanel_users")

    state, _ = AdminUserState.objects.get_or_create(user=target_user)

    if action == "suspend":
        target_user.is_active = False
        target_user.save(update_fields=["is_active"])
        state.suspended_at = timezone.now()
        state.suspension_reason = request.POST.get(
            "reason",
            "Suspended by administrator",
        )
        state.save(update_fields=["suspended_at", "suspension_reason", "updated_at"])
        messages.success(request, f"{target_user.username} suspended.")
    elif action == "activate":
        target_user.is_active = True
        target_user.save(update_fields=["is_active"])
        state.suspended_at = None
        state.suspension_reason = ""
        state.save(update_fields=["suspended_at", "suspension_reason", "updated_at"])
        messages.success(request, f"{target_user.username} activated.")
    elif action == "delete":
        username = target_user.username
        target_user.delete()
        messages.success(request, f"{username} deleted.")
    elif action == "promote_teacher":
        target_user.role = "teacher"
        target_user.save(update_fields=["role"])
        state.teacher_approval_status = AdminUserState.STATUS_PENDING
        state.save(update_fields=["teacher_approval_status", "updated_at"])
        messages.success(request, f"{target_user.username} promoted to teacher.")
    else:
        messages.error(request, "Unsupported action.")

    return redirect("adminpanel_users")


@admin_required
def user_edit(request, user_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request method.")

    target_user = get_object_or_404(User, id=user_id)
    target_user.email = request.POST.get("email", target_user.email).strip()

    requested_role = request.POST.get("role", target_user.role).strip()
    if requested_role in {"student", "teacher", "admin"}:
        target_user.role = requested_role

    target_user.is_active = request.POST.get("is_active") == "on"
    target_user.save(update_fields=["email", "role", "is_active"])
    messages.success(request, f"{target_user.username} updated successfully.")
    return redirect("adminpanel_users")


@admin_required
def teachers(request):
    query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    page_number = request.GET.get("page")

    teacher_qs = (
        User.objects.filter(role="teacher")
        .select_related("teacher_profile", "adminpanel_state")
        .annotate(
            classes_count=Count("teacher_classes", distinct=True),
            assignments_count=Count("teacher_classes__assignments", distinct=True),
        )
        .order_by("-date_joined")
    )

    if query:
        teacher_qs = teacher_qs.filter(
            Q(username__icontains=query) | Q(email__icontains=query)
        )
    if status_filter:
        teacher_qs = teacher_qs.filter(
            adminpanel_state__teacher_approval_status=status_filter
        )

    paginator = Paginator(teacher_qs, 12)
    page_obj = paginator.get_page(page_number)
    for teacher in page_obj:
        try:
            teacher.approval_status = teacher.adminpanel_state.teacher_approval_status
        except AdminUserState.DoesNotExist:
            teacher.approval_status = AdminUserState.STATUS_PENDING

    context = {
        "current_section": "teachers",
        "page_obj": page_obj,
        "query": query,
        "status_filter": status_filter,
        "invitation_form": TeacherInvitationAdminForm(),
        "pending_invitations": TeacherInvitation.objects.filter(is_used=False)[:10],
    }
    return _render_admin(request, "adminpanel/teachers.html", context)


@admin_required
def invite_teacher(request):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request method.")

    form = TeacherInvitationAdminForm(request.POST)
    if form.is_valid():
        try:
            invitation = form.save(request=request)
        except (SMTPException, TimeoutError, OSError, socket.timeout) as exc:
            messages.error(
                request,
                "Invitation email could not be sent. Check SMTP settings, network access, and the sender credentials.",
            )
            messages.error(request, f"Mail error: {exc}")
        else:
            action = "Invitation sent" if getattr(invitation, "was_created", False) else "Invitation re-sent"
            messages.success(request, f"{action} to {invitation.email}.")
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
    return redirect("adminpanel_teachers")


@admin_required
def resend_teacher_invite(request, invitation_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request method.")

    invitation = get_object_or_404(TeacherInvitation, id=invitation_id)
    try:
        resend_teacher_invitation(request, invitation)
    except (SMTPException, TimeoutError, OSError, socket.timeout) as exc:
        messages.error(
            request,
            "Invitation email could not be re-sent. Check SMTP settings, network access, and the sender credentials.",
        )
        messages.error(request, f"Mail error: {exc}")
    else:
        messages.success(request, f"Invitation re-sent to {invitation.email}.")
    return redirect("adminpanel_teachers")


@admin_required
def delete_teacher_invite(request, invitation_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request method.")

    invitation = get_object_or_404(TeacherInvitation, id=invitation_id)
    invitation_email = invitation.email
    invitation.delete()
    messages.success(request, f"Invitation data deleted for {invitation_email}.")
    return redirect("adminpanel_teachers")


@admin_required
def teacher_action(request, teacher_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request method.")

    teacher_user = get_object_or_404(User, id=teacher_id, role="teacher")
    action = request.POST.get("action", "").strip()
    state, _ = AdminUserState.objects.get_or_create(user=teacher_user)

    if action == "approve":
        state.teacher_approval_status = AdminUserState.STATUS_APPROVED
        teacher_user.is_active = True
        teacher_user.save(update_fields=["is_active"])
        state.save(update_fields=["teacher_approval_status", "updated_at"])
        messages.success(request, f"{teacher_user.username} approved.")
    elif action == "reject":
        state.teacher_approval_status = AdminUserState.STATUS_REJECTED
        teacher_user.is_active = False
        teacher_user.save(update_fields=["is_active"])
        state.save(update_fields=["teacher_approval_status", "updated_at"])
        messages.success(request, f"{teacher_user.username} rejected.")
    elif action == "remove":
        username = teacher_user.username
        teacher_user.delete()
        messages.success(request, f"{username} removed.")
    else:
        messages.error(request, "Unsupported action.")

    return redirect("adminpanel_teachers")


@admin_required
def students(request):
    query = request.GET.get("q", "").strip()
    page_number = request.GET.get("page")

    student_qs = (
        User.objects.filter(role="student")
        .select_related()
        .annotate(
            classes_count=Count("enrolled_classes", distinct=True),
            submissions_count=Count("performance_records", distinct=True),
            average_score=Avg("performance_records__score"),
        )
        .order_by("-date_joined")
    )

    if query:
        student_qs = student_qs.filter(
            Q(username__icontains=query) | Q(email__icontains=query)
        )

    paginator = Paginator(student_qs, 12)
    page_obj = paginator.get_page(page_number)

    context = {
        "current_section": "students",
        "page_obj": page_obj,
        "query": query,
    }
    return _render_admin(request, "adminpanel/students.html", context)


@admin_required
def student_action(request, student_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request method.")

    student_user = get_object_or_404(User, id=student_id, role="student")
    action = request.POST.get("action", "").strip()

    if action == "remove":
        username = student_user.username
        student_user.delete()
        messages.success(request, f"{username} removed.")
    elif action == "suspend":
        student_user.is_active = False
        student_user.save(update_fields=["is_active"])
        state, _ = AdminUserState.objects.get_or_create(user=student_user)
        state.suspended_at = timezone.now()
        state.suspension_reason = "Suspended by administrator"
        state.save(update_fields=["suspended_at", "suspension_reason", "updated_at"])
        messages.success(request, f"{student_user.username} suspended.")
    else:
        messages.error(request, "Unsupported action.")

    return redirect("adminpanel_students")


@admin_required
def assignments(request):
    query = request.GET.get("q", "").strip()
    low_completion_only = request.GET.get("low_completion") == "1"
    page_number = request.GET.get("page")

    assignment_qs = (
        Assignment.objects.select_related("classroom", "classroom__teacher")
        .annotate(
            enrolled_students=Count("classroom__students", distinct=True),
            file_submission_count=Count("submissions", distinct=True),
            code_submission_count=Count("code_submissions", distinct=True),
            quiz_submission_count=Count("quiz_questions__answers__student", distinct=True),
        )
        .order_by("-created_at")
    )

    if query:
        assignment_qs = assignment_qs.filter(
            Q(title__icontains=query)
            | Q(classroom__name__icontains=query)
            | Q(classroom__teacher__username__icontains=query)
        )

    assignment_rows = []
    for assignment in assignment_qs:
        total_submissions = (
            assignment.file_submission_count
            + assignment.code_submission_count
            + assignment.quiz_submission_count
        )
        completion_rate = (
            round((total_submissions / assignment.enrolled_students) * 100, 2)
            if assignment.enrolled_students
            else 0
        )
        is_low_completion = completion_rate < 50
        if low_completion_only and not is_low_completion:
            continue
        assignment_rows.append(
            {
                "assignment": assignment,
                "total_submissions": total_submissions,
                "completion_rate": completion_rate,
                "is_low_completion": is_low_completion,
            }
        )

    paginator = Paginator(assignment_rows, 12)
    page_obj = paginator.get_page(page_number)

    context = {
        "current_section": "assignments",
        "page_obj": page_obj,
        "query": query,
        "low_completion_only": low_completion_only,
    }
    return _render_admin(request, "adminpanel/assignments.html", context)


@admin_required
def assignment_action(request, assignment_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request method.")

    assignment = get_object_or_404(Assignment, id=assignment_id)
    action = request.POST.get("action", "").strip()
    if action == "delete":
        title = assignment.title
        assignment.delete()
        messages.success(request, f"Assignment '{title}' deleted.")
    else:
        messages.error(request, "Unsupported action.")
    return redirect("adminpanel_assignments")


@admin_required
def analytics(request):
    today = timezone.localdate()
    start_month = (today.replace(day=1) - timedelta(days=150)).replace(day=1)

    month_points = []
    cursor = start_month
    while cursor <= today.replace(day=1):
        month_points.append(cursor)
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)

    month_labels = [point.strftime("%b %Y") for point in month_points]

    student_growth_qs = (
        User.objects.filter(role="student", date_joined__date__gte=start_month)
        .annotate(month=TruncMonth("date_joined"))
        .values("month")
        .annotate(total=Count("id"))
    )
    teacher_growth_qs = (
        User.objects.filter(role="teacher", date_joined__date__gte=start_month)
        .annotate(month=TruncMonth("date_joined"))
        .values("month")
        .annotate(total=Count("id"))
    )
    completion_qs = (
        PerformanceRecord.objects.filter(recorded_at__date__gte=start_month)
        .annotate(month=TruncMonth("recorded_at"))
        .values("month")
        .annotate(
            total=Count("id"),
            graded=Count("id", filter=Q(score__isnull=False)),
        )
    )

    student_map = {row["month"].date(): row["total"] for row in student_growth_qs}
    teacher_map = {row["month"].date(): row["total"] for row in teacher_growth_qs}
    completion_map = {
        row["month"].date(): round((row["graded"] / row["total"]) * 100, 2)
        if row["total"]
        else 0
        for row in completion_qs
    }

    student_growth_values = [student_map.get(point, 0) for point in month_points]
    teacher_growth_values = [teacher_map.get(point, 0) for point in month_points]
    completion_values = [completion_map.get(point, 0) for point in month_points]

    top_students = (
        User.objects.filter(role="student")
        .annotate(
            avg_score=Avg("performance_records__score"),
            submission_count=Count("performance_records"),
        )
        .filter(submission_count__gt=0)
        .order_by("-avg_score")[:8]
    )

    active_teachers = (
        User.objects.filter(role="teacher")
        .annotate(
            class_count=Count("teacher_classes", distinct=True),
            assignment_count=Count("teacher_classes__assignments", distinct=True),
        )
        .order_by("-assignment_count", "-class_count")[:8]
    )

    context = {
        "current_section": "analytics",
        "month_labels": _to_json(month_labels),
        "student_growth_values": _to_json(student_growth_values),
        "teacher_growth_values": _to_json(teacher_growth_values),
        "completion_values": _to_json(completion_values),
        "top_students": top_students,
        "active_teachers": active_teachers,
    }
    return _render_admin(request, "adminpanel/analytics.html", context)
