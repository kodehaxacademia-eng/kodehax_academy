from django import template
from django.urls import NoReverseMatch, reverse

register = template.Library()


TEACHER_LABELS = {
    "teacher_dashboard": ["Dashboard"],
    "create_class": ["Create Classroom"],
    "class_detail": ["Classroom"],
    "assignment_type_selector": ["Assignments", "Assignment Type"],
    "create_assignment": ["Assignments", "New Assignment"],
    "create_file_assignment": ["Assignments", "New File Assignment"],
    "create_quiz_assignment": ["Assignments", "New Quiz Assignment"],
    "create_code_assignment": ["Assignments", "New Coding Assignment"],
    "assignment_list": ["Assignments"],
    "assignments_page": ["Assignments"],
    "assignment_detail": ["Assignments", "Details"],
    "grade_file_submission": ["Assignments", "Grade Submission"],
    "grade_code_submission": ["Assignments", "Grade Submission"],
    "evaluate_code_submission": ["Assignments", "Code Evaluation"],
    "performance_list": ["Performance"],
    "student_performance": ["Performance", "Student Detail"],
    "teacher_profile": ["Profile"],
    "teacher_edit_profile": ["Profile", "Edit"],
    "ai_tools": ["AI Tools"],
}

STUDENT_LABELS = {
    "student_dashboard": ["Dashboard"],
    "student_performance_dashboard": ["Performance"],
    "join_classroom": ["Join Classroom"],
    "student_class_detail": ["Classes", "Class Detail"],
    "view_assignments": ["Assignments"],
    "submit_assignment": ["Assignments", "Submission"],
    "take_quiz_assignment": ["Assignments", "Quiz"],
    "submit_code_assignment": ["Assignments", "Code Submission"],
    "student_profile": ["Profile"],
    "edit_student_profile": ["Profile", "Edit"],
    "chat_page": ["Chatroom"],
    "ai_chat": ["Chatroom"],
    "skill_assessment_entry": ["Skill Assessment"],
    "skill_assessment_step": ["Skill Assessment", "Step"],
    "skill_assessment_complete": ["Skill Assessment", "Complete"],
    "skill_assessment_profile": ["Skill Profile"],
    "daily_challenges_today": ["Daily Challenge"],
    "daily_challenge_workspace": ["Daily Challenge", "Workspace"],
}


def _safe_reverse(url_name):
    try:
        return reverse(url_name)
    except NoReverseMatch:
        return None


def _build_items(root_label, root_url, labels):
    items = [{"label": root_label, "url": root_url, "current": len(labels) == 0}]
    for index, label in enumerate(labels):
        items.append(
            {
                "label": label,
                "url": None,
                "current": index == len(labels) - 1,
            }
        )
    return items


@register.inclusion_tag("shared/breadcrumbs.html", takes_context=True)
def module_breadcrumbs(context, area):
    request = context.get("request")
    if request is None or not getattr(request, "resolver_match", None):
        return {"breadcrumb_items": []}

    route_name = request.resolver_match.url_name or ""
    kwargs = request.resolver_match.kwargs or {}

    if area == "teacher":
        labels = TEACHER_LABELS.get(route_name, [])
        root_label = "Teacher Hub"
        root_url = _safe_reverse("teacher_dashboard")
    else:
        labels = STUDENT_LABELS.get(route_name, [])
        root_label = "Student Panel"
        root_url = _safe_reverse("student_dashboard")

    if route_name == "skill_assessment_step":
        step = kwargs.get("step")
        labels = ["Skill Assessment", f"Step {step}"] if step else labels

    breadcrumb_items = _build_items(root_label, root_url, labels)
    return {"breadcrumb_items": breadcrumb_items}

