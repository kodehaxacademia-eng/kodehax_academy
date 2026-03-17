import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kodehax_academy.settings')
django.setup()

from teacher.models import Assignment, QuizQuestion

# Get the assignment from the screenshot (Likely "Python Quizz")
assignments = Assignment.objects.filter(assignment_type='quiz').order_by('-id')[:2]

for a in assignments:
    print(f"Assignment {a.id}: {a.title}")
    questions = a.quiz_questions.all()
    for q in questions:
        print(f"  Q{q.id}: {q.question[:40]}...")
        print(f"    A: '{q.option_a}'")
        print(f"    B: '{q.option_b}'")
        print(f"    C: '{q.option_c}'")
        print(f"    D: '{q.option_d}'")
    print("-" * 40)
