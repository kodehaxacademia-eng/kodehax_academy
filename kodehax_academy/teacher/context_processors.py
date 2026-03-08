from .models import TeacherProfile


def teacher_profile_nav(request):
    if not request.user.is_authenticated:
        return {}

    if getattr(request.user, "role", None) != "teacher":
        return {}

    profile = (
        TeacherProfile.objects.filter(user=request.user)
        .only("profile_picture")
        .first()
    )
    return {"nav_teacher_profile": profile}
