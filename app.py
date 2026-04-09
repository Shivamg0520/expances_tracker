import os
import io
import csv
import base64
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

import matplotlib
matplotlib.use("Agg")  # Render charts without a GUI (works on servers too).
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from flask import Flask, Response, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from plotly.io import to_html
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)


def get_database_uri() -> str:
    """Production: PostgreSQL via DATABASE_URL (Render/Railway etc.). Local: SQLite."""
    uri = os.environ.get("DATABASE_URL")
    if uri:
        # Render/Heroku sometimes give postgres:// — SQLAlchemy expects postgresql://
        if uri.startswith("postgres://"):
            uri = uri.replace("postgres://", "postgresql://", 1)
        return uri
    return "sqlite:///expenses.db"


# Production: set FLASK_SECRET_KEY and DATABASE_URL in the host dashboard.
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = get_database_uri()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    expenses = db.relationship("Expense", backref="user", lazy=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    category = db.Column(db.String(60), nullable=False, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)


@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))


@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not username or not password:
            flash("Username aur password required hai.", "error")
            return redirect(url_for("register"))

        if User.query.filter_by(username=username).first():
            flash("Username already exist karta hai.", "error")
            return redirect(url_for("register"))

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash("Account successfully create hua.", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            flash("Invalid username/password.", "error")
            return redirect(url_for("login"))

        login_user(user)
        flash("Login successful.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logout successful.", "success")
    return redirect(url_for("login"))


def _parse_date(date_str: str):
    # expects YYYY-MM-DD from <input type="date" />
    return datetime.strptime(date_str, "%Y-%m-%d").date()


@app.route("/add_expense", methods=["POST"])
@login_required
def add_expense():
    category = (request.form.get("category") or "").strip()
    amount_str = (request.form.get("amount") or "").strip()
    date_str = (request.form.get("date") or "").strip()

    if not category or not amount_str or not date_str:
        flash("Category, amount aur date required hai.", "error")
        return redirect(url_for("dashboard"))

    try:
        amount = Decimal(amount_str)
        if amount <= 0:
            raise ValueError("Amount must be > 0")
    except Exception:
        flash("Amount valid number (positive) hona chahiye.", "error")
        return redirect(url_for("dashboard"))

    try:
        exp_date = _parse_date(date_str)
    except Exception:
        flash("Date format YYYY-MM-DD hona chahiye.", "error")
        return redirect(url_for("dashboard"))

    exp = Expense(
        user_id=current_user.id,
        category=category,
        amount=amount,
        date=exp_date,
    )
    db.session.add(exp)
    db.session.commit()

    flash("Expense added.", "success")
    return redirect(url_for("dashboard"))


@app.route("/export")
@login_required
def export_csv():
    expenses = (
        Expense.query.filter_by(user_id=current_user.id)
        .order_by(Expense.date.desc(), Expense.id.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["category", "amount", "date"])

    for exp in expenses:
        writer.writerow([exp.category, str(exp.amount), exp.date.isoformat()])

    csv_data = output.getvalue()
    output.close()

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=expenses.csv"
        },
    )


@app.route("/dashboard")
@login_required
def dashboard():
    expenses = (
        Expense.query.filter_by(user_id=current_user.id)
        .order_by(Expense.date.desc(), Expense.id.desc())
        .all()
    )

    # Build charts only when we have data.
    totals_by_category = defaultdict(Decimal)
    month_totals = defaultdict(Decimal)

    for exp in expenses:
        totals_by_category[exp.category] += Decimal(exp.amount)
        month_key = exp.date.replace(day=1)
        month_totals[month_key] += Decimal(exp.amount)

    pie_div = ""
    bar_div = ""
    pie_img = ""
    bar_img = ""

    if totals_by_category:
        categories = list(totals_by_category.keys())
        category_values = [float(totals_by_category[c]) for c in categories]

        pie_fig = go.Figure(
            data=[
                go.Pie(
                    labels=categories,
                    values=category_values,
                    hole=0.35,
                )
            ]
        )
        pie_fig.update_layout(title="Spending by Category")
        pie_div = to_html(pie_fig, full_html=False, include_plotlyjs=False)

        # Matplotlib PNG (embedded via base64).
        fig, ax = plt.subplots()
        ax.pie(category_values, labels=categories, autopct="%1.1f%%", startangle=90)
        ax.axis("equal")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        pie_img = base64.b64encode(buf.read()).decode("utf-8")

    if month_totals:
        month_keys = sorted(month_totals.keys())
        x_labels = [d.strftime("%b %Y") for d in month_keys]
        y_values = [float(month_totals[d]) for d in month_keys]

        bar_fig = go.Figure(data=[go.Bar(x=x_labels, y=y_values)])
        bar_fig.update_layout(
            title="Monthly Spending",
            xaxis_title="Month",
            yaxis_title="Amount",
        )
        bar_div = to_html(bar_fig, full_html=False, include_plotlyjs=False)

        # Matplotlib PNG (embedded via base64).
        fig, ax = plt.subplots(figsize=(9, 4.8))
        ax.bar(x_labels, y_values)
        ax.set_title("Monthly Spending")
        ax.set_xlabel("Month")
        ax.set_ylabel("Amount")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        bar_img = base64.b64encode(buf.read()).decode("utf-8")

    grand_total = float(sum(Decimal(e.amount) for e in expenses)) if expenses else 0.0

    return render_template(
        "dashboard.html",
        expenses=expenses,
        grand_total=grand_total,
        pie_div=pie_div,
        bar_div=bar_div,
        pie_img=pie_img,
        bar_img=bar_img,
    )


def init_db():
    # Creates tables on first run. Needed for gunicorn too (__main__ does not run).
    with app.app_context():
        db.create_all()


init_db()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)

