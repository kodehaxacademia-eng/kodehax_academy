import ast
import json
import itertools
import random
import subprocess
import sys
from datetime import datetime, time, timedelta
from decimal import Decimal
from string import Formatter
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.utils import timezone

from skill_assessment.models import CodingProblem, StudentSkill
from skill_assessment.services import (
    build_starter_template,
    classify_skill_level,
    ensure_default_assessment_content,
    quantize_score,
)

from .models import (
    DailyChallenge,
    DailyChallengeQuestion,
    DailyChallengeSet,
    QuestionTemplate,
    StudentChallengeAttempt,
    StudentPoints,
)

User = get_user_model()
CHALLENGE_TZ = ZoneInfo(settings.DAILY_CHALLENGE_TIMEZONE)
PUBLISH_HOUR = settings.DAILY_CHALLENGE_PUBLISH_HOUR

HINT_COST = 5
LEVEL_SIZE = 3
PENALTY_WEIGHTS = {
    "failed": 1,
    "runtime": 1,
    "compilation": 1,
    "timeout": 2,
}
POINTS_BY_DIFFICULTY = {
    DailyChallenge.DIFFICULTY_EASY: 5,
    DailyChallenge.DIFFICULTY_MEDIUM: 10,
    DailyChallenge.DIFFICULTY_HARD: 20,
}
ATTEMPT_LIMITS = {
    DailyChallenge.DIFFICULTY_EASY: 3,
    DailyChallenge.DIFFICULTY_MEDIUM: 5,
    DailyChallenge.DIFFICULTY_HARD: 10,
}
POOL_MAP = {
    DailyChallenge.DIFFICULTY_EASY: [CodingProblem.DIFFICULTY_BEGINNER],
    DailyChallenge.DIFFICULTY_MEDIUM: [
        CodingProblem.DIFFICULTY_BASIC,
        CodingProblem.DIFFICULTY_INTERMEDIATE,
    ],
    DailyChallenge.DIFFICULTY_HARD: [CodingProblem.DIFFICULTY_ADVANCED],
}

RUNNER_SCRIPT = r"""
import ast
import builtins
import contextlib
import io
import json
import sys

payload = json.loads(sys.stdin.read())
code = payload["code"]
function_name = payload["function_name"]
test_cases = payload["test_cases"]

blocked_calls = {"eval", "exec", "open", "__import__", "compile", "input", "globals", "locals", "vars"}
blocked_modules = {"os", "sys", "subprocess", "socket", "pathlib", "shutil"}

tree = ast.parse(code, mode="exec")
for node in ast.walk(tree):
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name.split(".")[0] for alias in node.names]
        else:
            if node.module:
                names = [node.module.split(".")[0]]
        if any(name in blocked_modules for name in names):
            raise ValueError("Restricted import detected.")
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id in blocked_calls:
            raise ValueError("Restricted call detected.")
    if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
        raise ValueError("Dunder attribute access is not allowed.")

captured_stdout = io.StringIO()

def safe_print(*args, **kwargs):
    kwargs.setdefault("file", captured_stdout)
    return builtins.print(*args, **kwargs)

allowed_builtins = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "print": safe_print,
    "range": range,
    "reversed": reversed,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}

namespace = {"__builtins__": allowed_builtins}
with contextlib.redirect_stdout(captured_stdout):
    exec(compile(tree, "<daily-challenge>", "exec"), namespace, namespace)

target = namespace.get(function_name)
if not callable(target):
    raise ValueError(f"Function '{function_name}' was not defined.")

results = []
for case in test_cases:
    args = case.get("input", [])
    expected = case.get("expected")
    try:
        actual = target(*args)
        results.append(
            {
                "passed": actual == expected,
                "actual": actual,
                "expected": expected,
                "error_type": "",
                "error": "",
            }
        )
    except Exception as exc:
        results.append(
            {
                "passed": False,
                "actual": None,
                "expected": expected,
                "error_type": "runtime",
                "error": str(exc),
            }
        )

sys.stdout.write(json.dumps({"results": results}))
"""

