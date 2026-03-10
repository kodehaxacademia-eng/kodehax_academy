from __future__ import annotations

from collections import defaultdict

from django.db.models import Avg, Count, Q

from teacher.models import (
    Assignment,
    CodeSubmission,
    PerformanceRecord,
    QuizAnswer,
    QuizResult,
    Submission,
)


def _upsert_performance_record(
    *,
    student,
    assignment: Assignment,
    score,
    submitted_at,
    feedback: str,
    evaluation_type: str,
    assignment_ref=None,
    is_deleted_assignment: bool = False,
) -> PerformanceRecord:
    due_date = assignment.due_date
    was_on_time = True
    if submitted_at and due_date:
        was_on_time = submitted_at <= due_date

    record, _ = PerformanceRecord.objects.update_or_create(
        student=student,
        original_assignment_id=assignment.id,
        defaults={
            "classroom": assignment.classroom,
            "assignment": assignment_ref if assignment_ref else assignment,
            "assignment_title": assignment.title,
            "assignment_type": assignment.assignment_type,
            "score": score,
            "max_score": assignment.max_score,
            "submitted_at": submitted_at,
            "due_date_snapshot": due_date,
            "was_on_time": was_on_time,
            "evaluation_type": evaluation_type,
            "feedback": (feedback or "").strip(),
            "is_deleted_assignment": is_deleted_assignment,
        },
    )
    return record


def sync_file_submission_record(submission: Submission, evaluation_type: str) -> PerformanceRecord:
    return _upsert_performance_record(
        student=submission.student,
        assignment=submission.assignment,
        score=submission.score,
        submitted_at=submission.submitted_at,
        feedback=submission.ai_feedback,
        evaluation_type=evaluation_type,
        assignment_ref=submission.assignment,
    )


def sync_code_submission_record(code_submission: CodeSubmission, evaluation_type: str) -> PerformanceRecord:
    return _upsert_performance_record(
        student=code_submission.student,
        assignment=code_submission.assignment,
        score=code_submission.score,
        submitted_at=code_submission.submitted_at,
        feedback=code_submission.ai_feedback,
        evaluation_type=evaluation_type,
        assignment_ref=code_submission.assignment,
    )


def sync_quiz_result_record(result: QuizResult, evaluation_type: str = PerformanceRecord.EVALUATION_TYPE_AUTO) -> PerformanceRecord:
    return _upsert_performance_record(
        student=result.student,
        assignment=result.assignment,
        score=result.score,
        submitted_at=result.evaluated_at,
        feedback=result.feedback,
        evaluation_type=evaluation_type,
        assignment_ref=result.assignment,
    )


def snapshot_assignment_performance(assignment: Assignment) -> None:
    # Persist all available performance data before assignment deletion.
    if assignment.assignment_type == Assignment.ASSIGNMENT_TYPE_FILE:
        for submission in assignment.submissions.select_related("student").all():
            _upsert_performance_record(
                student=submission.student,
                assignment=assignment,
                score=submission.score,
                submitted_at=submission.submitted_at,
                feedback=submission.ai_feedback,
                evaluation_type=PerformanceRecord.EVALUATION_TYPE_AI,
                assignment_ref=None,
                is_deleted_assignment=True,
            )
        return

    if assignment.assignment_type == Assignment.ASSIGNMENT_TYPE_CODE:
        for submission in assignment.code_submissions.select_related("student").all():
            _upsert_performance_record(
                student=submission.student,
                assignment=assignment,
                score=submission.score,
                submitted_at=submission.submitted_at,
                feedback=submission.ai_feedback,
                evaluation_type=PerformanceRecord.EVALUATION_TYPE_AI,
                assignment_ref=None,
                is_deleted_assignment=True,
            )
        return

    quiz_results = assignment.quiz_results.select_related("student").all()
    if quiz_results.exists():
        for result in quiz_results:
            _upsert_performance_record(
                student=result.student,
                assignment=assignment,
                score=result.score,
                submitted_at=result.evaluated_at,
                feedback=result.feedback,
                evaluation_type=PerformanceRecord.EVALUATION_TYPE_AUTO,
                assignment_ref=None,
                is_deleted_assignment=True,
            )
        return

    student_ids = QuizAnswer.objects.filter(
        question__assignment=assignment
    ).values_list("student_id", flat=True).distinct()
    for student in assignment.classroom.students.filter(id__in=student_ids):
        _upsert_performance_record(
            student=student,
            assignment=assignment,
            score=None,
            submitted_at=None,
            feedback="Quiz attempted but no evaluated score found before deletion.",
            evaluation_type=PerformanceRecord.EVALUATION_TYPE_AUTO,
            assignment_ref=None,
            is_deleted_assignment=True,
        )


