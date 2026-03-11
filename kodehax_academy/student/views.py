from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import StudentProfile
import json
import requests #type: ignore
import re
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from chat.views import RESPONSE_STYLE_INSTRUCTION, format_ai_reply
from daily_challenges.services import get_today_challenge_set
from skill_assessment.models import StudentSkill
from teacher.models import (
    Assignment,
    ClassRoom,
    CodeSubmission,
    QuizAnswer,
    QuizQuestion,
    QuizResult,
    Submission,
)
from teacher.services.evaluation import evaluate_quiz_for_student
from teacher.services.performance import (
    get_student_performance_summary,
    sync_code_submission_record,
    sync_file_submission_record,
)

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "llama3:latest"

CODE_FENCE_PATTERN = re.compile(r"```[\w+-]*\n[\s\S]*?\n```")

def build_system_prompt(mode):
    prompts = {
        "tutor": "You are a helpful AI tutor for students. Answer questions clearly and educationally.",
        "quiz": "You are a quiz generator. Create multiple choice questions based on the topic given.",
        "summarize": "You are a lesson summarizer. Summarize the given content in simple, student-friendly language.",
        "course_qa": "You are a course assistant. Answer only questions related to the course material provided.",
    }
    return f"{prompts.get(mode, prompts['tutor'])}\n\n{RESPONSE_STYLE_INSTRUCTION}"

@csrf_exempt
def llama_chat(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        body = json.loads(request.body)
        user_message = body.get("message", "")
        mode = body.get("mode", "tutor")
        history = body.get("history", [])
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not user_message:
        return JsonResponse({"error": "Message is required"}, status=400)

    messages = [{"role": "system", "content": build_system_prompt(mode)}]
    messages += history
    messages.append({"role": "user", "content": user_message})

    try:
        response = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "messages": messages,
            "stream": False
        }, timeout=60)
        data = response.json()
        reply = format_ai_reply(data["message"]["content"])
        has_code = bool(CODE_FENCE_PATTERN.search(reply))
        return JsonResponse({"reply": reply, "has_code": has_code})
    
    except requests.exceptions.ConnectionError as e:
        return JsonResponse({"error": f"ConnectionError: {str(e)}"}, status=500)
    except requests.exceptions.Timeout as e:
        return JsonResponse({"error": f"Timeout: {str(e)}"}, status=500)
    except KeyError as e:
        return JsonResponse({"error": f"KeyError - unexpected response: {str(e)}", "raw": data}, status=500)
    except Exception as e:
        return JsonResponse({"error": f"Unknown error: {type(e).__name__}: {str(e)}"}, status=500)

def chat_page(request):
    return render(request, 'student/chat.html')


def _ensure_student(request):
    if request.user.role != "student":
        messages.error(
            request,
            "Student portal access denied for current session. Use a separate browser profile/incognito for parallel logins."
        )
        return redirect("home")
    return None


def _build_assignment_rows(assignments, student):
    assignment_list = list(assignments)
    assignment_ids = [assignment.id for assignment in assignment_list]

    file_submissions = Submission.objects.filter(
        student=student,
        assignment_id__in=assignment_ids
    ).select_related("assignment")
    file_submission_map = {
        submission.assignment_id: submission for submission in file_submissions
    }

    code_submissions = CodeSubmission.objects.filter(
        student=student,
        assignment_id__in=assignment_ids
    ).select_related("assignment")
    code_submission_map = {
        submission.assignment_id: submission for submission in code_submissions
    }

    quiz_result_map = {
        result.assignment_id: result
        for result in QuizResult.objects.filter(
            student=student,
            assignment_id__in=assignment_ids
        )
    }
    quiz_attempted_ids = set(
        QuizAnswer.objects.filter(
            student=student,
            question__assignment_id__in=assignment_ids
        ).values_list("question__assignment_id", flat=True).distinct()
    )

    rows = []
    for assignment in assignment_list:
        row = {
            "assignment": assignment,
            "status_label": "Pending",
            "status_class": "amber",
            "action_label": "Open",
            "can_submit": True,
        }

        if assignment.assignment_type == Assignment.ASSIGNMENT_TYPE_FILE:
            row["submission"] = file_submission_map.get(assignment.id)
            row["action_label"] = "Submit"
            if row["submission"]:
                row["status_label"] = "Submitted"
                row["status_class"] = "emerald"
                if assignment.allows_multiple_attempts:
                    row["action_label"] = "Re-submit"
                else:
                    row["action_label"] = "View Submission"
        elif assignment.assignment_type == Assignment.ASSIGNMENT_TYPE_CODE:
            row["submission"] = code_submission_map.get(assignment.id)
            row["action_label"] = "Write Code"
            if row["submission"]:
                row["status_label"] = "Submitted"
                row["status_class"] = "emerald"
                if assignment.allows_multiple_attempts:
                    row["action_label"] = "Update Code"
                else:
                    row["action_label"] = "View Submission"
        else:
            row["submission"] = quiz_result_map.get(assignment.id)
            row["action_label"] = "Take Quiz"
            attempted = row["submission"] or assignment.id in quiz_attempted_ids
            if attempted:
                row["status_class"] = "emerald"
                if assignment.allows_multiple_attempts:
                    row["status_label"] = "Attempted"
                    row["action_label"] = "Retake Quiz"
                else:
                    row["status_label"] = "Completed"
                    row["action_label"] = "View Quiz"
        rows.append(row)
    return rows