DEFAULT_QUESTION_TEMPLATES = [
    {
        "title_template": "Filter numbers divisible by {k}",
        "description_template": "Write `filter_divisible(numbers)` and return all numbers divisible by {k} in their original order.",
        "difficulty": QuestionTemplate.DIFFICULTY_EASY,
        "topic": "arrays",
        "parameter_schema": {"k": ["2", "3", "4", "5", "6", "7"]},
        "function_name": "filter_divisible",
        "starter_code_template": "def filter_divisible(numbers):\n    result = []\n    for value in numbers:\n        # Keep numbers divisible by {k}.\n        pass\n    return result\n",
        "test_cases_template": [
            {"input": [[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]], "expected": "[value for value in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] if value % {k} == 0]"},
            {"input": ["[{k}, {k_plus}, {k_times_2}, {k_times_3}]"], "expected": "[value for value in [{k}, {k_plus}, {k_times_2}, {k_times_3}] if value % {k} == 0]"},
        ],
    },
    {
        "title_template": "Find numbers greater than {x}",
        "description_template": "Write `numbers_greater_than(numbers)` and return a list of values strictly greater than {x}.",
        "difficulty": QuestionTemplate.DIFFICULTY_EASY,
        "topic": "arrays",
        "parameter_schema": {"x": ["5", "8", "10", "12", "15"]},
        "function_name": "numbers_greater_than",
        "starter_code_template": "def numbers_greater_than(numbers):\n    return []\n",
        "test_cases_template": [
            {"input": [[1, 5, 7, 10, 13, 2]], "expected": "[value for value in [1, 5, 7, 10, 13, 2] if value > {x}]"},
            {"input": ["[{x_minus}, {x}, {x_plus}, {x_times_2}]"], "expected": "[value for value in [{x_minus}, {x}, {x_plus}, {x_times_2}] if value > {x}]"},
        ],
    },
    {
        "title_template": "Count occurrences of {target}",
        "description_template": "Write `count_target(values)` and return how many times {target} appears in the list.",
        "difficulty": QuestionTemplate.DIFFICULTY_EASY,
        "topic": "loops",
        "parameter_schema": {"target": ["2", "3", "4", "5", "7"]},
        "function_name": "count_target",
        "starter_code_template": "def count_target(values):\n    count = 0\n    for value in values:\n        pass\n    return count\n",
        "test_cases_template": [
            {"input": ["[{target}, 1, {target}, 4, {target}, 6]"], "expected": 3},
            {"input": [[1, 2, 3, 4, 5]], "expected": "[1, 2, 3, 4, 5].count({target})"},
        ],
    },
    {
        "title_template": "Count vowels in a string that are not '{blocked}'",
        "description_template": "Write `count_filtered_vowels(text)` and count vowels in `text` except the vowel `{blocked}`.",
        "difficulty": QuestionTemplate.DIFFICULTY_EASY,
        "topic": "strings",
        "parameter_schema": {"blocked": ["a", "e", "i", "o", "u"]},
        "function_name": "count_filtered_vowels",
        "starter_code_template": "def count_filtered_vowels(text):\n    vowels = 'aeiouAEIOU'\n    count = 0\n    for char in text:\n        pass\n    return count\n",
        "test_cases_template": [
            {"input": ["education"], "expected": "sum(1 for char in 'education' if char in 'aeiouAEIOU' and char.lower() != '{blocked}')"},
            {"input": ["Kodehax Academy"], "expected": "sum(1 for char in 'Kodehax Academy' if char in 'aeiouAEIOU' and char.lower() != '{blocked}')"},
        ],
    },
    {
        "title_template": "Rotate an array left by {k}",
        "description_template": "Write `rotate_left(values)` and return the array rotated left by {k} positions.",
        "difficulty": QuestionTemplate.DIFFICULTY_MEDIUM,
        "topic": "arrays",
        "parameter_schema": {"k": ["1", "2", "3", "4"]},
        "function_name": "rotate_left",
        "starter_code_template": "def rotate_left(values):\n    if not values:\n        return []\n    # Rotate left by {k} positions.\n    return values\n",
        "test_cases_template": [
            {"input": [[1, 2, 3, 4, 5]], "expected": "([1, 2, 3, 4, 5][{k} % len([1, 2, 3, 4, 5]):] + [1, 2, 3, 4, 5][: {k} % len([1, 2, 3, 4, 5])])"},
            {"input": [[10, 20, 30, 40]], "expected": "([10, 20, 30, 40][{k} % len([10, 20, 30, 40]):] + [10, 20, 30, 40][: {k} % len([10, 20, 30, 40])])"},
        ],
    },
    {
        "title_template": "Find the first index of {target} in a sorted list",
        "description_template": "Write `first_index(values)` and return the first index of {target}. Return -1 if it is missing.",
        "difficulty": QuestionTemplate.DIFFICULTY_MEDIUM,
        "topic": "searching",
        "parameter_schema": {"target": ["4", "6", "9", "12"]},
        "function_name": "first_index",
        "starter_code_template": "def first_index(values):\n    left, right = 0, len(values) - 1\n    answer = -1\n    while left <= right:\n        pass\n    return answer\n",
        "test_cases_template": [
            {"input": [[1, 2, 4, 4, 4, 7, 9]], "expected": "([1, 2, 4, 4, 4, 7, 9].index({target}) if {target} in [1, 2, 4, 4, 4, 7, 9] else -1)"},
            {"input": [[2, 3, 5, 8, 13]], "expected": "([2, 3, 5, 8, 13].index({target}) if {target} in [2, 3, 5, 8, 13] else -1)"},
        ],
    },
    {
        "title_template": "Count words longer than {n} characters",
        "description_template": "Write `count_long_words(words)` and return how many words have length greater than {n}.",
        "difficulty": QuestionTemplate.DIFFICULTY_MEDIUM,
        "topic": "strings",
        "parameter_schema": {"n": ["3", "4", "5", "6"]},
        "function_name": "count_long_words",
        "starter_code_template": "def count_long_words(words):\n    return 0\n",
        "test_cases_template": [
            {"input": [["code", "python", "ai", "academy"]], "expected": "sum(1 for word in ['code', 'python', 'ai', 'academy'] if len(word) > {n})"},
            {"input": [["sun", "moon", "stars", "sky"]], "expected": "sum(1 for word in ['sun', 'moon', 'stars', 'sky'] if len(word) > {n})"},
        ],
    },
    {
        "title_template": "Find a pair that sums to {target}",
        "description_template": "Write `has_pair_sum(values)` and return `True` if any two numbers sum to {target}, otherwise return `False`.",
        "difficulty": QuestionTemplate.DIFFICULTY_MEDIUM,
        "topic": "dictionaries",
        "parameter_schema": {"target": ["8", "10", "12", "15"]},
        "function_name": "has_pair_sum",
        "starter_code_template": "def has_pair_sum(values):\n    seen = set()\n    for value in values:\n        pass\n    return False\n",
        "test_cases_template": [
            {"input": [[1, 2, 3, 4, 5, 6]], "expected": "any((({target} - value) in {1, 2, 3, 4, 5, 6} and ({target} - value) != value) or ([1, 2, 3, 4, 5, 6].count(value) > 1 and value * 2 == {target}) for value in [1, 2, 3, 4, 5, 6])"},
            {"input": [[7, 11, 19]], "expected": "any((({target} - value) in {7, 11, 19} and ({target} - value) != value) or ([7, 11, 19].count(value) > 1 and value * 2 == {target}) for value in [7, 11, 19])"},
        ],
    },
    {
        "title_template": "Find the second largest unique number",
        "description_template": "Write `second_largest(values)` and return the second largest unique number in the list.",
        "difficulty": QuestionTemplate.DIFFICULTY_MEDIUM,
        "topic": "sorting",
        "parameter_schema": {},
        "function_name": "second_largest",
        "starter_code_template": "def second_largest(values):\n    return None\n",
        "test_cases_template": [
            {"input": [[4, 1, 9, 7, 9, 3]], "expected": 7},
            {"input": [[10, 5, 10, 8, 6]], "expected": 8},
        ],
    },
    {
        "title_template": "Compute the {n}th Fibonacci number",
        "description_template": "Write `fibonacci_n()` and return the {n}th Fibonacci number using an efficient recursive or dynamic programming approach.",
        "difficulty": QuestionTemplate.DIFFICULTY_HARD,
        "topic": "dynamic programming",
        "parameter_schema": {"n": ["8", "10", "12", "15"]},
        "function_name": "fibonacci_n",
        "starter_code_template": "def fibonacci_n():\n    # Return the {n}th Fibonacci number.\n    return 0\n",
        "test_cases_template": [
            {"input": [], "expected": "{fib_n}"},
        ],
    },
    {
        "title_template": "Minimum steps to reduce {n} to 1",
        "description_template": "Write `min_steps_to_one()` and return the minimum steps to reduce {n} to 1. Allowed operations: subtract 1, divide by 2 when even, divide by 3 when divisible by 3.",
        "difficulty": QuestionTemplate.DIFFICULTY_HARD,
        "topic": "dynamic programming",
        "parameter_schema": {"n": ["10", "12", "15", "18"]},
        "function_name": "min_steps_to_one",
        "starter_code_template": "def min_steps_to_one():\n    return 0\n",
        "test_cases_template": [
            {"input": [], "expected": "{min_steps_n}"},
        ],
    },
    {
        "title_template": "Longest consecutive sequence length",
        "description_template": "Write `longest_consecutive(values)` and return the length of the longest consecutive integer sequence in the list.",
        "difficulty": QuestionTemplate.DIFFICULTY_HARD,
        "topic": "searching",
        "parameter_schema": {},
        "function_name": "longest_consecutive",
        "starter_code_template": "def longest_consecutive(values):\n    return 0\n",
        "test_cases_template": [
            {"input": [[100, 4, 200, 1, 3, 2]], "expected": 4},
            {"input": [[9, 1, 4, 7, 3, 2, 6, 8, 0]], "expected": 7},
        ],
    },
    {
        "title_template": "Count staircase paths for {n} steps",
        "description_template": "Write `count_stair_paths()` and return the number of distinct ways to climb {n} steps when you can move 1 or 2 steps at a time.",
        "difficulty": QuestionTemplate.DIFFICULTY_HARD,
        "topic": "dynamic programming",
        "parameter_schema": {"n": ["5", "6", "7", "8"]},
        "function_name": "count_stair_paths",
        "starter_code_template": "def count_stair_paths():\n    return 0\n",
        "test_cases_template": [
            {"input": [], "expected": "{stairs_n}"},
        ],
    },
]


