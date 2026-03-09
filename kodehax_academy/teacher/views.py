from django.shortcuts import render, redirect
from django.urls import reverse
from .forms import ClassRoomForm, TeacherProfileForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import (
    Assignment,
    ClassRoom,
    CodeSubmission,
    QuizAnswer,
    QuizQuestion,
    Submission,
    TeacherProfile,
)
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count
from datetime import timedelta
import re
from .services.ai_tools import generate_quiz, generate_notes, strip_quiz_answers
from .services.evaluation import (
    evaluate_quiz_for_assignment,
    get_classroom_student_performance,
    get_student_score_records,
    grade_code_submission_ai,
    grade_code_submission_manual,
    grade_file_submission_ai,
    grade_file_submission_manual,
)


def _get_teacher_classroom_or_redirect(request, class_id):
    if request.user.role != "teacher":
        messages.error(
            request,
            "Teacher portal access denied for current session. Use a separate browser profile/incognito for parallel logins."
        )
        return None, redirect("home")

    classroom = ClassRoom.objects.filter(
        id=class_id,
        teacher=request.user
    ).first()
    if not classroom:
        messages.error(request, "Classroom not found or you do not have access.")
        return None, redirect("teacher_dashboard")
    return classroom, None

@login_required
def teacher_dashboard(request):
    if request.user.role != "teacher":
        messages.error(
            request,
            "Teacher portal access denied for current session."
        )
        return redirect("home")

    classes = ClassRoom.objects.filter(teacher=request.user)
    assignment_count = Assignment.objects.filter(classroom__teacher=request.user).count()
    student_count = classes.aggregate(total=Count("students", distinct=True))["total"] or 0

    context = {
        "classes": classes,
        "assignment_count": assignment_count,
        "student_count": student_count,
    }
    return render(request, "teacher/dashboard.html", context)
@login_required
def create_class(request):

    # ensure only teachers create classes
    if request.user.role != "teacher":
        messages.error(request, "Only teachers can create classrooms.")
        return redirect("home")

    if request.method == "POST":

        form = ClassRoomForm(request.POST)

        if form.is_valid():

            classroom = form.save(commit=False)

            classroom.teacher = request.user

            classroom.save()

            return redirect("teacher_dashboard")

    else:
        form = ClassRoomForm()

    return render(request, "teacher/create_class.html", {
        "form": form
    })

@login_required
def class_detail(request, id):
    classroom, redirect_response = _get_teacher_classroom_or_redirect(request, id)
    if redirect_response:
        return redirect_response

    students = classroom.students.all()

    assignments = classroom.assignments.all()
    assignment_rows = []
    for assignment in assignments:
        if assignment.assignment_type == Assignment.ASSIGNMENT_TYPE_FILE:
            submission_count = assignment.submissions.count()
        elif assignment.assignment_type == Assignment.ASSIGNMENT_TYPE_CODE:
            submission_count = assignment.code_submissions.count()
        else:
            submission_count = QuizAnswer.objects.filter(
                question__assignment=assignment
            ).values("student_id").distinct().count()
        assignment_rows.append({
            "assignment": assignment,
            "submission_count": submission_count,
        })

    context = {
        "classroom": classroom,
        "students": students,
        "assignment_rows": assignment_rows
    }

    return render(request, "teacher/class_detail.html", context)

@login_required
def assignment_list(request, class_id):
    classroom, redirect_response = _get_teacher_classroom_or_redirect(request, class_id)
    if redirect_response:
        return redirect_response

    assignments = classroom.assignments.all().order_by("-created_at")
    assignment_rows = []
    for assignment in assignments:
        if assignment.assignment_type == Assignment.ASSIGNMENT_TYPE_FILE:
            submission_count = assignment.submissions.count()
        elif assignment.assignment_type == Assignment.ASSIGNMENT_TYPE_CODE:
            submission_count = assignment.code_submissions.count()
        else:
            submission_count = QuizAnswer.objects.filter(
                question__assignment=assignment
            ).values("student_id").distinct().count()
        assignment_rows.append({
            "assignment": assignment,
            "submission_count": submission_count,
        })

    return render(request, "teacher/assignment_list.html", {
        "classroom": classroom,
        "assignment_rows": assignment_rows
    })


