import json
import os

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from openai import OpenAI

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "local-only-change-this-secret")

def generate_questions(topic, count):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("The OPENAI_API_KEY environment variable is not set.")

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    prompt = f"""
Create exactly {count} multiple-choice quiz questions about: {topic}

Return only a JSON object in this format:
{{
  "questions": [
    {{
      "question": "Question text",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "answer": "The exact text of the correct option",
      "explanation": "Brief explanation"
    }}
  ]
}}

Use four distinct options per question. Ensure the answer exactly matches one option.
"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You create accurate educational quizzes."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    data = json.loads(response.choices[0].message.content)
    questions = data.get("questions", [])

    if len(questions) != count:
        raise ValueError("The AI did not return the requested number of questions.")

    validated = []
    for item in questions:
        question = str(item.get("question", "")).strip()
        options = item.get("options", [])
        answer = str(item.get("answer", "")).strip()
        explanation = str(item.get("explanation", "")).strip()

        if (
            not question
            or not isinstance(options, list)
            or len(options) != 4
            or answer not in options
        ):
            raise ValueError("The AI returned an invalid question.")

        validated.append({
            "question": question,
            "options": [str(option) for option in options],
            "answer": answer,
            "explanation": explanation,
        })

    return validated


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        topic = request.form.get("topic", "").strip()

        try:
            count = int(request.form.get("count", "5"))
        except ValueError:
            count = 5

        if not topic:
            flash("Enter a quiz topic.")
            return render_template("index.html")

        if not 1 <= count <= 10:
            flash("Choose between 1 and 10 questions.")
            return render_template("index.html")

        try:
            questions = generate_questions(topic, count)
        except Exception:
            app.logger.exception("Quiz generation failed")
            flash("Could not generate the quiz. Check your API key and try again.")
            return render_template("index.html")

        session["topic"] = topic
        session["questions"] = questions
        session.pop("results", None)
        return redirect(url_for("quiz"))

    return render_template("index.html")


@app.route("/quiz")
def quiz():
    questions = session.get("questions")
    if not questions:
        return redirect(url_for("home"))
    return render_template(
        "quiz.html",
        topic=session.get("topic", "Quiz"),
        questions=questions,
    )


@app.route("/submit", methods=["POST"])
def submit():
    questions = session.get("questions")
    if not questions:
        return redirect(url_for("home"))

    results = []
    score = 0

    for index, question in enumerate(questions):
        selected = request.form.get(f"question_{index}", "")
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
    if results is None:
        return redirect(url_for("home"))

    return render_template(
        "result.html",
        topic=session.get("topic", "Quiz"),
        results=results,
        score=session.get("score", 0),
    )


if __name__ == "__main__":
    app.run(debug=True)