def _today():
    now = timezone.now().astimezone(CHALLENGE_TZ)
    publish_time = time(hour=PUBLISH_HOUR, minute=0)
    if now.timetz().replace(tzinfo=None) < publish_time:
        return now.date() - timedelta(days=1)
    return now.date()


def _publish_at_for_date(challenge_date):
    return datetime.combine(
        challenge_date,
        time(hour=PUBLISH_HOUR, minute=0),
        tzinfo=CHALLENGE_TZ,
    )


def _normalized_topic_keys(weak_topics):
    if isinstance(weak_topics, dict):
        return [key.lower() for key in weak_topics.keys()]
    return []


def _difficulty_for_problem(problem):
    if problem.difficulty in POOL_MAP[DailyChallenge.DIFFICULTY_EASY]:
        return DailyChallenge.DIFFICULTY_EASY
    if problem.difficulty in POOL_MAP[DailyChallenge.DIFFICULTY_HARD]:
        return DailyChallenge.DIFFICULTY_HARD
    return DailyChallenge.DIFFICULTY_MEDIUM


def _level_for_difficulty(difficulty):
    return {
        DailyChallenge.DIFFICULTY_EASY: 1,
        DailyChallenge.DIFFICULTY_MEDIUM: 2,
        DailyChallenge.DIFFICULTY_HARD: 3,
    }[difficulty]


def _pick_problems(all_problems, selected_ids, difficulty, weak_topics):
    allowed = POOL_MAP[difficulty]
    candidates = [problem for problem in all_problems if problem.id not in selected_ids and problem.difficulty in allowed]
    weak_candidates = [problem for problem in candidates if problem.topic.lower() in weak_topics]
    pool = weak_candidates or candidates
    random.shuffle(pool)
    picked = list(pool[:LEVEL_SIZE])
    if len(picked) < LEVEL_SIZE:
        fallback = [
            problem
            for problem in all_problems
            if problem.id not in selected_ids and problem.id not in {item.id for item in picked}
        ]
        random.shuffle(fallback)
        picked.extend(fallback[: LEVEL_SIZE - len(picked)])
    return picked