def _parse_due_date_or_error(due_date_raw):
    if not due_date_raw:
        return None, "Due date is required."
    try:
        due_date_obj = timezone.make_aware(
            timezone.datetime.fromisoformat(due_date_raw)
        )
    except ValueError:
        return None, "Invalid due date format."
    if due_date_obj <= timezone.now():
        return None, "Due date must be in the future."
    return due_date_obj, None


def _parse_quiz_questions_from_text(raw_text):
    if not raw_text:
        return []

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    questions = []
    current = None
    option_pattern = re.compile(r"^([ABCD])[)\.:]\s*(.+)$", re.IGNORECASE)
    question_pattern = re.compile(r"^Q\s*\d+\s*[)\.:]?\s*(.+)$", re.IGNORECASE)
    answer_pattern = re.compile(r"^(answer|correct answer)\s*[:\-]\s*([ABCD])\b", re.IGNORECASE)

    def finalize_current():
        if not current:
            return
        if all(current.get(opt) for opt in ("A", "B", "C", "D")):
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
                "correct_answer": "A",
            }
            continue

        if not current:
            continue

        o_match = option_pattern.match(line)
        if o_match:
            current[o_match.group(1).upper()] = o_match.group(2).strip()
            continue

        a_match = answer_pattern.match(line)
        if a_match:
            current["correct_answer"] = a_match.group(2).upper()
            continue

        if not any(current.get(opt) for opt in ("A", "B", "C", "D")):
            current["question"] = f"{current['question']} {line}".strip()

    finalize_current()
    return questions


@login_required
def assignment_type_selector(request, class_id):
    classroom, redirect_response = _get_teacher_classroom_or_redirect(request, class_id)
    if redirect_response:
        return redirect_response
    return render(request, "teacher/assignment_type_selector.html", {
        "classroom": classroom
    })

@login_required
def create_assignment(request, class_id):
    # Backward-compatible route: keep this path working for file assignments.
    return create_file_assignment(request, class_id)


@login_required
def create_file_assignment(request, class_id):
    classroom, redirect_response = _get_teacher_classroom_or_redirect(request, class_id)
    if redirect_response:
        return redirect_response

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        due_date_obj, error = _parse_due_date_or_error(request.POST.get("due_date", "").strip())

        if not title or not description:
            error = "Title and description are required."

        if error:
            return render(request, "teacher/create_assignment.html", {
                "classroom": classroom,
                "assignment_type": Assignment.ASSIGNMENT_TYPE_FILE,
                "error": error,
            })

        Assignment.objects.create(
            classroom=classroom,
            title=title,
            description=description,
            due_date=due_date_obj,
            assignment_type=Assignment.ASSIGNMENT_TYPE_FILE,
        )
        return redirect("assignment_list", class_id=classroom.id)

    return render(request, "teacher/create_assignment.html", {
        "classroom": classroom,
        "assignment_type": Assignment.ASSIGNMENT_TYPE_FILE,
    })


