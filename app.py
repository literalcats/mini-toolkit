"""Mini Toolkit - five small Python tools behind one Flask app (Render-ready)."""

import calendar
import hashlib
import hmac
import os
import secrets
from datetime import date, datetime

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# Used to sign the secret-number token. Set SECRET_KEY in Render env vars.
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me").encode()


# ---------- helpers ----------

class ValidationError(Exception):
    pass


@app.errorhandler(ValidationError)
def handle_validation(err):
    return jsonify(error=str(err)), 400


def body():
    return request.get_json(silent=True) or {}


def num(data, key, label, minimum=None, maximum=None):
    raw = data.get(key)
    if raw is None or str(raw).strip() == "":
        raise ValidationError(f"{label} is required.")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number.")
    if value != value or value in (float("inf"), float("-inf")):
        raise ValidationError(f"{label} must be a finite number.")
    if minimum is not None and value < minimum:
        raise ValidationError(f"{label} must be at least {minimum:g}.")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{label} must be at most {maximum:g}.")
    return value


def parse_date(raw, label):
    try:
        return datetime.strptime(str(raw), "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError(f"{label} must be a valid date (YYYY-MM-DD).")


# ---------- pages ----------

@app.get("/")
def index():
    return render_template("index.html")


# ---------- 1. age and days ----------

@app.post("/api/age")
def api_age():
    data = body()
    born = parse_date(data.get("birthdate"), "Birth date")
    today = parse_date(data["today"], "Today") if data.get("today") else date.today()
    if born > today:
        raise ValidationError("Birth date can't be in the future.")

    years = today.year - born.year
    months = today.month - born.month
    days = today.day - born.day
    if days < 0:
        months -= 1
        prev_month = today.month - 1 or 12
        prev_year = today.year if today.month > 1 else today.year - 1
        days += calendar.monthrange(prev_year, prev_month)[1]
    if months < 0:
        years -= 1
        months += 12

    def birthday_in(year):
        try:
            return born.replace(year=year)
        except ValueError:  # Feb 29 in a non-leap year
            return date(year, 2, 28)

    next_bd = birthday_in(today.year)
    if next_bd < today:
        next_bd = birthday_in(today.year + 1)

    total_days = (today - born).days
    return jsonify(
        years=years,
        months=months,
        days=days,
        total_days=total_days,
        total_weeks=total_days // 7,
        total_months=years * 12 + months,
        born_weekday=born.strftime("%A"),
        next_birthday=next_bd.isoformat(),
        days_to_birthday=(next_bd - today).days,
        is_birthday_today=(next_bd == today),
    )


# ---------- 2. electricity calculator ----------

@app.post("/api/electricity")
def api_electricity():
    data = body()
    rate = num(data, "rate", "Rate per kWh", 0, 10_000)
    appliances = data.get("appliances")
    if not isinstance(appliances, list) or not appliances:
        raise ValidationError("Add at least one appliance.")
    if len(appliances) > 50:
        raise ValidationError("Too many appliances (max 50).")

    rows, total_kwh_day = [], 0.0
    for i, item in enumerate(appliances, start=1):
        item = item if isinstance(item, dict) else {}
        name = str(item.get("name") or f"Appliance {i}")[:40]
        watts = num(item, "watts", f"{name}: watts", 0, 1_000_000)
        hours = num(item, "hours", f"{name}: hours per day", 0, 24)
        kwh_day = watts * hours / 1000
        total_kwh_day += kwh_day
        rows.append(dict(name=name, kwh_day=kwh_day, cost_day=kwh_day * rate))

    days = int(num(data, "days", "Days in billing period", 1, 366))
    return jsonify(
        rows=rows,
        kwh_day=total_kwh_day,
        cost_day=total_kwh_day * rate,
        kwh_period=total_kwh_day * days,
        cost_period=total_kwh_day * days * rate,
        cost_year=total_kwh_day * 365 * rate,
        days=days,
    )


# ---------- 3. grade boundary checker ----------

DEFAULT_BOUNDARIES = [("A", 90), ("B", 80), ("C", 70), ("D", 60), ("F", 0)]


@app.post("/api/grade")
def api_grade():
    data = body()
    max_score = num(data, "max_score", "Maximum score", 1, 100_000)
    score = num(data, "score", "Score", 0, max_score)

    raw = data.get("boundaries")
    if raw:
        bounds = []
        for b in raw:
            b = b if isinstance(b, dict) else {}
            grade = str(b.get("grade") or "").strip()[:4]
            if not grade:
                raise ValidationError("Every boundary needs a grade label.")
            bounds.append((grade, num(b, "min", f"Boundary for {grade}", 0, 100)))
    else:
        bounds = DEFAULT_BOUNDARIES
    bounds = sorted(bounds, key=lambda b: b[1], reverse=True)

    percent = score / max_score * 100
    grade, idx = None, None
    for i, (g, minimum) in enumerate(bounds):
        if percent >= minimum:
            grade, idx = g, i
            break
    if grade is None:
        grade = "Ungraded"

    to_next = None
    if idx is not None and idx > 0:
        next_grade, next_min = bounds[idx - 1]
        to_next = dict(
            grade=next_grade,
            points=round(max(next_min / 100 * max_score - score, 0), 2),
        )

    return jsonify(
        grade=grade,
        percent=round(percent, 2),
        to_next=to_next,
        boundaries=[dict(grade=g, min=m) for g, m in bounds],
    )


# ---------- 4. largest of three ----------

@app.post("/api/largest")
def api_largest():
    data = body()
    a, b, c = (num(data, k, f"Number {k.upper()}") for k in ("a", "b", "c"))
    largest = max(a, b, c)
    names = [n for n, v in (("A", a), ("B", b), ("C", c)) if v == largest]
    return jsonify(
        largest=largest,
        winners=names,
        tie=len(names) > 1,
        sorted=sorted([a, b, c], reverse=True),
    )


# ---------- 5. secret number (stateless, signed token) ----------
# The server keeps no state: the token holds a salted HMAC of the secret, so
# the browser can't read the number, and each guess is checked by the server.

def _digest(max_n, salt, n):
    msg = f"{max_n}:{salt}:{n}".encode()
    return hmac.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()


@app.post("/api/secret/new")
def api_secret_new():
    max_n = int(num(body(), "max", "Upper limit", 2, 10_000)) if body().get("max") else 100
    n = secrets.randbelow(max_n) + 1
    salt = secrets.token_hex(8)
    return jsonify(token=f"{max_n}.{salt}.{_digest(max_n, salt, n)}", max=max_n)


@app.post("/api/secret/guess")
def api_secret_guess():
    data = body()
    try:
        max_s, salt, digest = str(data.get("token", "")).split(".")
        max_n = int(max_s)
    except ValueError:
        raise ValidationError("Invalid game token. Start a new game.")
    if not 2 <= max_n <= 10_000:
        raise ValidationError("Invalid game token. Start a new game.")

    guess = int(num(data, "guess", "Guess", 1, max_n))

    secret = next(
        (n for n in range(1, max_n + 1) if hmac.compare_digest(_digest(max_n, salt, n), digest)),
        None,
    )
    if secret is None:
        raise ValidationError("Invalid game token. Start a new game.")

    if guess == secret:
        return jsonify(result="correct", secret=secret)
    return jsonify(result="higher" if guess < secret else "lower")


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
