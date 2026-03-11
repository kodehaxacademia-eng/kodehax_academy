import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.utils import timezone

from skill_assessment.models import CodingProblem, StudentSkill
from skill_assessment.services import (
    classify_skill_level,
    ensure_default_assessment_content,
    quantize_score,
    run_code_against_test_cases,
)

from .models import DailyChallenge, DailyChallengeSet

User = get_user_model()

MAX_ATTEMPTS = 3
DIFFICULTY_SCORE_MAP = {
    CodingProblem.DIFFICULTY_BEGINNER: 10,
    CodingProblem.DIFFICULTY_BASIC: 20,
    CodingProblem.DIFFICULTY_INTERMEDIATE: 20,
    CodingProblem.DIFFICULTY_ADVANCED: 30,
}
FIRST_ATTEMPT_BONUS = 5

DIFFICULTY_GROUPS = {
    "easy": [CodingProblem.DIFFICULTY_BEGINNER],
    "medium": [CodingProblem.DIFFICULTY_BASIC, CodingProblem.DIFFICULTY_INTERMEDIATE],
    "hard": [CodingProblem.DIFFICULTY_ADVANCED],
}

LEVEL_PLANS = {
    StudentSkill.LEVEL_BEGINNER: ["easy", "easy", "easy"],
    StudentSkill.LEVEL_BASIC: ["easy", "easy", "easy"],
    StudentSkill.LEVEL_INTERMEDIATE: ["easy", "medium", "medium"],
    StudentSkill.LEVEL_ADVANCED: ["medium", "medium", "hard"],
    StudentSkill.LEVEL_EXPERT: ["medium", "hard", "hard"],
}


def _today():
    return timezone.localdate()


def _normalized_topic_keys(weak_topics):
    if isinstance(weak_topics, dict):
        return [key.lower() for key in weak_topics.keys()]
    return []


def _score_for_problem(problem, attempts):
    base_score = DIFFICULTY_SCORE_MAP.get(problem.difficulty, 10)
    if attempts == 1:
        return base_score + FIRST_ATTEMPT_BONUS
    return base_score


def _pick_from_pool(candidate_pool, selected_ids, needed):
    remaining = [problem for problem in candidate_pool if problem.id not in selected_ids]
    random.shuffle(remaining)
    return remaining[:needed]


def generate_daily_challenges(student, challenge_date=None, force=False):
    ensure_default_assessment_content()
    challenge_date = challenge_date or _today()

    if force:
        DailyChallenge.objects.filter(student=student, date=challenge_date).delete()
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
    skill_level = (
        skill_profile.skill_level if skill_profile else StudentSkill.LEVEL_BEGINNER
    )
    weak_topics = _normalized_topic_keys(
        skill_profile.weak_topics if skill_profile else {}
    )

    plan = LEVEL_PLANS.get(skill_level, LEVEL_PLANS[StudentSkill.LEVEL_BEGINNER])
    all_problems = list(
        CodingProblem.objects.filter(is_active=True).order_by("order", "id")
    )
    selected = []
    selected_ids = set()

    for band in plan:
        band_difficulties = DIFFICULTY_GROUPS[band]
        weak_pool = [
            problem
            for problem in all_problems
            if problem.difficulty in band_difficulties and problem.topic.lower() in weak_topics
        ]
        chosen = _pick_from_pool(weak_pool, selected_ids, 1)
        if not chosen:
            normal_pool = [
                problem for problem in all_problems if problem.difficulty in band_difficulties
            ]
            chosen = _pick_from_pool(normal_pool, selected_ids, 1)
        if not chosen:
            chosen = _pick_from_pool(all_problems, selected_ids, 1)
        if chosen:
            selected.extend(chosen)
            selected_ids.update(problem.id for problem in chosen)

    if len(selected) < 3:
        fillers = _pick_from_pool(all_problems, selected_ids, 3 - len(selected))
        selected.extend(fillers)
        selected_ids.update(problem.id for problem in fillers)

    challenge_set = DailyChallengeSet.objects.create(
        student=student,
        date=challenge_date,
    )
    for problem in selected[:3]:
        DailyChallenge.objects.create(
            challenge_set=challenge_set,
            student=student,
            problem=problem,
            date=challenge_date,
        )

    return DailyChallengeSet.objects.prefetch_related("challenges__problem").get(
        id=challenge_set.id
    )


