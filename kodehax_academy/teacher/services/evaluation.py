from __future__ import annotations

import os
from typing import Any

import ollama

from teacher.models import Assignment, CodeSubmission, QuizAnswer, QuizResult, Submission


def clamp_score(score: float, max_score: float) -> float:
    if score < 0:
        return 0.0
    if score > max_score:
        return float(max_score)
    return float(score)


def parse_score(raw_score: Any, max_score: float) -> float:
    return clamp_score(float(raw_score), max_score)


def grade_file_submission_manual(submission: Submission, score: Any, feedback: str) -> Submission:
    submission.score = parse_score(score, submission.assignment.max_score)
    submission.ai_feedback = (feedback or "").strip()
    submission.save(update_fields=["score", "ai_feedback"])
    return submission


def grade_code_submission_manual(code_submission: CodeSubmission, score: Any, feedback: str) -> CodeSubmission:
    code_submission.score = parse_score(score, code_submission.assignment.max_score)
    code_submission.ai_feedback = (feedback or "").strip()
    code_submission.save(update_fields=["score", "ai_feedback"])
    return code_submission


def _read_text_file(file_path: str, char_limit: int = 6000) -> str:
    if not file_path or not os.path.exists(file_path):
        return ""
    _, ext = os.path.splitext(file_path.lower())
    if ext not in {".txt", ".md", ".py", ".csv", ".json", ".html", ".js", ".java", ".c", ".cpp"}:
        return ""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
            return handle.read(char_limit)
    except OSError:
        return ""


def _ai_grade(prompt: str, max_score: float) -> tuple[float, str]:
    try:
        response = ollama.chat(
            model="llama3",
            messages=[{"role": "user", "content": prompt}],
        )
        content = response["message"]["content"].strip()
    except Exception as exc:  # noqa: BLE001
        return 0.0, f"AI grading failed: {exc}"

    score_value = 0.0
    for token in content.replace("\n", " ").split():
        cleaned = token.strip().strip(",.;")
        try:
            score_value = float(cleaned)
            break
        except ValueError:
            continue
    score_value = clamp_score(score_value, max_score)
    return score_value, content


def grade_file_submission_ai(submission: Submission) -> Submission:
    file_text = _read_text_file(submission.file.path)
    prompt = (
        "You are grading a student file submission.\n"
        f"Assignment description:\n{submission.assignment.description}\n\n"
        f"Student username: {submission.student.username}\n"
        f"Max score: {submission.assignment.max_score}\n"
        "Return feedback with the score as the first numeric value.\n"
        "If file text is unavailable, still provide best-effort feedback.\n\n"
        f"Extracted file text:\n{file_text or '[Non-text file or empty extract]'}"
    )
    score, feedback = _ai_grade(prompt, submission.assignment.max_score)
    submission.score = score
    submission.ai_feedback = feedback
    submission.save(update_fields=["score", "ai_feedback"])
    return submission


def grade_code_submission_ai(code_submission: CodeSubmission) -> CodeSubmission:
    prompt = (
        "You are grading a coding submission.\n"
        f"Assignment description:\n{code_submission.assignment.description}\n\n"
        f"Language: {code_submission.language}\n"
        f"Max score: {code_submission.assignment.max_score}\n"
        "Score for correctness, logic, readability, and structure.\n"
        "Return feedback with the score as the first numeric value.\n\n"
        f"Student code:\n{code_submission.code}"
    )
    score, feedback = _ai_grade(prompt, code_submission.assignment.max_score)
    code_submission.score = score
    code_submission.ai_feedback = feedback
    code_submission.save(update_fields=["score", "ai_feedback"])
    return code_submission


def evaluate_quiz_for_student(assignment: Assignment, student) -> QuizResult:
    questions = assignment.quiz_questions.all()
    total_questions = questions.count()
    if total_questions == 0:
        result, _ = QuizResult.objects.update_or_create(
            assignment=assignment,
            student=student,
            defaults={
                "total_questions": 0,
                "correct_answers": 0,
                "score": 0,
                "feedback": "No questions configured.",
            },
        )
        return result

    answers = QuizAnswer.objects.filter(
        question__assignment=assignment,
        student=student,
    ).select_related("question")
    answer_map = {answer.question_id: answer.selected_option for answer in answers}

    correct_count = 0
    for question in questions:
        if answer_map.get(question.id) == question.correct_answer:
            correct_count += 1

    score = (correct_count / total_questions) * assignment.max_score
    feedback = f"Auto-graded quiz: {correct_count}/{total_questions} correct."
    result, _ = QuizResult.objects.update_or_create(
        assignment=assignment,
        student=student,
        defaults={
            "total_questions": total_questions,
            "correct_answers": correct_count,
            "score": round(score, 2),
            "feedback": feedback,
        },
    )
    return result


def evaluate_quiz_for_assignment(assignment: Assignment) -> int:
    student_ids = QuizAnswer.objects.filter(
        question__assignment=assignment
    ).values_list("student_id", flat=True).distinct()
    graded = 0
    for student_id in student_ids:
        student = assignment.classroom.students.filter(id=student_id).first()
        if student:
            evaluate_quiz_for_student(assignment, student)
            graded += 1
    return graded


def get_student_score_records(classroom, student):
    assignments = classroom.assignments.all().order_by("due_date")
    records = []
    graded_scores = []

    for assignment in assignments:
        score = None
        feedback = ""
        submitted_at = None

        if assignment.assignment_type == Assignment.ASSIGNMENT_TYPE_FILE:
            submission = Submission.objects.filter(assignment=assignment, student=student).first()
            if submission:
                score = submission.score
                feedback = submission.ai_feedback
                submitted_at = submission.submitted_at
        elif assignment.assignment_type == Assignment.ASSIGNMENT_TYPE_CODE:
            submission = CodeSubmission.objects.filter(assignment=assignment, student=student).first()
            if submission:
                score = submission.score
                feedback = submission.ai_feedback
                submitted_at = submission.submitted_at
        else:
            if QuizAnswer.objects.filter(question__assignment=assignment, student=student).exists():
                result = evaluate_quiz_for_student(assignment, student)
                score = result.score
                feedback = result.feedback
                submitted_at = result.evaluated_at

        records.append({
            "assignment": assignment,
            "score": score,
            "feedback": feedback,
            "submitted_at": submitted_at,
        })
        if score is not None:
            graded_scores.append(float(score))

    average_score = round(sum(graded_scores) / len(graded_scores), 2) if graded_scores else 0
    return records, average_score


def get_classroom_student_performance(classroom):
    rows = []
    for student in classroom.students.all():
        records, avg_score = get_student_score_records(classroom, student)
        submission_count = len([record for record in records if record["submitted_at"] is not None])
        rows.append({
            "student": student,
            "submissions": submission_count,
            "avg_score": avg_score if submission_count else "N/A",
        })
    return rows
