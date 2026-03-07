from django.shortcuts import render, redirect
from .forms import ClassRoomForm
from django.contrib.auth.decorators import login_required
from .models import ClassRoom, Assignment, Submission
from django.shortcuts import get_object_or_404
from django.utils import timezone



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