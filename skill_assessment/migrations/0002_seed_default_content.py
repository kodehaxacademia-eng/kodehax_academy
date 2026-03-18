from django.db import migrations


DEFAULT_QUESTIONS = [
    {
        "question_text": "Which data structure stores elements in contiguous memory and allows index-based access?",
        "topic": "arrays",
        "difficulty": "beginner",
        "correct_answer": "A",
        "options": [
            {"value": "A", "label": "Array"},
            {"value": "B", "label": "Queue"},
            {"value": "C", "label": "Stack"},
            {"value": "D", "label": "Tree"},
        ],
    },
    {
        "question_text": "What is the time complexity of binary search on a sorted array?",
        "topic": "time complexity",
        "difficulty": "basic",
        "correct_answer": "B",
        "options": [
            {"value": "A", "label": "O(n)"},
            {"value": "B", "label": "O(log n)"},
            {"value": "C", "label": "O(n log n)"},
            {"value": "D", "label": "O(1)"},
        ],
    },
    {
        "question_text": "Which loop is best when you know exactly how many times code should repeat?",
        "topic": "loops",
        "difficulty": "beginner",
        "correct_answer": "C",
        "options": [
            {"value": "A", "label": "while loop"},
            {"value": "B", "label": "do-while loop"},
            {"value": "C", "label": "for loop"},
            {"value": "D", "label": "infinite loop"},
        ],
    },
    {
        "question_text": "What is recursion?",
        "topic": "recursion",
        "difficulty": "beginner",
        "correct_answer": "D",
        "options": [
            {"value": "A", "label": "A loop that always runs forever"},
            {"value": "B", "label": "Sorting items alphabetically"},
            {"value": "C", "label": "A variable calling another variable"},
            {"value": "D", "label": "A function calling itself with a smaller subproblem"},
        ],
    },
    {
        "question_text": "Which sorting algorithm has average-case time complexity O(n log n)?",
        "topic": "sorting",
        "difficulty": "basic",
        "correct_answer": "A",
        "options": [
            {"value": "A", "label": "Merge sort"},
            {"value": "B", "label": "Bubble sort"},
            {"value": "C", "label": "Selection sort"},
            {"value": "D", "label": "Linear search"},
        ],
    },
    {
        "question_text": "What does `s[::-1]` do in Python?",
        "topic": "strings",
        "difficulty": "beginner",
        "correct_answer": "B",
        "options": [
            {"value": "A", "label": "Returns every second character"},
            {"value": "B", "label": "Reverses the string"},
            {"value": "C", "label": "Sorts the string"},
            {"value": "D", "label": "Removes duplicates"},
        ],
    },
    {
        "question_text": "If an algorithm inspects every element of a list once, what is its time complexity?",
        "topic": "time complexity",
        "difficulty": "beginner",
        "correct_answer": "A",
        "options": [
            {"value": "A", "label": "O(n)"},
            {"value": "B", "label": "O(log n)"},
            {"value": "C", "label": "O(n^2)"},
            {"value": "D", "label": "O(1)"},
        ],
    },
    {
        "question_text": "Which statement about arrays is true?",
        "topic": "arrays",
        "difficulty": "basic",
        "correct_answer": "C",
        "options": [
            {"value": "A", "label": "Arrays cannot store numbers"},
            {"value": "B", "label": "Arrays always remove duplicate values"},
            {"value": "C", "label": "Arrays can be traversed using indexes"},
            {"value": "D", "label": "Arrays are only available in Python"},
        ],
    },
    {
        "question_text": "Why is a base case important in recursion?",
        "topic": "recursion",
        "difficulty": "basic",
        "correct_answer": "B",
        "options": [
            {"value": "A", "label": "It makes the function run faster than O(1)"},
            {"value": "B", "label": "It stops recursive calls from continuing forever"},
            {"value": "C", "label": "It sorts the recursion output"},
            {"value": "D", "label": "It converts recursion into iteration"},
        ],
    },
    {
        "question_text": "Which built-in Python method joins a list of strings into a single string?",
        "topic": "strings",
        "difficulty": "beginner",
        "correct_answer": "D",
        "options": [
            {"value": "A", "label": "split()"},
            {"value": "B", "label": "append()"},
            {"value": "C", "label": "replace()"},
            {"value": "D", "label": "join()"},
        ],
    },
]


DEFAULT_PROBLEMS = [
    {
        "title": "Reverse a String",
        "slug": "reverse-a-string",
        "description": "Write a Python function `reverse_string(text)` that returns the reversed version of the input string.",
        "function_name": "reverse_string",
        "difficulty": "beginner",
        "starter_code": "def reverse_string(text):\n    # Return the reversed string.\n    return text[::-1]\n",
        "test_cases": [
            {"input": ["hello"], "expected": "olleh"},
            {"input": ["Kodehax"], "expected": "xahedoK"},
            {"input": [""], "expected": ""},
        ],
    },
    {
        "title": "Find Maximum in a List",
        "slug": "find-maximum-in-a-list",
        "description": "Write a Python function `max_in_list(numbers)` that returns the largest number from the given list.",
        "function_name": "max_in_list",
        "difficulty": "beginner",
        "starter_code": "def max_in_list(numbers):\n    # Return the largest value in the list.\n    return max(numbers)\n",
        "test_cases": [
            {"input": [[3, 8, 2, 9, 4]], "expected": 9},
            {"input": [[-5, -2, -8]], "expected": -2},
            {"input": [[7]], "expected": 7},
        ],
    },
]


def seed_default_content(apps, schema_editor):
    AssessmentQuestion = apps.get_model("skill_assessment", "AssessmentQuestion")
    CodingProblem = apps.get_model("skill_assessment", "CodingProblem")

    if not AssessmentQuestion.objects.exists():
        for index, item in enumerate(DEFAULT_QUESTIONS, start=1):
            AssessmentQuestion.objects.create(order=index, **item)

    if not CodingProblem.objects.exists():
        for index, item in enumerate(DEFAULT_PROBLEMS, start=1):
            CodingProblem.objects.create(order=index, **item)


def remove_default_content(apps, schema_editor):
    AssessmentQuestion = apps.get_model("skill_assessment", "AssessmentQuestion")
    CodingProblem = apps.get_model("skill_assessment", "CodingProblem")
    AssessmentQuestion.objects.filter(question_text__in=[item["question_text"] for item in DEFAULT_QUESTIONS]).delete()
    CodingProblem.objects.filter(slug__in=[item["slug"] for item in DEFAULT_PROBLEMS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("skill_assessment", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_default_content, remove_default_content),
    ]
