from functools import wraps
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from app import db
from app.models import Department, Student, User

auth = Blueprint("auth", __name__)


def anonymous_only(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if current_user.is_authenticated:
            return redirect(url_for("main.select_department"))
        return view_func(*args, **kwargs)

    return wrapped


@auth.route("/")
def home():
    return render_template("landing.html")


@auth.route("/staff/register", methods=["GET", "POST"])
@anonymous_only
def staff_register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        if not full_name or not username or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("auth.staff_register"))

        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect(url_for("auth.staff_register"))

        user = User(role="staff", full_name=full_name, username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Staff account created. Please login.", "success")
        return redirect(url_for("auth.login", role="staff"))

    return render_template("auth/staff_register.html")


@auth.route("/student/register", methods=["GET", "POST"])
@anonymous_only
def student_register():
    departments = Department.query.order_by(Department.name).all()
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        roll_number = request.form.get("roll_number", "").strip().upper()
        phone_number = request.form.get("phone_number", "").strip()
        department_id = request.form.get("department_id", type=int)
        year = request.form.get("year", type=int)

        if not all([full_name, roll_number, phone_number, department_id, year]):
            flash("All fields are required.", "danger")
            return redirect(url_for("auth.student_register"))

        if User.query.filter_by(username=roll_number).first() or Student.query.filter_by(roll_number=roll_number).first():
            flash("Roll number is already registered.", "danger")
            return redirect(url_for("auth.student_register"))

        user = User(role="student", full_name=full_name, username=roll_number, department_id=department_id)
        user.set_password(phone_number)
        db.session.add(user)
        db.session.flush()

        student = Student(user_id=user.id, roll_number=roll_number, phone_number=phone_number, year=year)
        db.session.add(student)
        db.session.commit()
        flash("Student account created. Login with roll number and phone number.", "success")
        return redirect(url_for("auth.login", role="student"))

    return render_template("auth/student_register.html", departments=departments)


@auth.route("/login/<role>", methods=["GET", "POST"])
@anonymous_only
def login(role):
    if role not in ("student", "staff", "admin"):
        flash("Invalid role selected.", "danger")
        return redirect(url_for("auth.home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username, role=role).first()

        if not user or not user.check_password(password):
            flash("Invalid credentials.", "danger")
            return redirect(url_for("auth.login", role=role))

        login_user(user)
        flash("Login successful.", "success")
        if role == "student":
            return redirect(url_for("main.student_dashboard"))
        if role == "admin":
            return redirect(url_for("main.admin_dashboard"))
        return redirect(url_for("main.select_department"))

    return render_template("auth/login.html", role=role)


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("selected_department_id", None)
    flash("Logged out.", "info")
    return redirect(url_for("auth.home"))
