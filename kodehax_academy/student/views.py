from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from .models import StudentProfile

@login_required
def student_dashboard(request):
    profile, _ = StudentProfile.objects.get_or_create(user=request.user)
    return render(request, "student/dashboard.html", {"profile": profile})


@login_required
def student_assignments(request):
    return render(request, "student/assignment/assignment.html")


@login_required
def student_view_assignment(request):
    return render(request, "student/assignment/view_assignment.html")


@login_required
def student_submit_assignment(request):
    return render(request, "student/assignment/submit_assignment.html")

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