@login_required
def create_quiz_assignment(request, class_id):
    classroom, redirect_response = _get_teacher_classroom_or_redirect(request, class_id)
    if redirect_response:
        return redirect_response

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        due_date_obj, error = _parse_due_date_or_error(request.POST.get("due_date", "").strip())

        questions = request.POST.getlist("question")
        option_as = request.POST.getlist("option_a")
        option_bs = request.POST.getlist("option_b")
        option_cs = request.POST.getlist("option_c")
        option_ds = request.POST.getlist("option_d")
        correct_answers = request.POST.getlist("correct_answer")

        if not title:
            error = "Title is required."
        if not questions:
            error = "Add at least one quiz question."
        if len({len(questions), len(option_as), len(option_bs), len(option_cs), len(option_ds), len(correct_answers)}) != 1:
            error = "Quiz question data is incomplete."
        for answer in correct_answers:
            if (answer or "").strip().upper() not in {"A", "B", "C", "D"}:
                error = "Correct answer must be one of A, B, C, D."
                break

        if error:
            return render(request, "teacher/create_quiz_assignment.html", {
                "classroom": classroom,
                "error": error,
            })

        assignment = Assignment.objects.create(
            classroom=classroom,
            title=title,
            description=description,
            due_date=due_date_obj,
            assignment_type=Assignment.ASSIGNMENT_TYPE_QUIZ,
        )

        for idx in range(len(questions)):
            if not questions[idx].strip():
                continue
            QuizQuestion.objects.create(
                assignment=assignment,
                question=questions[idx].strip(),
                option_a=option_as[idx].strip(),
                option_b=option_bs[idx].strip(),
                option_c=option_cs[idx].strip(),
                option_d=option_ds[idx].strip(),
                correct_answer=(correct_answers[idx] or "").strip().upper(),
            )
        return redirect("assignment_detail", id=assignment.id)

    return render(request, "teacher/create_quiz_assignment.html", {
        "classroom": classroom
    })


@login_required
def create_code_assignment(request, class_id):
    classroom, redirect_response = _get_teacher_classroom_or_redirect(request, class_id)
    if redirect_response:
        return redirect_response

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        due_date_obj, error = _parse_due_date_or_error(request.POST.get("due_date", "").strip())

        if not title or not description:
            error = "Title and coding prompt are required."

        if error:
            return render(request, "teacher/create_code_assignment.html", {
                "classroom": classroom,
                "error": error,
            })

        assignment = Assignment.objects.create(
            classroom=classroom,
            title=title,
            description=description,
            due_date=due_date_obj,
            assignment_type=Assignment.ASSIGNMENT_TYPE_CODE,
        )
        return redirect("assignment_detail", id=assignment.id)

    return render(request, "teacher/create_code_assignment.html", {
        "classroom": classroom
    })
        
@login_required
def assignment_detail(request, id):
    if request.user.role != "teacher":
        messages.error(request, "Only teachers can view assignment details.")
        return redirect("home")

    assignment = Assignment.objects.filter(
        id=id,
        classroom__teacher=request.user
    ).first()
    if not assignment:
        messages.error(request, "Assignment not found or you do not have access.")
        return redirect("teacher_dashboard")

    file_submissions = assignment.submissions.select_related("student").all()
    code_submissions = assignment.code_submissions.select_related("student").all()
    quiz_questions = assignment.quiz_questions.all()
    quiz_results = assignment.quiz_results.select_related("student").order_by("-score")

    quiz_attempt_count = QuizAnswer.objects.filter(
        question__assignment=assignment
    ).values("student_id").distinct().count()

    return render(request, "teacher/assignment_detail.html", {
        "assignment": assignment,
        "file_submissions": file_submissions,
        "code_submissions": code_submissions,
        "quiz_questions": quiz_questions,
        "quiz_results": quiz_results,
        "quiz_attempt_count": quiz_attempt_count,
    })


@login_required
def grade_file_submission(request, submission_id):
    submission = Submission.objects.select_related(
        "assignment",
        "assignment__classroom",
        "student",
    ).filter(
        id=submission_id,
        assignment__classroom__teacher=request.user,
    ).first()
    if not submission:
        messages.error(request, "Submission not found.")
        return redirect("teacher_dashboard")

    if request.method == "POST":
        action = request.POST.get("action", "manual")
        if action == "ai":
            grade_file_submission_ai(submission)
            messages.success(request, "AI grading completed for file submission.")
        else:
            score = request.POST.get("score", "0")
            feedback = request.POST.get("feedback", "")
            try:
                grade_file_submission_manual(submission, score, feedback)
                messages.success(request, "Manual grading saved.")
            except ValueError:
                messages.error(request, "Invalid score value.")
        return redirect("assignment_detail", id=submission.assignment.id)

    return render(request, "teacher/grade_file_submission.html", {
        "submission": submission,
        "assignment": submission.assignment,
    })