def _parse_quiz_questions_from_description(raw_text):
    if not raw_text:
        return []
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    questions = []
    current = None
    question_pattern = re.compile(r"^Q\s*\d+\s*[)\.:]?\s*(.+)$", re.IGNORECASE)
    option_pattern = re.compile(r"^([ABCD])[)\.:]\s*(.+)$", re.IGNORECASE)

    def finalize_current():
        if current and all(current.get(opt) for opt in ("A", "B", "C", "D")):
            questions.append(current.copy())

    for line in lines:
        q_match = question_pattern.match(line)
        if q_match:
            finalize_current()
            current = {
                "question": q_match.group(1).strip(),
                "A": "",
                "B": "",
                "C": "",
                "D": "",
            }
            continue

        if not current:
            continue

        o_match = option_pattern.match(line)
        if o_match:
            current[o_match.group(1).upper()] = o_match.group(2).strip()
            continue

        if not any(current.get(opt) for opt in ("A", "B", "C", "D")):
            current["question"] = f"{current['question']} {line}".strip()

    finalize_current()
    return questions

@login_required
def student_dashboard(request):
    redirect_response = _ensure_student(request)
    if redirect_response:
        return redirect_response

    skill_profile = StudentSkill.objects.filter(student=request.user).first()
    if not skill_profile:
        return redirect("skill_assessment_entry")

    profile, _ = StudentProfile.objects.get_or_create(user=request.user)

    joined_classes = ClassRoom.objects.filter(
        students=request.user
    ).select_related("teacher").prefetch_related("assignments").order_by("-created_at")

    daily_challenge_set = get_today_challenge_set(request.user)
    solved_daily_count = daily_challenge_set.challenges.filter(status="solved").count()

    assignments = Assignment.objects.filter(
        classroom__students=request.user,
        due_date__gte=timezone.now(),
    ).select_related("classroom")
    assignment_rows = _build_assignment_rows(assignments, request.user)
    submission_map = {row["assignment"].id: row for row in assignment_rows}

    return render(request, "student/dashboard.html", {
        "profile": profile,
        "joined_classes": joined_classes,
        "submission_map": submission_map,
        "skill_profile": skill_profile,
        "medium_topics": skill_profile.assessment_snapshot.get("medium_topics", []),
        "daily_challenge_set": daily_challenge_set,
        "solved_daily_count": solved_daily_count,
    })

@login_required
def join_classroom(request):
    redirect_response = _ensure_student(request)
    if redirect_response:
        return redirect_response

    if request.method == "POST":
        class_code = request.POST.get("class_code", "").strip().upper()
        if not class_code:
            messages.error(request, "Please enter a class code.")
            return redirect("student_dashboard")

        classroom = ClassRoom.objects.filter(
            class_code=class_code,
            is_active=True
        ).first()

        if not classroom:
            messages.error(request, "Invalid or inactive class code.")
            return redirect("student_dashboard")

        classroom.students.add(request.user)
        messages.success(
            request,
            f"You joined {classroom.name}."
        )
    return redirect("student_dashboard")

@login_required
def class_detail(request, class_id):
    redirect_response = _ensure_student(request)
    if redirect_response:
        return redirect_response

    classroom = get_object_or_404(
        ClassRoom.objects.select_related("teacher"),
        id=class_id,
        students=request.user
    )

    assignments = classroom.assignments.filter(
        due_date__gte=timezone.now()
    ).order_by("due_date")
    assignment_rows = _build_assignment_rows(assignments, request.user)

    return render(request, "student/class_detail.html", {
        "classroom": classroom,
        "assignment_rows": assignment_rows,
    })


