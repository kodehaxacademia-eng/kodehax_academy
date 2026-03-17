import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kodehax_academy.settings')
django.setup()

from teacher.models import Assignment, QuizResult
from teacher.services.evaluation import evaluate_quiz_for_student
from django.contrib.auth import get_user_model

User = get_user_model()
student = User.objects.get(username="Mubashir114")
assignment = Assignment.objects.get(id=5) # Python Quizz

print("Re-evaluating quiz...")
result = evaluate_quiz_for_student(assignment, student)
print(f"New score: {result.score} / {assignment.max_score}")
