from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from .models import StudentProfile
import json
import requests #type: ignore
import re
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

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
    return prompts.get(mode, prompts["tutor"])

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

    # try:
    #     response = requests.post(OLLAMA_URL, json={
    #         "model": MODEL,
    #         "messages": messages,
    #         "stream": False
    #     }, timeout=60)  # ← timeout added for slow responses
    #     data = response.json()
    #     reply = data["message"]["content"]
    #     return JsonResponse({"reply": reply})
    # except requests.exceptions.ConnectionError:
    #     return JsonResponse({"error": "Cannot connect to Ollama. Make sure it is running."}, status=500)
    # except requests.exceptions.Timeout:
    #     return JsonResponse({"error": "Ollama took too long to respond. Try again."}, status=500)
    # except Exception as e:
    #     return JsonResponse({"error": str(e)}, status=500)
    try:
        response = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "messages": messages,
            "stream": False
        }, timeout=60)
        data = response.json()
        reply = data["message"]["content"]
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