@login_required
def view_assignments(request):
    redirect_response = _ensure_student(request)
    if redirect_response:
        return redirect_response

    assignments = Assignment.objects.filter(
        classroom__students=request.user,
        due_date__gte=timezone.now(),
    ).select_related("classroom", "classroom__teacher").order_by("due_date")

    assignment_rows = _build_assignment_rows(assignments, request.user)

    return render(request, "student/assignment/view_assignment.html", {
        "assignment_rows": assignment_rows,
    })


@login_required
def student_performance_dashboard(request):
    redirect_response = _ensure_student(request)
    if redirect_response:
        return redirect_response

    analytics = get_student_performance_summary(request.user)
    summary = analytics["summary"]
    charts = analytics["charts"]

    return render(request, "student/performance.html", {
        "summary": summary,
        "records": analytics["records"],
        "score_progression_labels": json.dumps(charts["score_progression_labels"]),
        "score_progression_values": json.dumps(charts["score_progression_values"]),
        "assignment_score_labels": json.dumps(charts["assignment_score_labels"]),
        "assignment_score_values": json.dumps(charts["assignment_score_values"]),
        "submission_trend_labels": json.dumps(charts["submission_trend_labels"]),
        "submission_trend_values": json.dumps(charts["submission_trend_values"]),
    })


@login_required
def submit_assignment(request, assignment_id):
    redirect_response = _ensure_student(request)
    if redirect_response:
        return redirect_response

    assignment = get_object_or_404(
        Assignment.objects.select_related("classroom", "classroom__teacher"),
        id=assignment_id,
        classroom__students=request.user
    )
    if assignment.due_date < timezone.now():
        messages.error(request, "This assignment deadline has passed.")
        return redirect("view_assignments")

    if assignment.assignment_type == Assignment.ASSIGNMENT_TYPE_QUIZ:
        return redirect("take_quiz_assignment", assignment_id=assignment.id)
    if assignment.assignment_type == Assignment.ASSIGNMENT_TYPE_CODE:
        return redirect("submit_code_assignment", assignment_id=assignment.id)

    existing_submission = Submission.objects.filter(
        assignment=assignment,
        student=request.user
    ).first()
    can_submit = assignment.allows_multiple_attempts or not existing_submission

    if request.method == "POST":
        if not can_submit:
            messages.error(request, "This assignment allows only one attempt.")
            return redirect("submit_assignment", assignment_id=assignment.id)

        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            messages.error(request, "Please select a file to submit.")
            return redirect("submit_assignment", assignment_id=assignment.id)

        if existing_submission:
            existing_submission.file = uploaded_file
            existing_submission.save(update_fields=["file"])
            sync_file_submission_record(existing_submission, evaluation_type="manual")
            success_message = "Assignment re-submitted successfully."
        else:
            submission = Submission.objects.create(
                assignment=assignment,
                student=request.user,
                file=uploaded_file,
            )
            sync_file_submission_record(submission, evaluation_type="manual")
            success_message = "Assignment submitted successfully."

        messages.success(request, success_message)
        return redirect("view_assignments")

    return render(request, "student/assignment/submit_assignment.html", {
        "assignment": assignment,
        "existing_submission": existing_submission,
        "can_submit": can_submit,
    })


@login_required
def take_quiz_assignment(request, assignment_id):
    redirect_response = _ensure_student(request)
    if redirect_response:
        return redirect_response

    assignment = get_object_or_404(
        Assignment.objects.select_related("classroom"),
        id=assignment_id,
        classroom__students=request.user,
        assignment_type=Assignment.ASSIGNMENT_TYPE_QUIZ
    )
    if assignment.due_date < timezone.now():
        messages.error(request, "This quiz deadline has passed.")
        return redirect("view_assignments")
    questions = assignment.quiz_questions.all()
    if not questions.exists():
        # Backfill parser for old AI quizzes that were saved only as description text.
        parsed = _parse_quiz_questions_from_description(assignment.description)
        for item in parsed:
            QuizQuestion.objects.create(
                assignment=assignment,
                question=item["question"],
                option_a=item["A"],
                option_b=item["B"],
                option_c=item["C"],
                option_d=item["D"],
                # Old descriptions often miss answer keys; keep a placeholder.
                correct_answer="A",
            )
        questions = assignment.quiz_questions.all()

    existing_answers = {
        answer.question_id: answer.selected_option
        for answer in QuizAnswer.objects.filter(
            question__assignment=assignment,
            student=request.user,
        )
    }
    has_existing_result = QuizResult.objects.filter(
        assignment=assignment,
        student=request.user,
    ).exists()
    has_existing_attempt = bool(existing_answers) or has_existing_result
    can_submit = assignment.allows_multiple_attempts or not has_existing_attempt

    if request.method == "POST":
        if not questions.exists():
            messages.error(request, "No quiz questions configured yet.")
            return redirect("view_assignments")
        if not can_submit:
            messages.error(request, "This quiz allows only one attempt.")
            return redirect("take_quiz_assignment", assignment_id=assignment.id)

        selected_answers = {}
        for question in questions:
            selected_option = request.POST.get(f"question_{question.id}", "").strip().upper()
            if selected_option not in {"A", "B", "C", "D"}:
                messages.error(request, "Please answer all quiz questions before submitting.")
                return redirect("take_quiz_assignment", assignment_id=assignment.id)
            selected_answers[question.id] = selected_option

        for question in questions:
            QuizAnswer.objects.update_or_create(
                question=question,
                student=request.user,
                defaults={"selected_option": selected_answers[question.id]}
            )

        evaluate_quiz_for_student(assignment, request.user)

        if has_existing_attempt:
            messages.success(request, "Quiz re-submitted successfully.")
        else:
            messages.success(request, "Quiz submitted successfully.")
        return redirect("view_assignments")

    question_rows = [
        {
            "question": question,
            "selected_option": existing_answers.get(question.id, ""),
        }
        for question in questions
    ]
    show_description = bool(assignment.description)
    if show_description and questions.exists():
        show_description = not bool(
            _parse_quiz_questions_from_description(assignment.description)
        )

    return render(request, "student/assignment/take_quiz.html", {
        "assignment": assignment,
        "questions": questions,
        "question_rows": question_rows,
        "can_submit": can_submit,
        "show_description": show_description,
    })


