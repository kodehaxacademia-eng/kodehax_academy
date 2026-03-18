import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kodehax_academy.settings')
django.setup()

from teacher.models import QuizAnswer, Assignment

with open('ans_debug.txt', 'w', encoding='utf-8') as f:
    answers = QuizAnswer.objects.all().order_by('-id')[:10]
    for ans in answers:
        f.write(f"Answer {ans.id} - Student: {ans.student.username} - QID: {ans.question.id} - Option: '{ans.selected_option}'\n")