@login_required
def grade_code_submission(request, submission_id):
    submission = CodeSubmission.objects.select_related(
        "assignment",
        "assignment__classroom",
        "student",
    ).filter(
        id=submission_id,
        assignment__classroom__teacher=request.user,
    ).first()
    if not submission:
        messages.error(request, "Code submission not found.")
        return redirect("teacher_dashboard")

    if request.method == "POST":
        action = request.POST.get("action", "manual")
        if action == "ai":
            grade_code_submission_ai(submission)
            messages.success(request, "AI grading completed for code submission.")
        else:
            score = request.POST.get("score", "0")
            feedback = request.POST.get("feedback", "")
            try:
                grade_code_submission_manual(submission, score, feedback)
                messages.success(request, "Manual grading saved.")
            except ValueError:
                messages.error(request, "Invalid score value.")
        return redirect("assignment_detail", id=submission.assignment.id)

    return render(request, "teacher/grade_code_submission.html", {
        "submission": submission,
        "assignment": submission.assignment,
    })


@login_required
def auto_grade_quiz(request, assignment_id):
    assignment = Assignment.objects.filter(
        id=assignment_id,
        classroom__teacher=request.user,
        assignment_type=Assignment.ASSIGNMENT_TYPE_QUIZ,
    ).first()
    if not assignment:
        messages.error(request, "Quiz assignment not found.")
        return redirect("teacher_dashboard")

    if request.method == "POST":
        graded_count = evaluate_quiz_for_assignment(assignment)
        messages.success(request, f"Auto-graded quiz for {graded_count} students.")
    return redirect("assignment_detail", id=assignment.id)

@login_required
def assignments_page(request, class_id):
    # Backward-compatible route for old links:
    # GET -> show assignment list, POST -> create file assignment.
    if request.method == "POST":
        return create_file_assignment(request, class_id)
    return assignment_list(request, class_id)

@login_required
def performance_list(request, class_id):
    classroom, redirect_response = _get_teacher_classroom_or_redirect(request, class_id)
    if redirect_response:
        return redirect_response
    student_data = get_classroom_student_performance(classroom)

    return render(request, "teacher/performance_list.html", {
        "classroom": classroom,
        "student_data": student_data
    })


@login_required
def student_performance(request, class_id, student_id):
    classroom, redirect_response = _get_teacher_classroom_or_redirect(request, class_id)
    if redirect_response:
        return redirect_response

    student = classroom.students.filter(id=student_id).first()
    if not student:
        messages.error(request, "Student not found in this classroom.")
        return redirect("performance_list", class_id=classroom.id)

    score_records, avg_score = get_student_score_records(classroom, student)
    scores = [record["score"] for record in score_records if record["score"] is not None]
    assignments = [record["assignment"].title for record in score_records if record["score"] is not None]

    context = {
        "classroom": classroom,
        "student": student,
        "score_records": score_records,
        "scores": scores,
        "assignments": assignments,
        "avg_score": round(avg_score,2)
    }

    return render(request, "teacher/student_performance.html", context)
