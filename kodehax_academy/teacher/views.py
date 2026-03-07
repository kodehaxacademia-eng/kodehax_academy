from django.shortcuts import render, redirect
from .forms import ClassRoomForm
from django.contrib.auth.decorators import login_required
from .models import ClassRoom, Assignment, Submission
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Avg
from django.db.models import Count
from datetime import timedelta
from .services.ai_tools import generate_quiz, generate_notes, strip_quiz_answers

@login_required
def teacher_dashboard(request):

    classes = ClassRoom.objects.filter(teacher=request.user)

    context = {
        "classes": classes
    }
    return render(request, "teacher/dashboard.html", context)
@login_required
def create_class(request):

    # ensure only teachers create classes
    if request.user.role != "teacher":
        return redirect("student_dashboard")

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

    classroom = get_object_or_404(
        ClassRoom,
        id=id,
        teacher=request.user
    )

    students = classroom.students.all()

    assignments = classroom.assignments.all()

    context = {
        "classroom": classroom,
        "students": students,
        "assignments": assignments
    }

    return render(request, "teacher/class_detail.html", context)

@login_required
def assignment_list(request, class_id):

    classroom = get_object_or_404(
        ClassRoom,
        id=class_id,
        teacher=request.user
    )

    assignments = classroom.assignments.all()

    return render(request, "teacher/assignment_list.html", {
        "classroom": classroom,
        "assignments": assignments
    })

@login_required
def create_assignment(request, class_id):

    classroom = get_object_or_404(
        ClassRoom,
        id=class_id,
        teacher=request.user
    )

    if request.method == "POST":

        title = request.POST.get("title")
        description = request.POST.get("description")
        due_date = request.POST.get("due_date")

        if due_date:

            due_date_obj = timezone.make_aware(
                timezone.datetime.fromisoformat(due_date)
            )

            if due_date_obj <= timezone.now():

                return render(request, "teacher/create_assignment.html", {
                    "classroom": classroom,
                    "error": "Due date must be in the future."
                })

        Assignment.objects.create(
            classroom=classroom,
            title=title,
            description=description,
            due_date=due_date_obj
        )
    return
        
@login_required
def assignment_detail(request, id):

    assignment = get_object_or_404(
        Assignment,
        id=id,
        classroom__teacher=request.user
    )

    submissions = assignment.submissions.all()

    return render(request, "teacher/assignment_detail.html", {
        "assignment": assignment,
        "submissions": submissions
    })

@login_required
def assignments_page(request, class_id):

    classroom = get_object_or_404(
        ClassRoom,
        id=class_id,
        teacher=request.user
    )

    # CREATE ASSIGNMENT
    if request.method == "POST":

        title = request.POST.get("title")
        description = request.POST.get("description")
        due_date = request.POST.get("due_date")

        if due_date:

            due_date_obj = timezone.make_aware(
                timezone.datetime.fromisoformat(due_date)
            )

            if due_date_obj <= timezone.now():

                return render(request,
                    "teacher/assignments.html",
                    {
                        "classroom": classroom,
                        "assignments": classroom.assignments.all(),
                        "error": "Due date must be in the future"
                    }
                )

            Assignment.objects.create(
                classroom=classroom,
                title=title,
                description=description,
                due_date=due_date_obj
            )

            return redirect("assignments_page", class_id=classroom.id)

    assignments = classroom.assignments.all()

    return render(request, "teacher/assignments.html", {
        "classroom": classroom,
        "assignments": assignments
    })

@login_required
def performance_list(request, class_id):

    classroom = get_object_or_404(
        ClassRoom,
        id=class_id,
        teacher=request.user
    )

    students = classroom.students.all()

    student_data = []

    for student in students:

        submissions = Submission.objects.filter(
            assignment__classroom=classroom,
            student=student
        )

        avg_score = submissions.aggregate(
            Avg('score')
        )['score__avg']

        student_data.append({
            "student": student,
            "submissions": submissions.count(),
            "avg_score": round(avg_score,2) if avg_score else "N/A"
        })

    return render(request, "teacher/performance_list.html", {
        "classroom": classroom,
        "student_data": student_data
    })


@login_required
def student_performance(request, class_id, student_id):

    classroom = get_object_or_404(
        ClassRoom,
        id=class_id,
        teacher=request.user
    )

    student = classroom.students.get(id=student_id)

    submissions = Submission.objects.filter(
        assignment__classroom=classroom,
        student=student
    )

    scores = []
    assignments = []

    for s in submissions:
        if s.score:
            scores.append(s.score)
            assignments.append(s.assignment.title)

    avg_score = sum(scores) / len(scores) if scores else 0

    context = {
        "classroom": classroom,
        "student": student,
        "submissions": submissions,
        "scores": scores,
        "assignments": assignments,
        "avg_score": round(avg_score,2)
    }

    return render(request, "teacher/student_performance.html", context)
@login_required
def teacher_profile(request):

    teacher = request.user

    classes = ClassRoom.objects.filter(teacher=teacher)

    assignments = Assignment.objects.filter(classroom__teacher=teacher)

    submissions = Submission.objects.filter(
        assignment__classroom__teacher=teacher
    )

    stats = {
        "class_count": classes.count(),
        "assignment_count": assignments.count(),
        "student_count": sum([c.students.count() for c in classes]),
        "submission_count": submissions.count(),
    }

    context = {
        "teacher": teacher,
        "classes": classes,
        "stats": stats
    }

    return render(request, "teacher/profile.html", context)

@login_required
def ai_tools(request):

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

                    Assignment.objects.create(
                        classroom=classroom,
                        title=title,
                        description=clean_questions,
                        due_date=due_date_obj
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