@login_required
def submit_code_assignment(request, assignment_id):
    redirect_response = _ensure_student(request)
    if redirect_response:
        return redirect_response

    assignment = get_object_or_404(
        Assignment.objects.select_related("classroom"),
        id=assignment_id,
        classroom__students=request.user,
        assignment_type=Assignment.ASSIGNMENT_TYPE_CODE
    )
    if assignment.due_date < timezone.now():
        messages.error(request, "This coding assignment deadline has passed.")
        return redirect("view_assignments")
    existing_submission = CodeSubmission.objects.filter(
        assignment=assignment,
        student=request.user
    ).first()
    can_submit = assignment.allows_multiple_attempts or not existing_submission

    if request.method == "POST":
        if not can_submit:
            messages.error(request, "This coding assignment allows only one attempt.")
            return redirect("submit_code_assignment", assignment_id=assignment.id)

        code = request.POST.get("code", "").rstrip()
        language = request.POST.get("language", "python").strip() or "python"

        if not code:
            messages.error(request, "Code cannot be empty.")
            return redirect("submit_code_assignment", assignment_id=assignment.id)

        if existing_submission:
            existing_submission.code = code
            existing_submission.language = language
            existing_submission.save(update_fields=["code", "language"])
            sync_code_submission_record(existing_submission, evaluation_type="manual")
            success_message = "Code re-submitted successfully."
        else:
            code_submission = CodeSubmission.objects.create(
                assignment=assignment,
                student=request.user,
                code=code,
                language=language,
            )
            sync_code_submission_record(code_submission, evaluation_type="manual")
            success_message = "Code submitted successfully."
        messages.success(request, success_message)
        return redirect("view_assignments")

    return render(request, "student/assignment/submit_code.html", {
        "assignment": assignment,
        "existing_submission": existing_submission,
        "can_submit": can_submit,
    })


@login_required
def student_profile(request):

    profile, _ = StudentProfile.objects.get_or_create(user=request.user)

    return render(request, "student/profile.html", {"profile": profile})


@login_required
def edit_student_profile(request):

    profile, _ = StudentProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":

        request.user.username = request.POST.get("username", request.user.username)
        request.user.email = request.POST.get("email", request.user.email)
        request.user.save()

        profile.phone_number = request.POST.get("phone_number", "")
        profile.address = request.POST.get("address", "")
        profile.course = request.POST.get("course", "")
        profile.batch = request.POST.get("batch", "")
        profile.student_id = request.POST.get("student_id", "")

        dob_value = request.POST.get("date_of_birth")
        profile.date_of_birth = dob_value or None

        profile.gender = request.POST.get("gender", "")
        profile.parent_name = request.POST.get("parent_name", "")
        profile.parent_phone = request.POST.get("parent_phone", "")
        profile.parent_email = request.POST.get("parent_email", "")
        profile.guardian_relation = request.POST.get("guardian_relation", "")

        if request.FILES.get("profile_picture"):
            profile.profile_picture = request.FILES.get("profile_picture")

        profile.save()

        return redirect("student_profile")

    return render(request, "student/update.html", {"profile": profile})
