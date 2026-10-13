import json
import os

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from openai import OpenAI

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "local-development-key-change-me")


def generate_questions(topic, count):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    prompt = f"""
Create exactly {count} multiple-choice quiz questions about: {topic}

Return a JSON object with a "questions" array. Each question must contain:
- "question": question text
- "options": exactly four distinct options
- "answer": exact text of the correct option
- "explanation": a brief explanation

The answer must exactly match one of the four options.
"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You create accurate educational quizzes."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("The AI returned an empty response.")

    data = json.loads(content)
    questions = data.get("questions")

    if not isinstance(questions, list) or len(questions) != count:
        raise ValueError("The AI returned an unexpected number of questions.")

    validated = []

    for item in questions:
        if not isinstance(item, dict):
            raise ValueError("The AI returned an invalid question.")

        question_text = str(item.get("question", "")).strip()
        raw_options = item.get("options", [])
        answer = str(item.get("answer", "")).strip()
        explanation = str(item.get("explanation", "")).strip()

        if not isinstance(raw_options, list) or len(raw_options) != 4:
            raise ValueError("Each question must have four options.")

        options = [str(option).strip() for option in raw_options]

        if (
            not question_text
            or any(not option for option in options)
            or len(set(options)) != 4
            or answer not in options
        ):
            raise ValueError("The AI returned an invalid question.")

        validated.append({
            "question": question_text,
            "options": options,
            "answer": answer,
            "explanation": explanation,
        })

    return validated


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "GET":
        return render_template("index.html")

    topic = request.form.get("topic", "").strip()

    try:
        count = int(request.form.get("count", "5"))
    except (TypeError, ValueError):
        count = 5

    if not topic:
        flash("Please enter a quiz topic.")
        return render_template("index.html")

    if len(topic) > 200:
        flash("The topic must be 200 characters or fewer.")
        return render_template("index.html")

    if count not in (5, 10):
        flash("Choose 5 or 10 questions.")
        return render_template("index.html")

    try:
        questions = generate_questions(topic, count)
    except Exception:
        app.logger.exception("Quiz generation failed")
        flash("Could not generate the quiz. Check the app settings and try again.")
        return render_template("index.html")

    session.clear()
    session["topic"] = topic
    session["questions"] = questions

    return redirect(url_for("quiz"))


@app.route("/quiz")
def quiz():
    questions = session.get("questions")

    if not isinstance(questions, list) or not questions:
        flash("Please generate a quiz first.")
        return redirect(url_for("home"))

    return render_template(
        "quiz.html",
        topic=session.get("topic", "Quiz"),
        questions=questions,
    )


@app.route("/submit", methods=["POST"])
def submit():
    questions = session.get("questions")

    if not isinstance(questions, list) or not questions:
        flash("Your quiz session expired. Please start a new quiz.")
        return redirect(url_for("home"))

    selected_answers = []

    for index, question in enumerate(questions):
        submitted = request.form.getlist(f"question_{index}")

        if len(submitted) != 1 or submitted[0] not in question.get("options", []):
            flash("Please choose one answer for every question.")
            return redirect(url_for("quiz"))

        selected_answers.append(submitted[0])

    results = []
    score = 0

    for question, selected in zip(questions, selected_answers):
        correct = selected == question["answer"]
        if correct:
            score += 1

        results.append({
            **question,
            "selected": selected,
            "correct": correct,
        })

    session["results"] = results
    session["score"] = score

    return redirect(url_for("result"))


@app.route("/result")
def result():
    results = session.get("results")

    if not isinstance(results, list):
        flash("Submit a quiz to see your results.")
        return redirect(url_for("home"))

    return render_template(
        "result.html",
        topic=session.get("topic", "Quiz"),
        results=results,
        score=session.get("score", 0),
    )


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1")