def _safe_format_string(template, params):
    if not template:
        return ""
    required = {
        field_name
        for _, field_name, _, _ in Formatter().parse(template)
        if field_name
    }
    values = {key: params.get(key, "{" + key + "}") for key in required}
    return template.format(**values)


def _coerce_rendered_value(value):
    if not isinstance(value, str):
        return value
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value


def _augment_template_params(params):
    enriched = dict(params)
    for key, value in list(params.items()):
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        enriched[f"{key}_plus"] = number + 1
        enriched[f"{key}_minus"] = number - 1
        enriched[f"{key}_times_2"] = number * 2
        enriched[f"{key}_times_3"] = number * 3

    if "n" in params:
        try:
            n_value = int(params["n"])
        except (TypeError, ValueError):
            n_value = None
        if n_value is not None:
            enriched["fib_n"] = _fibonacci_value(n_value)
            enriched["min_steps_n"] = _min_steps_to_one_value(n_value)
            enriched["stairs_n"] = _count_stair_paths_value(n_value)
    return enriched


def _render_template_value(value, params):
    if isinstance(value, str):
        return _coerce_rendered_value(_safe_format_string(value, params))
    if isinstance(value, list):
        return [_render_template_value(item, params) for item in value]
    if isinstance(value, dict):
        return {key: _render_template_value(item, params) for key, item in value.items()}
    return value


def _parameter_options(template):
    schema = template.parameter_schema or {}
    options = {}
    for key, raw_value in schema.items():
        if isinstance(raw_value, dict):
            values = raw_value.get("values", [])
        else:
            values = raw_value
        cleaned = [str(item).strip() for item in (values or []) if str(item).strip()]
        if cleaned:
            options[key] = cleaned
    return options