def get_student_performance_summary(student):
    records = PerformanceRecord.objects.filter(student=student).select_related("classroom").order_by("submitted_at", "recorded_at")
    active_total_assignments = Assignment.objects.filter(classroom__students=student).count()
    completed_records = records.filter(submitted_at__isnull=False)

    avg_score = completed_records.aggregate(value=Avg("score"))["value"] or 0
    highest_score = completed_records.order_by("-score").values_list("score", flat=True).first()
    lowest_score = completed_records.order_by("score").values_list("score", flat=True).first()

    completed_count = completed_records.values("original_assignment_id").distinct().count()
    on_time_count = completed_records.filter(was_on_time=True).values("original_assignment_id").distinct().count()

    completion_percentage = round((completed_count / active_total_assignments) * 100, 2) if active_total_assignments else 0
    completion_percentage = min(completion_percentage, 100.0)
    on_time_rate = round((on_time_count / completed_count) * 100, 2) if completed_count else 0

    score_labels = []
    score_values = []
    bar_labels = []
    bar_values = []
    for record in records:
        if record.score is None:
            continue
        when = record.submitted_at or record.recorded_at
        label = f"{record.assignment_title} ({when.strftime('%d %b')})"
        score_labels.append(label)
        score_values.append(round(float(record.score), 2))
        bar_labels.append(record.assignment_title)
        bar_values.append(round(float(record.score), 2))

    daily_submission_counter = defaultdict(int)
    for record in completed_records:
        when = record.submitted_at or record.recorded_at
        daily_submission_counter[when.date()] += 1

    cumulative = 0
    trend_labels = []
    trend_values = []
    for day in sorted(daily_submission_counter.keys()):
        cumulative += daily_submission_counter[day]
        trend_labels.append(day.strftime("%d %b"))
        trend_values.append(cumulative)

    return {
        "summary": {
            "average_score": round(avg_score, 2),
            "highest_score": round(float(highest_score), 2) if highest_score is not None else 0,
            "lowest_score": round(float(lowest_score), 2) if lowest_score is not None else 0,
            "assignments_completed": completed_count,
            "total_assignments": active_total_assignments,
            "completion_percentage": completion_percentage,
            "submission_rate": completion_percentage,
            "on_time_submission_rate": on_time_rate,
        },
        "records": records,
        "charts": {
            "score_progression_labels": score_labels,
            "score_progression_values": score_values,
            "assignment_score_labels": bar_labels,
            "assignment_score_values": bar_values,
            "submission_trend_labels": trend_labels,
            "submission_trend_values": trend_values,
        },
    }


def get_classroom_performance_analytics(classroom):
    students = list(classroom.students.all())
    total_students = len(students)
    total_assignments = classroom.assignments.count()

    records = PerformanceRecord.objects.filter(
        classroom=classroom,
        student__in=students,
    ).select_related("student")
    records_with_scores = records.filter(score__isnull=False)
    class_average_score = records_with_scores.aggregate(value=Avg("score"))["value"] or 0

    completion_denominator = total_assignments * total_students
    completed_submissions = records.filter(submitted_at__isnull=False).values(
        "student_id", "original_assignment_id"
    ).distinct().count()
    completion_rate = round((completed_submissions / completion_denominator) * 100, 2) if completion_denominator else 0
    completion_rate = min(completion_rate, 100.0)

    student_stats = {
        row["student_id"]: row
        for row in records.values("student_id").annotate(
            assignments_completed=Count(
                "original_assignment_id",
                filter=Q(submitted_at__isnull=False),
                distinct=True,
            ),
            average_score=Avg("score"),
        )
    }

    student_rows = []
    ranking_labels = []
    ranking_values = []
    distribution = {"High": 0, "Medium": 0, "Low": 0}

    for student in students:
        stat = student_stats.get(student.id, {})
        completed_count = stat.get("assignments_completed", 0) or 0
        avg_score = stat.get("average_score")
        submission_rate = round((completed_count / total_assignments) * 100, 2) if total_assignments else 0
        submission_rate = min(submission_rate, 100.0)

        avg_score_value = round(float(avg_score), 2) if avg_score is not None else 0
        if avg_score is None:
            level = "Low"
        elif avg_score_value >= 80:
            level = "High"
        elif avg_score_value >= 50:
            level = "Medium"
        else:
            level = "Low"
        distribution[level] += 1

        student_rows.append({
            "student": student,
            "assignments_completed": completed_count,
            "average_score": avg_score_value,
            "submission_rate": submission_rate,
            "performance_level": level,
        })
        ranking_labels.append(student.username)
        ranking_values.append(avg_score_value)

    student_rows.sort(key=lambda row: row["average_score"], reverse=True)
    highest_student = student_rows[0]["student"] if student_rows else None
    lowest_student = student_rows[-1]["student"] if student_rows else None

    assignment_difficulty_qs = records_with_scores.values(
        "original_assignment_id", "assignment_title"
    ).annotate(avg_score=Avg("score"), attempts=Count("id")).order_by("avg_score")
    assignment_labels = [item["assignment_title"] for item in assignment_difficulty_qs]
    assignment_avg_scores = [round(float(item["avg_score"]), 2) for item in assignment_difficulty_qs]

    return {
        "summary": {
            "total_students": total_students,
            "total_assignments": total_assignments,
            "class_average_score": round(float(class_average_score), 2),
            "assignment_completion_rate": completion_rate,
            "highest_performing_student": highest_student,
            "lowest_performing_student": lowest_student,
        },
        "student_rows": student_rows,
        "charts": {
            "student_ranking_labels": ranking_labels,
            "student_ranking_values": ranking_values,
            "assignment_labels": assignment_labels,
            "assignment_avg_scores": assignment_avg_scores,
            "distribution_labels": ["High", "Medium", "Low"],
            "distribution_values": [
                distribution["High"],
                distribution["Medium"],
                distribution["Low"],
            ],
        },
    }
