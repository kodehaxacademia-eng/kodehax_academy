import ast
import json
import random
import subprocess
import sys
from datetime import datetime, time, timedelta
from decimal import Decimal
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

from .models import DailyChallenge, DailyChallengeSet, StudentChallengeAttempt, StudentPoints

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


def _copy_problem(problem, challenge_set, question_number, difficulty):
    level = _level_for_difficulty(difficulty)
    return DailyChallenge(
        challenge_set=challenge_set,
        student=challenge_set.student,
        problem=problem,
        date=challenge_set.date,
        title=problem.title,
        description=problem.description,
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


def generate_daily_challenges(student, challenge_date=None, force=False):
    ensure_default_assessment_content()
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

    selected_by_difficulty = {}
    selected_ids = set()
    for difficulty in (
        DailyChallenge.DIFFICULTY_EASY,
        DailyChallenge.DIFFICULTY_MEDIUM,
        DailyChallenge.DIFFICULTY_HARD,
    ):
        picked = _pick_problems(all_problems, selected_ids, difficulty, weak_topics)
        selected_by_difficulty[difficulty] = picked
        selected_ids.update(problem.id for problem in picked)

    challenge_set = DailyChallengeSet.objects.create(
        student=student,
        date=challenge_date,
        published_at=_publish_at_for_date(challenge_date),
    )

    challenge_rows = []
    question_number = 1
    for difficulty in (
        DailyChallenge.DIFFICULTY_EASY,
        DailyChallenge.DIFFICULTY_MEDIUM,
        DailyChallenge.DIFFICULTY_HARD,
    ):
        subset = selected_by_difficulty.get(difficulty, [])
        for problem in subset:
            _ensure_problem_hints(problem)
            challenge_rows.append(_copy_problem(problem, challenge_set, question_number, difficulty))
            question_number += 1

    DailyChallenge.objects.bulk_create(challenge_rows)
    return DailyChallengeSet.objects.prefetch_related("challenges__problem").get(id=challenge_set.id)


def get_today_challenge_set(student):
    challenge_date = _today()
    challenge_set = (
        DailyChallengeSet.objects.filter(student=student, date=challenge_date)
        .prefetch_related("challenges__problem")
        .first()
    )
    if challenge_set:
        for item in challenge_set.challenges.all():
            _sanitize_unsolved_challenge_code(item)
        expected_publish_at = _publish_at_for_date(challenge_set.date)
        if challenge_set.published_at != expected_publish_at:
            challenge_set.published_at = expected_publish_at
            challenge_set.save(update_fields=["published_at", "updated_at"])
        if challenge_set.challenges.count() != 9:
            challenge_set.delete()
            return generate_daily_challenges(student)
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
        + hints_used * HINT_COST
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
    points.points_remaining = earned
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
        "question_pool_count": CodingProblem.objects.filter(is_active=True).count(),
    }