def _fibonacci_value(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _min_steps_to_one_value(n):
    dp = [0] * (n + 1)
    for value in range(2, n + 1):
        best = dp[value - 1] + 1
        if value % 2 == 0:
            best = min(best, dp[value // 2] + 1)
        if value % 3 == 0:
            best = min(best, dp[value // 3] + 1)
        dp[value] = best
    return dp[n]


def _count_stair_paths_value(n):
    if n <= 1:
        return 1
    a, b = 1, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def ensure_default_question_templates():
    if QuestionTemplate.objects.filter(
        is_active=True,
        approval_status=QuestionTemplate.STATUS_APPROVED,
    ).exists():
        return

    QuestionTemplate.objects.bulk_create(
        [
            QuestionTemplate(
                title_template=item["title_template"],
                description_template=item["description_template"],
                difficulty=item["difficulty"],
                topic=item["topic"],
                parameter_schema=item.get("parameter_schema", {}),
                starter_code_template=item.get("starter_code_template", ""),
                function_name=item.get("function_name", "solve"),
                test_cases_template=item.get("test_cases_template", []),
                hint1_template=item.get("hint1_template", ""),
                hint2_template=item.get("hint2_template", ""),
                approval_status=QuestionTemplate.STATUS_APPROVED,
                approved_at=timezone.now(),
                is_active=True,
            )
            for item in DEFAULT_QUESTION_TEMPLATES
        ]
    )


def _parameter_signature(params):
    if not params:
        return ""
    return "|".join(f"{key}={params[key]}" for key in sorted(params))


def _template_recent_history(template, challenge_date):
    cutoff = challenge_date - timedelta(days=30)
    return DailyChallengeQuestion.objects.filter(
        template=template,
        date_used__gte=cutoff,
        date_used__lt=challenge_date,
    )


def _select_template_parameters(template, challenge_date):
    options = _parameter_options(template)
    if not options:
        return {}

    keys = sorted(options)
    all_combinations = [
        dict(zip(keys, combo))
        for combo in itertools.product(*(options[key] for key in keys))
    ]
    if not all_combinations:
        return {}

    recent_signatures = set(
        _template_recent_history(template, challenge_date).exclude(parameter_signature="").values_list("parameter_signature", flat=True)
    )
    fresh = [combo for combo in all_combinations if _parameter_signature(combo) not in recent_signatures]
    pool = fresh or all_combinations
    return _augment_template_params(random.choice(pool))


def _build_template_hints(template, params):
    hint1 = _safe_format_string(template.hint1_template, params)
    hint2 = _safe_format_string(template.hint2_template, params)
    topic_label = (template.topic or "general").replace("_", " ").title()
    if not hint1:
        hint1 = f"Hint 1: Focus on the core {topic_label} pattern needed for {template.function_name}."
    if not hint2:
        hint2 = f"Hint 2: Start by writing {template.function_name} and handling the expected inputs step by step."
    return hint1, hint2


def _build_problem_from_template(template, params):
    rendered_title = _safe_format_string(template.title_template, params)
    rendered_description = _safe_format_string(template.description_template, params)
    rendered_starter = _safe_format_string(template.starter_code_template, params)
    rendered_tests = _render_template_value(template.test_cases_template, params)
    hint1, hint2 = _build_template_hints(template, params)
    return CodingProblem.objects.create(
        title=rendered_title,
        topic=template.topic,
        description=rendered_description,
        starter_code=rendered_starter,
        function_name=template.function_name,
        test_cases=rendered_tests if isinstance(rendered_tests, list) else [],
        hint1=hint1,
        hint2=hint2,
        difficulty={
            DailyChallenge.DIFFICULTY_EASY: CodingProblem.DIFFICULTY_BEGINNER,
            DailyChallenge.DIFFICULTY_MEDIUM: CodingProblem.DIFFICULTY_INTERMEDIATE,
            DailyChallenge.DIFFICULTY_HARD: CodingProblem.DIFFICULTY_ADVANCED,
        }[template.difficulty],
        is_active=False,
    )


def _candidate_templates(difficulty, challenge_date, preferred_topics=None, excluded_topics=None):
    recent_template_ids = set(
        DailyChallengeQuestion.objects.filter(
            date_used__gte=challenge_date - timedelta(days=30),
            date_used__lt=challenge_date,
        ).values_list("template_id", flat=True)
    )
    queryset = QuestionTemplate.objects.filter(
        difficulty=difficulty,
        is_active=True,
        approval_status=QuestionTemplate.STATUS_APPROVED,
    )

    def usable(items):
        return [item for item in items if item.test_cases_template]

    if preferred_topics:
        preferred_qs = queryset.filter(topic__in=preferred_topics)
        if excluded_topics:
            preferred_qs = preferred_qs.exclude(topic__in=excluded_topics)
        preferred = usable(list(preferred_qs.exclude(id__in=recent_template_ids)))
        if preferred:
            return preferred

    if excluded_topics:
        non_recent = usable(list(queryset.exclude(topic__in=excluded_topics).exclude(id__in=recent_template_ids)))
        if non_recent:
            return non_recent

    non_recent = usable(list(queryset.exclude(id__in=recent_template_ids)))
    if non_recent:
        return non_recent

    if excluded_topics:
        relaxed = usable(list(queryset.exclude(topic__in=excluded_topics)))
        if relaxed:
            return relaxed
    return usable(list(queryset))


def _pick_templates_for_difficulty(difficulty, challenge_date, preferred_topics, excluded_topics, limit=LEVEL_SIZE):
    candidates = _candidate_templates(difficulty, challenge_date, preferred_topics, excluded_topics)
    if not candidates:
        return []
    random.shuffle(candidates)
    return candidates[:limit]


def _build_challenge_from_template(template, challenge_set, question_number, preferred_topics):
    params = _select_template_parameters(template, challenge_set.date)
    generated_problem = _build_problem_from_template(template, params)
    difficulty = template.difficulty
    hint1, hint2 = _build_template_hints(template, params)
    return DailyChallenge(
        challenge_set=challenge_set,
        student=challenge_set.student,
        problem=generated_problem,
        template=template,
        date=challenge_set.date,
        title=generated_problem.title,
        description=generated_problem.description,
        topic=template.topic,
        generated_parameters=params,
        starter_code=build_starter_template(template.function_name, generated_problem.starter_code),
        function_name=template.function_name,
        test_cases=generated_problem.test_cases,
        difficulty=difficulty,
        level=_level_for_difficulty(difficulty),
        question_number=question_number,
        points=POINTS_BY_DIFFICULTY[difficulty],
        hint1=hint1,
        hint2=hint2,
    )


def _record_generation_history(challenge_rows):
    DailyChallengeQuestion.objects.bulk_create(
        [
            DailyChallengeQuestion(
                template=challenge.template,
                challenge=challenge,
                generated_question=challenge.title,
                parameters_used=challenge.generated_parameters,
                parameter_signature=_parameter_signature(challenge.generated_parameters),
                date_used=challenge.date,
            )
            for challenge in challenge_rows
            if challenge.template_id
        ]
    )


def _copy_problem(problem, challenge_set, question_number, difficulty):
    level = _level_for_difficulty(difficulty)
    return DailyChallenge(
        challenge_set=challenge_set,
        student=challenge_set.student,
        problem=problem,
        date=challenge_set.date,
        title=problem.title,
        description=problem.description,
        topic=problem.topic,
        starter_code=build_starter_template(problem.function_name, problem.starter_code),
        function_name=problem.function_name,
        test_cases=problem.test_cases,
        difficulty=difficulty,
        level=level,
        question_number=question_number,
        points=POINTS_BY_DIFFICULTY[difficulty],
        hint1=problem.hint1,
        hint2=problem.hint2,
    )


def _build_fallback_hints(problem):
    topic_label = (problem.topic or "general").replace("_", " ").title()
    return (
        f"Hint 1: Focus on the core {topic_label} pattern needed for {problem.function_name}.",
        f"Hint 2: Start by writing {problem.function_name} and handling the expected inputs step by step.",
    )


def _ensure_problem_hints(problem):
    changed = False
    hint1, hint2 = _build_fallback_hints(problem)
    if not problem.hint1:
        problem.hint1 = hint1
        changed = True
    if not problem.hint2:
        problem.hint2 = hint2
        changed = True
    if changed:
        problem.save(update_fields=["hint1", "hint2", "updated_at"])


def _sanitize_unsolved_challenge_code(challenge):
    safe_starter = build_starter_template(
        challenge.function_name,
        challenge.starter_code or challenge.problem.starter_code,
    )
    changed_fields = []

    if challenge.starter_code != safe_starter:
        challenge.starter_code = safe_starter
        changed_fields.append("starter_code")

    # Old daily challenge rows may still carry solved code in latest_code even
    # though the student has never attempted the question.
    if challenge.status == DailyChallenge.STATUS_PENDING and challenge.attempts == 0 and challenge.latest_code:
        challenge.latest_code = ""
        changed_fields.append("latest_code")

    if changed_fields:
        changed_fields.append("updated_at")
        challenge.save(update_fields=changed_fields)


def _should_regenerate_existing_set(challenge_set):
    expected_count = LEVEL_SIZE * 3
    if challenge_set.challenges.count() != expected_count:
        return True

    has_approved_templates = QuestionTemplate.objects.filter(
        is_active=True,
        approval_status=QuestionTemplate.STATUS_APPROVED,
    ).exists()
    if not has_approved_templates:
        return False

    # Legacy daily sets created before the template pool shipped contain only
    # fixed CodingProblem rows with no template linkage.
    if not challenge_set.challenges.filter(template__isnull=False).exists():
        return True

    return False


def generate_daily_challenges(student, challenge_date=None, force=False):
    ensure_default_assessment_content()
    ensure_default_question_templates()
    challenge_date = challenge_date or _today()

    if force:
        DailyChallengeSet.objects.filter(student=student, date=challenge_date).delete()

    existing_set = (
        DailyChallengeSet.objects.filter(student=student, date=challenge_date)
        .prefetch_related("challenges__problem")
        .first()
    )
    if existing_set:
        refresh_challenge_set(existing_set)
        return existing_set

    skill_profile = StudentSkill.objects.filter(student=student).first()
    weak_topics = _normalized_topic_keys(skill_profile.weak_topics if skill_profile else {})
    all_problems = list(CodingProblem.objects.filter(is_active=True).order_by("order", "id"))

    challenge_set = DailyChallengeSet.objects.create(
        student=student,
        date=challenge_date,
        published_at=_publish_at_for_date(challenge_date),
    )

    challenge_rows = []
    chosen_topics = set()
    question_number = 1
    for difficulty in (
        DailyChallenge.DIFFICULTY_EASY,
        DailyChallenge.DIFFICULTY_MEDIUM,
        DailyChallenge.DIFFICULTY_HARD,
    ):
        templates = _pick_templates_for_difficulty(
            difficulty,
            challenge_date,
            preferred_topics=weak_topics,
            excluded_topics=chosen_topics,
        )
        for template in templates:
            challenge_rows.append(_build_challenge_from_template(template, challenge_set, question_number, weak_topics))
            chosen_topics.add(template.topic)
            question_number += 1

        selected_ids = {item.problem_id for item in challenge_rows if item.problem_id}
        fallback = _pick_problems(all_problems, selected_ids, difficulty, weak_topics)
        if len(templates) >= LEVEL_SIZE:
            continue

        used_problem_ids = set(
            DailyChallenge.objects.filter(
                date__gte=challenge_date - timedelta(days=30),
                date__lt=challenge_date,
            ).values_list("problem_id", flat=True)
        )
        remaining_slots = LEVEL_SIZE - len(templates)
        fresh_fallback = [item for item in fallback if item.id not in used_problem_ids]
        fallback_pool = fresh_fallback if len(fresh_fallback) >= remaining_slots else fallback
        for problem in fallback_pool[:remaining_slots]:
            _ensure_problem_hints(problem)
            challenge_rows.append(_copy_problem(problem, challenge_set, question_number, difficulty))
            chosen_topics.add(problem.topic.lower())
            question_number += 1

    DailyChallenge.objects.bulk_create(challenge_rows)
    stored_rows = list(DailyChallenge.objects.filter(challenge_set=challenge_set).select_related("template", "problem"))
    _record_generation_history(stored_rows)
    return DailyChallengeSet.objects.prefetch_related("challenges__problem").get(id=challenge_set.id)


def get_today_challenge_set(student):
    challenge_date = _today()
    challenge_set = (
        DailyChallengeSet.objects.filter(student=student, date=challenge_date)
        .prefetch_related("challenges__problem")
        .first()
    )
    if challenge_set:
        if _should_regenerate_existing_set(challenge_set):
            challenge_set.delete()
            return generate_daily_challenges(student, challenge_date=challenge_date)
        for item in challenge_set.challenges.all():
            _sanitize_unsolved_challenge_code(item)
        expected_publish_at = _publish_at_for_date(challenge_set.date)
        if challenge_set.published_at != expected_publish_at:
            challenge_set.published_at = expected_publish_at
            challenge_set.save(update_fields=["published_at", "updated_at"])
        refresh_challenge_set(challenge_set)
        return DailyChallengeSet.objects.prefetch_related("challenges__problem").get(id=challenge_set.id)
    return generate_daily_challenges(student, challenge_date=challenge_date)


def assign_daily_challenges(challenge_date=None):
    challenge_date = challenge_date or _today()
    generated_sets = []
    for student in User.objects.filter(role="student", is_active=True):
        generated_sets.append(generate_daily_challenges(student, challenge_date=challenge_date))
    return generated_sets


def regenerate_daily_challenges(student=None, challenge_date=None):
    challenge_date = challenge_date or _today()
    targets = [student] if student is not None else list(User.objects.filter(role="student", is_active=True))
    regenerated = []
    for target in targets:
        regenerated.append(generate_daily_challenges(target, challenge_date=challenge_date, force=True))
    return regenerated


def _run_code(problem, code):
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-c", RUNNER_SCRIPT],
            input=json.dumps(
                {
                    "code": code,
                    "function_name": problem.function_name,
                    "test_cases": problem.test_cases,
                }
            ),
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return [], "timeout", "Execution timed out."

    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "Execution failed.").strip()
        lowered = stderr.lower()
        error_type = "compilation" if any(token in lowered for token in ("syntaxerror", "indentationerror", "valueerror", "restricted")) else "runtime"
        return [], error_type, stderr

    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return [], "runtime", "Execution returned an invalid response."

    return payload.get("results", []), "", ""


def _summarize_results(results, error_type):
    summary = {
        "passed": 0,
        "failed": 0,
        "runtime": 0,
        "compilation": 0,
        "timeout": 0,
    }
    for item in results:
        if item.get("passed"):
            summary["passed"] += 1
        elif item.get("error_type") == "runtime":
            summary["runtime"] += 1
        else:
            summary["failed"] += 1

    if error_type == "timeout":
        summary["timeout"] += 1
    elif error_type == "compilation":
        summary["compilation"] += 1
    elif error_type == "runtime" and not results:
        summary["runtime"] += 1
    return summary


def _calculate_penalty(summary, hints_used):
    return (
        summary["failed"] * PENALTY_WEIGHTS["failed"]
        + summary["runtime"] * PENALTY_WEIGHTS["runtime"]
        + summary["compilation"] * PENALTY_WEIGHTS["compilation"]
        + summary["timeout"] * PENALTY_WEIGHTS["timeout"]
    )


def _calculate_final_score(challenge, summary):
    solved = (
        summary["failed"] == 0
        and summary["runtime"] == 0
        and summary["compilation"] == 0
        and summary["timeout"] == 0
        and summary["passed"] == len(challenge.test_cases)
        and len(challenge.test_cases) > 0
    )
    penalty = _calculate_penalty(summary, challenge.hints_used)
    final_score = max(0, challenge.points - penalty) if solved else 0
    return solved, penalty, final_score


def challenge_attempt_limit(challenge):
    return ATTEMPT_LIMITS.get(challenge.difficulty, 10)


def _recalculate_student_points(student):
    earned = DailyChallengeSet.objects.filter(student=student).aggregate(total=Sum("total_score"))["total"] or 0
    spent = DailyChallenge.objects.filter(student=student).aggregate(total=Sum("hints_used"))["total"] or 0
    points, _ = StudentPoints.objects.get_or_create(student=student)
    points.total_points = earned
    points.points_spent = spent * HINT_COST
    points.points_remaining = max(0, earned - points.points_spent)
    points.save(update_fields=["total_points", "points_spent", "points_remaining", "updated_at"])
    return points


def update_student_skill_from_daily_score(student, daily_score):
    profile, _ = StudentSkill.objects.get_or_create(
        student=student,
        defaults={
            "skill_score": 0,
            "skill_level": StudentSkill.LEVEL_BEGINNER,
            "weak_topics": {},
            "strong_topics": [],
            "assessment_snapshot": {},
        },
    )
    old_score = Decimal(str(profile.skill_score or 0))
    new_score = quantize_score((old_score * Decimal("0.8")) + (Decimal(daily_score) * Decimal("0.2")))
    capped_score = min(new_score, Decimal("100"))

    snapshot = profile.assessment_snapshot or {}
    snapshot["latest_daily_score"] = daily_score
    snapshot["last_daily_update"] = timezone.now().isoformat()

    profile.skill_score = capped_score
    profile.skill_level = classify_skill_level(capped_score)
    profile.assessment_snapshot = snapshot
    profile.save(update_fields=["skill_score", "skill_level", "assessment_snapshot", "updated_at"])
    return profile


def refresh_challenge_set(challenge_set):
    total_score = challenge_set.challenges.aggregate(total=Sum("score"))["total"] or 0
    solved_count = challenge_set.challenges.filter(status=DailyChallenge.STATUS_SOLVED).count()
    easy_solved = challenge_set.challenges.filter(
        status=DailyChallenge.STATUS_SOLVED, level=1
    ).count()
    medium_solved = challenge_set.challenges.filter(
        status=DailyChallenge.STATUS_SOLVED, level=2
    ).count()
    hard_solved = challenge_set.challenges.filter(
        status=DailyChallenge.STATUS_SOLVED, level=3
    ).count()
    completed = solved_count == challenge_set.challenges.count()

    challenge_set.total_score = total_score
    challenge_set.solved_count = solved_count
    challenge_set.easy_solved_count = easy_solved
    challenge_set.medium_solved_count = medium_solved
    challenge_set.hard_solved_count = hard_solved
    challenge_set.completed = completed
    challenge_set.save(
        update_fields=[
            "total_score",
            "solved_count",
            "easy_solved_count",
            "medium_solved_count",
            "hard_solved_count",
            "completed",
            "updated_at",
        ]
    )
    _recalculate_student_points(challenge_set.student)
    return challenge_set


def level_unlock_state(challenge_set):
    return {
        1: True,
        2: challenge_set.easy_solved_count >= 2,
        3: challenge_set.medium_solved_count >= 2,
    }


def can_access_challenge(challenge):
    unlocks = level_unlock_state(challenge.challenge_set)
    return unlocks.get(challenge.level, False)


def preview_solution(challenge, code):
    refresh_challenge_set(challenge.challenge_set)
    if not can_access_challenge(challenge):
        return {"allowed": False, "error": "Solve the required lower-level challenges first.", "results": [], "summary": {}}
    if challenge.attempts >= challenge_attempt_limit(challenge):
        return {"allowed": False, "error": "Attempt limit reached for this question.", "results": [], "summary": {}}

    results, error_type, error_message = _run_code(challenge, code)
    summary = _summarize_results(results, error_type)
    penalty = _calculate_penalty(summary, challenge.hints_used)
    preview_score = max(0, challenge.points - penalty)
    return {
        "allowed": True,
        "error": error_message,
        "error_type": error_type,
        "results": results,
        "summary": summary,
        "penalty_points": penalty,
        "preview_score": preview_score,
    }


def unlock_hint(challenge):
    if challenge.hints_used >= 2:
        return {"ok": False, "error": "Both hints are already unlocked."}

    points, _ = StudentPoints.objects.get_or_create(student=challenge.student)
    if points.points_remaining < HINT_COST:
        return {"ok": False, "error": f"Not enough points. You need {HINT_COST} points to unlock a hint, but you have {points.points_remaining} available."}

    challenge.hints_used += 1
    challenge.save(update_fields=["hints_used", "updated_at"])
    refresh_challenge_set(challenge.challenge_set)

    return {
        "ok": True,
        "hints_used": challenge.hints_used,
        "hint_text": challenge.hint1 if challenge.hints_used == 1 else challenge.hint2,
    }


def submit_solution_for_challenge(challenge, code):
    refresh_challenge_set(challenge.challenge_set)
    attempt_limit = challenge_attempt_limit(challenge)
    if challenge.student_id != challenge.challenge_set.student_id:
        return {"ok": False, "error": "Challenge owner mismatch."}
    if not can_access_challenge(challenge):
        return {"ok": False, "error": "Solve the required lower-level challenges first."}
    if challenge.attempts >= attempt_limit:
        return {"ok": False, "error": "Attempt limit reached."}

    challenge.attempts += 1
    challenge.latest_code = code

    results, error_type, error_message = _run_code(challenge, code)
    summary = _summarize_results(results, error_type)
    solved, penalty, final_score = _calculate_final_score(challenge, summary)

    challenge.failed_tests = summary["failed"]
    challenge.runtime_errors = summary["runtime"]
    challenge.compilation_errors = summary["compilation"]
    challenge.timeout_errors = summary["timeout"]
    challenge.penalty_points = penalty
    challenge.score = final_score
    challenge.latest_result = {
        "results": results,
        "summary": summary,
        "error": error_message,
        "error_type": error_type,
    }
    challenge.status = DailyChallenge.STATUS_SOLVED if solved else DailyChallenge.STATUS_PENDING
    if challenge.attempts >= attempt_limit and not solved:
        challenge.status = DailyChallenge.STATUS_FAILED

    challenge.save(
        update_fields=[
            "attempts",
            "latest_code",
            "failed_tests",
            "runtime_errors",
            "compilation_errors",
            "timeout_errors",
            "penalty_points",
            "score",
            "latest_result",
            "status",
            "updated_at",
        ]
    )

    StudentChallengeAttempt.objects.create(
        student=challenge.student,
        challenge=challenge,
        code=code,
        passed_tests=summary["passed"],
        failed_tests=summary["failed"],
        runtime_errors=summary["runtime"],
        compilation_errors=summary["compilation"],
        timeout_errors=summary["timeout"],
        hints_used=challenge.hints_used,
        penalty_points=penalty,
        final_score=final_score,
        solved=solved,
        result_payload={
            "results": results,
            "summary": summary,
            "error": error_message,
            "error_type": error_type,
        },
    )

    refresh_challenge_set(challenge.challenge_set)
    challenge.challenge_set.refresh_from_db()
    update_student_skill_from_daily_score(challenge.student, challenge.challenge_set.total_score)

    message = "Challenge solved successfully." if solved else "Submission recorded. Review the failing output and try again."
    if challenge.status == DailyChallenge.STATUS_FAILED:
        message = "Attempt limit reached. This question is now locked for the day."

    return {
        "ok": True,
        "solved": solved,
        "message": message,
        "error": error_message,
        "error_type": error_type,
        "results": results,
        "summary": summary,
        "penalty_points": penalty,
        "final_score": final_score,
        "challenge": challenge,
        "challenge_set": challenge.challenge_set,
        "attempt_limit": attempt_limit,
    }


def challenge_dashboard_stats(challenge_date=None):
    challenge_date = challenge_date or _today()
    sets = DailyChallengeSet.objects.filter(date=challenge_date).prefetch_related("challenges", "student")
    challenge_items = DailyChallenge.objects.filter(date=challenge_date)
    leaderboard = StudentPoints.objects.select_related("student").order_by("-total_points", "student__username")[:10]
    attempt_stats = StudentChallengeAttempt.objects.filter(challenge__date=challenge_date).aggregate(
        total_attempts=Count("id"),
        hint_uses=Sum("hints_used"),
    )

    return {
        "sets": sets,
        "solved_count": challenge_items.filter(status=DailyChallenge.STATUS_SOLVED).count(),
        "pending_count": challenge_items.filter(status=DailyChallenge.STATUS_PENDING).count(),
        "failed_count": challenge_items.filter(status=DailyChallenge.STATUS_FAILED).count(),
        "top_students": sets.order_by("-total_score", "student__username")[:8],
        "leaderboard": leaderboard,
        "attempt_count": attempt_stats["total_attempts"] or 0,
        "hint_usage_count": attempt_stats["hint_uses"] or 0,
        "question_pool_count": QuestionTemplate.objects.filter(
            is_active=True,
            approval_status=QuestionTemplate.STATUS_APPROVED,
        ).count(),
        "pending_template_count": QuestionTemplate.objects.filter(
            approval_status=QuestionTemplate.STATUS_PENDING
        ).count(),
        "recent_template_rows": QuestionTemplate.objects.select_related("created_by", "approved_by").order_by("-updated_at")[:8],
    }
