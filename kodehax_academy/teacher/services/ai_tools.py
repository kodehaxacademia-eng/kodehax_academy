import re

import google.generativeai as genai

from django.conf import settings

genai.configure(api_key=settings.GEMINI_API_KEY)


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

CRITICAL: Do NOT generate anything else other than these 5 multiple choice questions.
"""

    try:
        model = genai.GenerativeModel("gemini-flash-latest")
        response = model.generate_content(prompt)
        return response.text
    except Exception as exc:
        print(f"Error generating quiz: {exc}")
        return ""


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

    try:
        model = genai.GenerativeModel("gemini-flash-latest")
        response = model.generate_content(prompt)
        return response.text
    except Exception as exc:
        print(f"Error generating notes: {exc}")
        return ""


def strip_quiz_answers(quiz_text):

    if not quiz_text:
        return ""

    cleaned = re.split(r"(?im)^\s*answer\s*key\s*:?\s*$", quiz_text)[0]
    cleaned = re.sub(r"(?im)^\s*(correct\s*answer|answer)\s*[:\-].*$", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


def generate_coding_assignment(topic):

    prompt = f"""
You are creating a standalone coding assignment for students.
Topic: {topic}

Requirements:
- Create coding problems based strictly on the topic above.
- If the topic asks for multiple problems (e.g., "3 DSA questions"), you MUST separate each problem strictly using the heading "### Problem X:" (where X is the number 1, 2, 3...).
- The assignment must include three clear sub-headings for EACH problem:
  1. Problem Statement
  2. Requirements (bullet points regarding inputs, outputs, constraints)
  3. Examples (Input & Output formats)

Format rules:
- Format the output using clear Markdown.
- Keep the language completely concise and focused.
- Do NOT provide the implementation or solution code to the problem.

CRITICAL: Provide ONLY the coding problem details. Do NOT output MCQs or notes.
"""

    try:
        model = genai.GenerativeModel("gemini-flash-latest")
        response = model.generate_content(prompt)
        return response.text
    except Exception as exc:
        print(f"Error generating coding assignment: {exc}")
        return ""