@login_required
def teacher_profile(request):
    if request.user.role != "teacher":
        messages.error(request, "Only teachers can access teacher profile.")
        return redirect("home")

    teacher = request.user
    profile, _ = TeacherProfile.objects.get_or_create(user=teacher)

    classes = ClassRoom.objects.filter(teacher=teacher)
    assignments = Assignment.objects.filter(classroom__teacher=teacher)
    submissions = Submission.objects.filter(
        assignment__classroom__teacher=teacher
    )

    stats = {
        "class_count": classes.count(),
        "assignment_count": assignments.count(),
        "student_count": classes.aggregate(total=Count("students", distinct=True))["total"] or 0,
        "submission_count": submissions.count(),
    }

    context = {
        "teacher": teacher,
        "classes": classes,
        "stats": stats,
        "profile": profile,
        "updated": request.GET.get("updated") == "1",
    }

    return render(request, "teacher/profile.html", context)


@login_required
def teacher_edit_profile(request):
    if request.user.role != "teacher":
        messages.error(request, "Only teachers can edit teacher profile.")
        return redirect("home")

    teacher = request.user
    profile, _ = TeacherProfile.objects.get_or_create(user=teacher)

    if request.method == "POST":
        profile_form = TeacherProfileForm(
            request.POST,
            request.FILES,
            instance=profile
        )
        if profile_form.is_valid():
            profile_form.save()
            return redirect(f"{reverse('teacher_profile')}?updated=1")
    else:
        profile_form = TeacherProfileForm(instance=profile)

    return render(request, "teacher/edit_profile.html", {
        "teacher": teacher,
        "profile": profile,
        "profile_form": profile_form,
    })

@login_required
def ai_tools(request):
    if request.user.role != "teacher":
        messages.error(request, "Only teachers can access AI tools.")
        return redirect("home")

    result = None
    tool_used = None
    topic = ""
    upload_success = None
    upload_error = None

    classes = ClassRoom.objects.filter(teacher=request.user)

    if request.method == "POST":

        action = request.POST.get("action", "generate")

        if action == "upload_quiz":

            class_id = request.POST.get("class_id")
            assignment_title = request.POST.get("assignment_title", "").strip()
            due_date = request.POST.get("due_date", "").strip()
            quiz_content = request.POST.get("quiz_content", "")

            if not class_id or not quiz_content.strip():
                upload_error = "Classroom and quiz content are required."
                result = quiz_content
                tool_used = "quiz"
            else:
                classroom = get_object_or_404(
                    ClassRoom,
                    id=class_id,
                    teacher=request.user
                )

                due_date_obj = None
                if due_date:
                    due_date_obj = timezone.make_aware(
                        timezone.datetime.fromisoformat(due_date)
                    )
                    if due_date_obj <= timezone.now():
                        upload_error = "Due date must be in the future."

                if not due_date_obj and not upload_error:
                    due_date_obj = timezone.now() + timedelta(days=7)

                if not upload_error:
                    clean_questions = strip_quiz_answers(quiz_content)
                    title = assignment_title or f"AI Quiz - {classroom.name}"

                    assignment = Assignment.objects.create(
                        classroom=classroom,
                        title=title,
                        description=clean_questions,
                        due_date=due_date_obj,
                        assignment_type=Assignment.ASSIGNMENT_TYPE_QUIZ,
                    )

                    parsed_questions = _parse_quiz_questions_from_text(quiz_content)
                    for q in parsed_questions:
                        QuizQuestion.objects.create(
                            assignment=assignment,
                            question=q["question"],
                            option_a=q["A"],
                            option_b=q["B"],
                            option_c=q["C"],
                            option_d=q["D"],
                            correct_answer=q["correct_answer"],
                        )
                    upload_success = f"Quiz uploaded to {classroom.name} as '{title}'."

                result = quiz_content
                tool_used = "quiz"

        else:
            topic = request.POST.get("topic", "").strip()
            tool_used = request.POST.get("tool")

            if tool_used == "quiz" and topic:
                result = generate_quiz(topic)
            elif tool_used == "notes" and topic:
                result = generate_notes(topic)

    return render(request, "teacher/ai_tools.html", {
        "result": result,
        "tool_used": tool_used,
        "topic": topic,
        "classes": classes,
        "upload_success": upload_success,
        "upload_error": upload_error,
    })