def refresh_challenge_set(challenge_set):
    if challenge_set.is_expired:
        challenge_set.challenges.filter(status=DailyChallenge.STATUS_PENDING).update(
            status=DailyChallenge.STATUS_FAILED
        )

    total_score = (
        challenge_set.challenges.aggregate(total=Sum("score"))["total"] or 0
    )
    completed = not challenge_set.challenges.filter(
        status=DailyChallenge.STATUS_PENDING
    ).exists()

    challenge_set.total_score = total_score
    challenge_set.completed = completed
    challenge_set.save(update_fields=["total_score", "completed", "updated_at"])
    return challenge_set


def get_today_challenge_set(student):
    challenge_set = (
        DailyChallengeSet.objects.filter(student=student, date=_today())
        .prefetch_related("challenges__problem")
        .first()
    )
    if challenge_set:
        refresh_challenge_set(challenge_set)
        return DailyChallengeSet.objects.prefetch_related("challenges__problem").get(
            id=challenge_set.id
        )
    return generate_daily_challenges(student)


def assign_daily_challenges(challenge_date=None):
    challenge_date = challenge_date or _today()
    generated_sets = []
    for student in User.objects.filter(role="student", is_active=True):
        generated_sets.append(generate_daily_challenges(student, challenge_date=challenge_date))
    return generated_sets


def regenerate_daily_challenges(student=None, challenge_date=None):
    challenge_date = challenge_date or _today()
    if student is not None:
        return [generate_daily_challenges(student, challenge_date=challenge_date, force=True)]

    regenerated = []
    for target in User.objects.filter(role="student", is_active=True):
        regenerated.append(
            generate_daily_challenges(target, challenge_date=challenge_date, force=True)
        )
    return regenerated


def preview_solution(challenge, code):
    refresh_challenge_set(challenge.challenge_set)
    if challenge.challenge_set.is_expired:
        return {
            "allowed": False,
            "error": "This daily challenge has expired.",
            "results": [],
        }
    results, error = run_code_against_test_cases(challenge.problem, code)
    return {
        "allowed": True,
        "error": error,
        "results": results,
    }


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


def submit_solution_for_challenge(challenge, code):
    refresh_challenge_set(challenge.challenge_set)
    if challenge.student_id != challenge.challenge_set.student_id:
        return {"ok": False, "error": "Challenge owner mismatch."}
    if challenge.challenge_set.is_expired:
        return {"ok": False, "error": "This daily challenge has expired."}
    if challenge.status != DailyChallenge.STATUS_PENDING:
        return {"ok": False, "error": "This challenge is already closed."}
    if challenge.attempts >= MAX_ATTEMPTS:
        challenge.status = DailyChallenge.STATUS_FAILED
        challenge.save(update_fields=["status", "updated_at"])
        refresh_challenge_set(challenge.challenge_set)
        return {"ok": False, "error": "Attempt limit reached."}

    challenge.attempts += 1
    challenge.latest_code = code
    results, error = run_code_against_test_cases(challenge.problem, code)
    solved = bool(results) and all(item.get("passed") for item in results) and not error

    if solved:
        challenge.status = DailyChallenge.STATUS_SOLVED
        challenge.score = _score_for_problem(challenge.problem, challenge.attempts)
        message = "Challenge solved successfully."
    else:
        if challenge.attempts >= MAX_ATTEMPTS:
            challenge.status = DailyChallenge.STATUS_FAILED
            message = "Challenge failed after the maximum number of attempts."
        else:
            challenge.status = DailyChallenge.STATUS_PENDING
            message = "Solution submitted. Review the failed test cases and try again."

    challenge.save(update_fields=["attempts", "latest_code", "status", "score", "updated_at"])
    refresh_challenge_set(challenge.challenge_set)
    challenge.challenge_set.refresh_from_db()
    update_student_skill_from_daily_score(challenge.student, challenge.challenge_set.total_score)

    return {
        "ok": True,
        "solved": solved,
        "message": message,
        "error": error,
        "results": results,
        "challenge": challenge,
        "challenge_set": challenge.challenge_set,
    }


def challenge_dashboard_stats(challenge_date=None):
    challenge_date = challenge_date or _today()
    sets = DailyChallengeSet.objects.filter(date=challenge_date).prefetch_related("challenges", "student")
    challenge_items = DailyChallenge.objects.filter(date=challenge_date)

    return {
        "sets": sets,
        "solved_count": challenge_items.filter(status=DailyChallenge.STATUS_SOLVED).count(),
        "pending_count": challenge_items.filter(status=DailyChallenge.STATUS_PENDING).count(),
        "failed_count": challenge_items.filter(status=DailyChallenge.STATUS_FAILED).count(),
        "top_students": sets.order_by("-total_score", "student__username")[:8],
    }
