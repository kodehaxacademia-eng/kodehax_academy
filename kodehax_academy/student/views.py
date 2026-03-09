from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import StudentProfile
import json
import requests #type: ignore
import re
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from chat.views import RESPONSE_STYLE_INSTRUCTION, format_ai_reply
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
        }

        if assignment.assignment_type == Assignment.ASSIGNMENT_TYPE_FILE:
            row["submission"] = file_submission_map.get(assignment.id)
            row["action_label"] = "Submit / Re-submit"
            if row["submission"]:
                row["status_label"] = "Submitted"
                row["status_class"] = "emerald"
        elif assignment.assignment_type == Assignment.ASSIGNMENT_TYPE_CODE:
            row["submission"] = code_submission_map.get(assignment.id)
            row["action_label"] = "Write Code"
            if row["submission"]:
                row["status_label"] = "Submitted"
                row["status_class"] = "emerald"
        else:
            row["submission"] = quiz_result_map.get(assignment.id)
            row["action_label"] = "Take Quiz"
            if row["submission"] or assignment.id in quiz_attempted_ids:
                row["status_label"] = "Completed"
                row["status_class"] = "emerald"
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
    profile, _ = StudentProfile.objects.get_or_create(user=request.user)

    redirect_response = _ensure_student(request)
    if redirect_response:
        return redirect_response

    joined_classes = ClassRoom.objects.filter(
        students=request.user
    ).select_related("teacher").prefetch_related("assignments").order_by("-created_at")

    assignments = Assignment.objects.filter(
        classroom__students=request.user
    ).select_related("classroom")
    assignment_rows = _build_assignment_rows(assignments, request.user)
    submission_map = {row["assignment"].id: row for row in assignment_rows}

    return render(request, "student/dashboard.html", {
        "profile": profile,
        "joined_classes": joined_classes,
        "submission_map": submission_map,
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

    assignments = classroom.assignments.all().order_by("due_date")
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
        classroom__students=request.user
    ).select_related("classroom", "classroom__teacher").order_by("due_date")

    assignment_rows = _build_assignment_rows(assignments, request.user)

    return render(request, "student/assignment/view_assignment.html", {
        "assignment_rows": assignment_rows,
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

    if assignment.assignment_type == Assignment.ASSIGNMENT_TYPE_QUIZ:
        return redirect("take_quiz_assignment", assignment_id=assignment.id)
    if assignment.assignment_type == Assignment.ASSIGNMENT_TYPE_CODE:
        return redirect("submit_code_assignment", assignment_id=assignment.id)

    if request.method == "POST":
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            messages.error(request, "Please select a file to submit.")
            return redirect("submit_assignment", assignment_id=assignment.id)

        submission, created = Submission.objects.get_or_create(
            assignment=assignment,
            student=request.user,
            defaults={"file": uploaded_file}
        )

        if not created:
            submission.file = uploaded_file
            submission.save(update_fields=["file"])

        messages.success(request, "Assignment submitted successfully.")
        return redirect("view_assignments")

    existing_submission = Submission.objects.filter(
        assignment=assignment,
        student=request.user
    ).first()

    return render(request, "student/assignment/submit_assignment.html", {
        "assignment": assignment,
        "existing_submission": existing_submission,
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

    if request.method == "POST":
        if not questions.exists():
            messages.error(request, "No quiz questions configured yet.")
            return redirect("view_assignments")

        for question in questions:
            selected_option = request.POST.get(f"question_{question.id}", "").strip().upper()
            if selected_option not in {"A", "B", "C", "D"}:
                continue
            QuizAnswer.objects.update_or_create(
                question=question,
                student=request.user,
                defaults={"selected_option": selected_option}
            )

        evaluate_quiz_for_student(assignment, request.user)

        messages.success(request, "Quiz submitted successfully.")
        return redirect("view_assignments")

    return render(request, "student/assignment/take_quiz.html", {
        "assignment": assignment,
        "questions": questions,
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

    if request.method == "POST":
        code = request.POST.get("code", "").rstrip()
        language = request.POST.get("language", "python").strip() or "python"

        if not code:
            messages.error(request, "Code cannot be empty.")
            return redirect("submit_code_assignment", assignment_id=assignment.id)

        CodeSubmission.objects.update_or_create(
            assignment=assignment,
            student=request.user,
            defaults={
                "code": code,
                "language": language,
            }
        )
        messages.success(request, "Code submitted successfully.")
        return redirect("view_assignments")

    existing_submission = CodeSubmission.objects.filter(
        assignment=assignment,
        student=request.user
    ).first()

    return render(request, "student/assignment/submit_code.html", {
        "assignment": assignment,
        "existing_submission": existing_submission,
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
