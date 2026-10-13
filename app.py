import os
import json
import random

from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "").strip()

if not app.secret_key:
    # Local-development fallback. Set SECRET_KEY in .env for your own project.
    app.secret_key = "local-development-only-change-this-secret-key"

API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
MODEL_NAME = os.getenv("OPENAI_MODEL", "").strip()

client = OpenAI(api_key=API_KEY) if API_KEY and OpenAI else None


# Built-in questions are used if AI is not configured or the API call fails.
SAMPLE_QUESTIONS = [
    {
        "question": "Which HTML element defines the main heading of a page?",
        "options": ["<head>", "<h1>", "<title>", "<header>"],
        "answer": "<h1>",
        "explanation": "The <h1> element represents the most important heading on a page."
    },
    {
        "question": "Which attribute specifies the destination URL of a hyperlink?",
        "options": ["src", "link", "href", "target"],
        "answer": "href",
        "explanation": "The href attribute contains the destination URL for an HTML link."
    },
    {
        "question": "Which HTML element is used to display an image?",
        "options": ["<image>", "<img>", "<picture-url>", "<src>"],
        "answer": "<img>",
        "explanation": "The <img> element embeds an image. Its src attribute identifies the image file."
    },
    {
        "question": "Which language is mainly used to style HTML pages?",
        "options": ["Python", "SQL", "CSS", "Java"],
        "answer": "CSS",
        "explanation": "CSS controls the appearance and layout of HTML elements."
    },
    {
        "question": "Which HTML element creates a paragraph?",
        "options": ["<para>", "<p>", "<text>", "<paragraph>"],
        "answer": "<p>",
        "explanation": "The <p> element defines a paragraph of text."
    },
    {
        "question": "Which tag creates an unordered list in HTML?",
        "options": ["<ol>", "<li>", "<ul>", "<list>"],
        "answer": "<ul>",
        "explanation": "The <ul> element creates an unordered, usually bulleted, list."
    },
    {
        "question": "Which attribute provides alternative text for an image?",
        "options": ["title", "alt", "name", "description"],
        "answer": "alt",
        "explanation": "The alt attribute provides alternative text for accessibility and when an image cannot load."
    },
    {
        "question": "Which tag is used to create a line break in HTML?",
        "options": ["<break>", "<lb>", "<br>", "<newline>"],
        "answer": "<br>",
        "explanation": "The <br> element inserts a line break."
    },
    {
        "question": "Which HTML element creates a numbered list?",
        "options": ["<ul>", "<ol>", "<dl>", "<li>"],
        "answer": "<ol>",
        "explanation": "The <ol> element creates an ordered, numbered list."
    },
    {
        "question": "Which tag sets the title shown in the browser tab?",
        "options": ["<meta>", "<head>", "<title>", "<h1>"],
        "answer": "<title>",
        "explanation": "The <title> element defines the document title shown in the browser tab."
    }
]


def clean_question(item):
    """Validate and standardize one question from AI output."""
    if not isinstance(item, dict):
        return None

    question_text = str(item.get("question", "")).strip()
    options = item.get("options", [])
    answer = str(item.get("answer", "")).strip()
    explanation = str(item.get("explanation", "")).strip()

    if not question_text or not isinstance(options, list):
        return None

    options = [str(option).strip() for option in options if str(option).strip()]
    if len(options) < 2 or not answer:
        return None

    # Match the answer to an option without case-sensitive formatting issues.
    matching_option = next(
        (option for option in options if option.casefold() == answer.casefold()),
        None
    )
    if matching_option is None:
        return None

    return {
        "question": question_text,
        "options": options,
        "answer": matching_option,
        "explanation": explanation or f"The correct answer is {matching_option}."
    }


def generate_ai_questions(topic, count):
    """Generate questions with the OpenAI API if configured."""
    if not client or not MODEL_NAME:
        raise RuntimeError(
            "AI is not configured. Add OPENAI_API_KEY and OPENAI_MODEL to .env."
        )

    prompt = f"""
Create exactly {count} multiple-choice quiz questions about: {topic}

Return only valid JSON in this format:
{{
  "questions": [
    {{
      "question": "Question text",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "answer": "Exact text of the correct option",
      "explanation": "A short explanation of why the answer is correct"
    }}
  ]
}}

Rules:
- Each question must have four options.
- The answer must exactly match one option.
- Explanations must be short and clear.
- Do not include Markdown fences or extra text.
"""

    response = client.responses.create(
        model=MODEL_NAME,
        input=prompt
    )

    output_text = response.output_text.strip()

    if output_text.startswith("```"):
        output_text = output_text.replace("```json", "", 1).replace("```", "").strip()

    data = json.loads(output_text)
    raw_questions = data.get("questions", []) if isinstance(data, dict) else []

    questions = []
    for item in raw_questions:
        cleaned = clean_question(item)
        if cleaned:
            questions.append(cleaned)
        if len(questions) >= count:
            break

    if not questions:
        raise ValueError("The AI did not return valid quiz questions.")

    return questions


@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    if request.method == "GET":
        return redirect(url_for("home"))

    topic = request.form.get("topic", "General Knowledge").strip()
    if not topic:
        flash("Please enter a quiz topic.")
        return redirect(url_for("home"))

    try:
        count = int(request.form.get("count", "5"))
    except (TypeError, ValueError):
        count = 5

    if count not in (5, 10):
        count = 5

    quiz_source = "AI-generated questions"

    try:
        questions = generate_ai_questions(topic, count)
        if len(questions) < count:
            raise ValueError("The AI returned too few questions.")
    except Exception as exc:
        app.logger.warning("AI question generation failed; using sample questions: %s", exc)
        questions = random.sample(SAMPLE_QUESTIONS, min(count, len(SAMPLE_QUESTIONS)))
        quiz_source = "Built-in sample questions"

    # Store answer keys server-side in the Flask session.
    session["active_quiz"] = {
        "topic": topic,
        "questions": questions,
        "quiz_source": quiz_source
    }

    public_questions = [
        {"question": q["question"], "options": q["options"]}
        for q in questions
    ]

    return render_template(
        "quiz.html",
        topic=topic,
        questions=public_questions,
        quiz_source=quiz_source
    )


@app.route("/submit", methods=["POST"])
def submit():
    active_quiz = session.get("active_quiz")

    if not active_quiz or not active_quiz.get("questions"):
        flash("Your quiz session has expired. Please start a new quiz.")
        return redirect(url_for("home"))

    questions = active_quiz["questions"]
    topic = active_quiz.get("topic", "Quiz")
    results = []
    score = 0

    for i, question in enumerate(questions):
        selected_answer = request.form.get(f"question_{i}", "").strip()
        correct_answer = question["answer"]
        is_correct = selected_answer == correct_answer

        if is_correct:
            score += 1

        results.append({
            "question": question["question"],
            "selected_answer": selected_answer,
            "correct_answer": correct_answer,
            "is_correct": is_correct,
            "explanation": question.get(
                "explanation",
                f"The correct answer is {correct_answer}."
            )
        })

    total = len(questions)
    percentage = round((score / total) * 100, 1) if total else 0

    # Keep results for the rendered response; clear the active quiz to prevent resubmission.
    session.pop("active_quiz", None)

    return render_template(
        "result.html",
        topic=topic,
        results=results,
        score=score,
        total=total,
        percentage=percentage
    )


@app.errorhandler(404)
def page_not_found(_error):
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
