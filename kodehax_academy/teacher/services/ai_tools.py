import re

import ollama


def generate_quiz(topic):

    prompt = f"""
You are generating a teacher-ready quiz.
Topic: {topic}

Requirements:
- Write exactly 5 multiple-choice questions.
- Difficulty: moderate.
- Each question must have 4 options: A, B, C, D.
- After all questions, provide a separate section named 'Answer Key'.
- Keep language concise and student-friendly.

Strict output format:
Q1. <question text>
A) ...
B) ...
C) ...
D) ...

Q2. ...

(continue until Q5)

Answer Key:
1) <option letter>
2) <option letter>
3) <option letter>
4) <option letter>
5) <option letter>
"""

    response = ollama.chat(
        model="llama3",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response["message"]["content"]


def generate_notes(topic):

    prompt = f"""
Create concise classroom lecture notes for: {topic}

Format with clear headings:
1. Overview
2. Core Concepts
3. Worked Example
4. Common Mistakes
5. Quick Recap

Rules:
- Use short paragraphs and bullet points where useful.
- Keep it practical for high-school/undergrad learners.
- End with 3 quick revision questions.
"""

    response = ollama.chat(
        model="llama3",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response["message"]["content"]


def strip_quiz_answers(quiz_text):

    if not quiz_text:
        return ""

    cleaned = re.split(r"(?im)^\s*answer\s*key\s*:?\s*$", quiz_text)[0]
    cleaned = re.sub(r"(?im)^\s*(correct\s*answer|answer)\s*[:\-].*$", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()
