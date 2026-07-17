from collections import defaultdict
from functools import wraps
import os
from uuid import uuid4
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from app import db
from app.models import (
    BroadcastNotification,
    Department,
    Feedback,
    Mark,
    News,
    Notification,
    Semester,
    Student,
    SubjectTemplate,
    User,
)

main = Blueprint("main", __name__)


YEAR_LABEL = {1: "First Year", 2: "Second Year", 3: "Final Year"}
EXAM_LABELS = {
    "first_internal": "First Internal",
    "second_internal": "Second Internal",
    "model_exam": "Model Exam",
    "university_exam": "University Exam",
}
FEEDBACK_EXAM_LABELS = {
    "first_internal": "First Internal",
    "second_internal": "Second Internal",
}
NEWS_CATEGORIES = {
    "general": "General News",
    "announcement": "Announcement",
    "timetable": "Timetable",
    "event": "Event",
}
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_PDF_EXTENSIONS = {"pdf"}


def role_required(role):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != role:
                flash("Access denied.", "danger")
                return redirect(url_for("auth.home"))
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


def year_for_semester(semester_number):
    if semester_number in (1, 2):
        return 1
    if semester_number in (3, 4):
        return 2
    return 3


def selected_department():
    dept_id = session.get("selected_department_id")
    if not dept_id:
        return None
    return Department.query.get(dept_id)


def semester_templates_for_department(department_id, semester):
    return (
        SubjectTemplate.query.filter_by(
            department_id=department_id,
            year=year_for_semester(semester.number),
            semester_id=semester.id,
        )
        .order_by(SubjectTemplate.id)
        .all()
    )


def ordered_marks_for_semester(student_id, semester_id, templates):
    marks = Mark.query.filter_by(student_id=student_id, semester_id=semester_id).all()
    marks_by_subject = {mark.subject_name: mark for mark in marks}
    template_subjects = [template.subject_name for template in templates]

    ordered = []
    for subject_name in template_subjects:
        mark = marks_by_subject.get(subject_name)
        if mark:
            ordered.append(mark)

    extras = [mark for mark in marks if mark.subject_name not in template_subjects]
    extras.sort(key=lambda item: item.id)
    ordered.extend(extras)
    return ordered


def ensure_default_marks(student, semester, department_id):
    templates = semester_templates_for_department(department_id, semester)
    if not templates:
        return templates, ordered_marks_for_semester(student.id, semester.id, templates)

    existing_subjects = {
        mark.subject_name for mark in Mark.query.filter_by(student_id=student.id, semester_id=semester.id).all()
    }

    created_any = False
    for template in templates:
        if template.subject_name in existing_subjects:
            continue
        db.session.add(
            Mark(
                student_id=student.id,
                semester_id=semester.id,
                subject_name=template.subject_name,
            )
        )
        created_any = True

    if created_any:
        db.session.commit()

    return templates, ordered_marks_for_semester(student.id, semester.id, templates)


def compute_semester_metrics(marks):
    if not marks:
        return {"percentage": 0.0, "sgpa": 0.0}
    subject_totals = [m.subject_average for m in marks]
    percentage = round(sum(subject_totals) / len(subject_totals), 2)
    sgpa = round(min(10.0, percentage / 10.0), 2)
    return {"percentage": percentage, "sgpa": sgpa}


def compute_overall_cgpa(semester_stats):
    populated = [s["sgpa"] for s in semester_stats.values() if s["sgpa"] > 0]
    if not populated:
        return 0.0
    return round(sum(populated) / len(populated), 2)


def compute_exam_summary(marks, exam_type):
    total = round(sum(getattr(mark, exam_type) for mark in marks), 2)
    max_total = float(len(marks) * 100)
    percentage = round((total / max_total) * 100, 2) if max_total > 0 else 0.0
    return {"total": total, "max_total": max_total, "percentage": percentage}


def build_exam_breakdown(marks):
    data = {}
    for exam_type, label in EXAM_LABELS.items():
        metrics = compute_exam_summary(marks, exam_type)
        data[exam_type] = {"label": label, **metrics}
    return data


def build_student_academic_context(student_id):
    semester_marks = defaultdict(list)
    student = Student.query.get_or_404(student_id)
    department_id = student.user.department_id

    for sem_number in range(1, 7):
        semester = Semester.query.filter_by(number=sem_number).first()
        if not semester:
            semester_marks[sem_number] = []
            continue
        templates = semester_templates_for_department(department_id, semester)
        semester_marks[sem_number] = ordered_marks_for_semester(student_id, semester.id, templates)

    stats = {}
    exam_breakdown = {}
    for sem_number in range(1, 7):
        sem_marks = semester_marks[sem_number]
        stats[sem_number] = compute_semester_metrics(sem_marks)
        exam_breakdown[sem_number] = build_exam_breakdown(sem_marks)

    feedback_by_semester = defaultdict(list)
    feedback_entries = Feedback.query.filter_by(student_id=student_id).order_by(Feedback.created_at.desc()).all()
    for entry in feedback_entries:
        feedback_by_semester[entry.semester.number].append(entry)

    return semester_marks, stats, exam_breakdown, feedback_by_semester


def performance_suggestion(percentages):
    populated = [p for p in percentages if p > 0]
    if not populated:
        return "No marks available yet. Start strong this semester."
    if len(populated) == 1:
        return "Good start. Keep your consistency in upcoming semesters."

    latest = populated[-1]
    previous = populated[-2]
    average = round(sum(populated) / len(populated), 2)

    if latest >= previous and latest >= 75:
        return "Keep it up. Your performance trend is improving."
    if latest < previous and latest < 60:
        return "Improve your performance. Focus on weak subjects and revise daily."
    if average >= 70:
        return "You are performing well overall. Aim for steady growth."
    return "You can do better. Increase practice and maintain regular preparation."


def _save_uploaded_file(file_obj, folder_name, allowed_extensions):
    if not file_obj or not file_obj.filename:
        return None

    filename = secure_filename(file_obj.filename)
    if "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in allowed_extensions:
        return None

    unique_name = f"{uuid4().hex}.{ext}"
    target_dir = os.path.join(current_app.root_path, "static", "uploads", "news", folder_name)
    os.makedirs(target_dir, exist_ok=True)
    file_obj.save(os.path.join(target_dir, unique_name))
    return unique_name


def create_role_notifications(title, message, news_id=None):
    db.session.add(
        BroadcastNotification(
            recipient_role="staff",
            title=title,
            message=message,
            news_id=news_id,
        )
    )
    db.session.add(
        BroadcastNotification(
            recipient_role="student",
            title=title,
            message=message,
            news_id=news_id,
        )
    )


@main.route("/select-department", methods=["GET", "POST"])
@login_required
def select_department():
    if current_user.role == "student":
        return redirect(url_for("main.student_dashboard"))
    if current_user.role == "admin":
        return redirect(url_for("main.admin_dashboard"))

    departments = Department.query.order_by(Department.name).all()

    if request.method == "POST":
        department_id = request.form.get("department_id", type=int)
        department = Department.query.get(department_id)
        if not department:
            flash("Please select a valid department.", "danger")
            return redirect(url_for("main.select_department"))

        session["selected_department_id"] = department.id
        return redirect(url_for("main.staff_dashboard"))

    return render_template("select_department.html", departments=departments)


@main.route("/staff/dashboard")
@login_required
@role_required("staff")
def staff_dashboard():
    department = selected_department()
    if not department:
        return redirect(url_for("main.select_department"))

    year = request.args.get("year", default=1, type=int)
    students = (
        Student.query.join(User)
        .filter(User.department_id == department.id, Student.year == year)
        .order_by(Student.roll_number)
        .all()
    )
    role_notifications = (
        BroadcastNotification.query.filter_by(recipient_role="staff")
        .order_by(BroadcastNotification.created_at.desc())
        .limit(8)
        .all()
    )
    news_items = News.query.order_by(News.created_at.desc()).limit(6).all()

    return render_template(
        "staff/dashboard.html",
        department=department,
        year=year,
        students=students,
        role_notifications=role_notifications,
        news_items=news_items,
        year_label=YEAR_LABEL,
        exam_labels=EXAM_LABELS,
    )


@main.route("/staff/results", methods=["GET", "POST"])
@login_required
@role_required("staff")
def staff_results_lookup():
    department = selected_department()
    if not department:
        return redirect(url_for("main.select_department"))

    if request.method == "POST":
        roll_number = request.form.get("roll_number", "").strip().upper()
        semester_number = request.form.get("semester", type=int)
        exam_type = request.form.get("exam_type", "first_internal").strip()
        return redirect(
            url_for(
                "main.staff_results_lookup",
                roll_number=roll_number,
                semester=semester_number,
                exam_type=exam_type,
            )
        )

    roll_number = request.args.get("roll_number", "").strip().upper()
    semester_number = request.args.get("semester", default=1, type=int)
    exam_type = request.args.get("exam_type", default="first_internal", type=str)
    exam_type = exam_type if exam_type in EXAM_LABELS else "first_internal"

    student = None
    semester = Semester.query.filter_by(number=semester_number).first()
    marks = []
    summary = {"total": 0.0, "max_total": 0.0, "percentage": 0.0}

    if roll_number and semester:
        student = (
            Student.query.join(User)
            .filter(Student.roll_number == roll_number, User.department_id == department.id)
            .first()
        )
        if student:
            templates = semester_templates_for_department(department.id, semester)
            marks = ordered_marks_for_semester(student.id, semester.id, templates)
            summary = compute_exam_summary(marks, exam_type)
        else:
            flash("Student not found in selected department.", "warning")

    return render_template(
        "staff/results_lookup.html",
        department=department,
        roll_number=roll_number,
        semester_number=semester_number,
        exam_type=exam_type,
        exam_labels=EXAM_LABELS,
        student=student,
        semester=semester,
        marks=marks,
        summary=summary,
    )


@main.route("/staff/students-marks")
@login_required
@role_required("staff")
def staff_students_marks():
    department = selected_department()
    if not department:
        return redirect(url_for("main.select_department"))

    year = request.args.get("year", default=1, type=int)
    semester_number = request.args.get("semester", default=1, type=int)
    exam_type = request.args.get("exam_type", default="first_internal", type=str)
    exam_type = exam_type if exam_type in EXAM_LABELS else "first_internal"

    semester = Semester.query.filter_by(number=semester_number).first_or_404()
    students = (
        Student.query.join(User)
        .filter(User.department_id == department.id, Student.year == year)
        .order_by(Student.roll_number)
        .all()
    )

    rows = []
    for student in students:
        templates = semester_templates_for_department(department.id, semester)
        marks = ordered_marks_for_semester(student.id, semester.id, templates)
        exam_summary = compute_exam_summary(marks, exam_type)
        rows.append(
            {
                "student": student,
                "subject_count": len(marks),
                "total": exam_summary["total"],
                "max_total": exam_summary["max_total"],
                "percentage": exam_summary["percentage"],
            }
        )

    return render_template(
        "staff/students_marks.html",
        department=department,
        year=year,
        semester=semester,
        exam_type=exam_type,
        exam_labels=EXAM_LABELS,
        year_label=YEAR_LABEL,
        rows=rows,
    )


@main.route("/staff/news")
@login_required
@role_required("staff")
def staff_news():
    department = selected_department()
    if not department:
        return redirect(url_for("main.select_department"))

    news_items = News.query.order_by(News.created_at.desc()).all()
    role_notifications = (
        BroadcastNotification.query.filter_by(recipient_role="staff")
        .order_by(BroadcastNotification.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template(
        "staff/news.html",
        department=department,
        news_items=news_items,
        role_notifications=role_notifications,
        news_categories=NEWS_CATEGORIES,
    )


@main.route("/staff/student/new", methods=["GET", "POST"])
@login_required
@role_required("staff")
def add_student():
    department = selected_department()
    if not department:
        return redirect(url_for("main.select_department"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        roll_number = request.form.get("roll_number", "").strip().upper()
        phone_number = request.form.get("phone_number", "").strip()
        year = request.form.get("year", type=int)

        if not all([full_name, roll_number, phone_number, year]):
            flash("All fields are mandatory.", "danger")
            return redirect(url_for("main.add_student"))

        if User.query.filter_by(username=roll_number).first():
            flash("Roll number already exists.", "danger")
            return redirect(url_for("main.add_student"))

        user = User(
            role="student",
            full_name=full_name,
            username=roll_number,
            department_id=department.id,
        )
        user.set_password(phone_number)
        db.session.add(user)
        db.session.flush()

        student = Student(
            user_id=user.id,
            roll_number=roll_number,
            phone_number=phone_number,
            year=year,
        )
        db.session.add(student)
        db.session.commit()
        flash("Student created successfully.", "success")
        return redirect(url_for("main.staff_dashboard", year=year))

    return render_template("staff/student_form.html", mode="create", student=None)


@main.route("/staff/student/<int:student_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("staff")
def edit_student(student_id):
    department = selected_department()
    if not department:
        return redirect(url_for("main.select_department"))

    student = Student.query.join(User).filter(Student.id == student_id, User.department_id == department.id).first_or_404()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone_number = request.form.get("phone_number", "").strip()
        year = request.form.get("year", type=int)

        student.user.full_name = full_name
        student.phone_number = phone_number
        student.year = year
        student.user.set_password(phone_number)
        db.session.commit()
        flash("Student updated.", "success")
        return redirect(url_for("main.staff_dashboard", year=year))

    return render_template("staff/student_form.html", mode="edit", student=student)


@main.route("/staff/student/<int:student_id>/delete", methods=["POST"])
@login_required
@role_required("staff")
def delete_student(student_id):
    department = selected_department()
    if not department:
        return redirect(url_for("main.select_department"))

    student = Student.query.join(User).filter(Student.id == student_id, User.department_id == department.id).first_or_404()
    year = student.year
    user = student.user
    db.session.delete(student)
    db.session.delete(user)
    db.session.commit()
    flash("Student removed.", "info")
    return redirect(url_for("main.staff_dashboard", year=year))


@main.route("/staff/student/<int:student_id>/marks", methods=["GET", "POST"])
@login_required
@role_required("staff")
def manage_marks(student_id):
    semester_number = request.args.get("semester", default=1, type=int)
    return redirect(url_for("main.staff_student_details", student_id=student_id, semester=semester_number))


@main.route("/staff/student-details")
@login_required
@role_required("staff")
def staff_student_details_list():
    department = selected_department()
    if not department:
        return redirect(url_for("main.select_department"))

    year = request.args.get("year", default=1, type=int)
    students = (
        Student.query.join(User)
        .filter(User.department_id == department.id, Student.year == year)
        .order_by(Student.roll_number)
        .all()
    )

    return render_template(
        "staff/student_details_list.html",
        department=department,
        students=students,
        year=year,
        year_label=YEAR_LABEL,
    )


@main.route("/staff/student/<int:student_id>/details", methods=["GET", "POST"])
@login_required
@role_required("staff")
def staff_student_details(student_id):
    department = selected_department()
    if not department:
        return redirect(url_for("main.select_department"))

    student = Student.query.join(User).filter(Student.id == student_id, User.department_id == department.id).first_or_404()
    semester_number = request.args.get("semester", default=1, type=int)
    semester = Semester.query.filter_by(number=semester_number).first_or_404()

    if request.method == "POST":
        mark_ids = request.form.getlist("mark_id")
        for mark_id in mark_ids:
            mark = Mark.query.filter_by(id=int(mark_id), student_id=student.id, semester_id=semester.id).first_or_404()
            old_values = {field: getattr(mark, field) for field in EXAM_LABELS}

            first_internal = request.form.get(f"first_internal_{mark.id}", type=float)
            second_internal = request.form.get(f"second_internal_{mark.id}", type=float)
            model_exam = request.form.get(f"model_exam_{mark.id}", type=float)
            university_exam = request.form.get(f"university_exam_{mark.id}", type=float)

            for value in [first_internal, second_internal, model_exam, university_exam]:
                if value is None or value < 0 or value > 100:
                    flash("Marks must be between 0 and 100.", "danger")
                    return redirect(url_for("main.staff_student_details", student_id=student_id, semester=semester_number))

            mark.first_internal = first_internal
            mark.second_internal = second_internal
            mark.model_exam = model_exam
            mark.university_exam = university_exam

            changed_exams = []
            for field, label in EXAM_LABELS.items():
                if float(old_values[field]) != float(getattr(mark, field)):
                    changed_exams.append(label)

            if changed_exams:
                labels = ", ".join(changed_exams)
                db.session.add(
                    Notification(
                        student_id=student.id,
                        semester_id=semester.id,
                        exam_type="first_internal",
                        title="Marks Updated",
                        message=f"{labels} marks updated for Semester {semester.number} ({mark.subject_name}).",
                    )
                )

        db.session.commit()
        flash("Marks saved in semester subject order.", "success")
        return redirect(url_for("main.staff_student_details", student_id=student_id, semester=semester_number))

    templates, marks = ensure_default_marks(student, semester, department.id)
    has_subject_templates = len(templates) > 0
    metrics = compute_semester_metrics(marks)
    exam_breakdown = build_exam_breakdown(marks)

    return render_template(
        "staff/student_details.html",
        department=department,
        student=student,
        semester=semester,
        marks=marks,
        metrics=metrics,
        exam_breakdown=exam_breakdown,
        has_subject_templates=has_subject_templates,
    )


@main.route("/staff/subjects", methods=["GET", "POST"])
@login_required
@role_required("staff")
def staff_subjects():
    department = selected_department()
    if not department:
        return redirect(url_for("main.select_department"))

    semester_number = request.args.get("semester", default=1, type=int)
    semester = Semester.query.filter_by(number=semester_number).first_or_404()

    if request.method == "POST":
        subject_name = request.form.get("subject_name", "").strip()
        post_semester_number = request.form.get("semester_number", type=int)
        post_semester = Semester.query.filter_by(number=post_semester_number).first_or_404()
        post_year = year_for_semester(post_semester.number)

        if not subject_name:
            flash("Subject name is required.", "danger")
            return redirect(url_for("main.staff_subjects", semester=post_semester.number))

        existing = SubjectTemplate.query.filter_by(
            department_id=department.id,
            year=post_year,
            semester_id=post_semester.id,
            subject_name=subject_name,
        ).first()
        if existing:
            flash("Subject already exists for this semester.", "warning")
            return redirect(url_for("main.staff_subjects", semester=post_semester.number))

        db.session.add(
            SubjectTemplate(
                department_id=department.id,
                year=post_year,
                semester_id=post_semester.id,
                subject_name=subject_name,
            )
        )
        db.session.commit()
        flash(f"Added subject to Semester {post_semester.number}.", "success")
        return redirect(url_for("main.staff_subjects", semester=post_semester.number))

    semester_templates = {}
    for sem_number in range(1, 7):
        sem = Semester.query.filter_by(number=sem_number).first()
        sem_year = year_for_semester(sem_number)
        semester_templates[sem_number] = (
            SubjectTemplate.query.filter_by(
                department_id=department.id,
                year=sem_year,
                semester_id=sem.id,
            )
            .order_by(SubjectTemplate.id)
            .all()
        )

    return render_template(
        "staff/subjects.html",
        department=department,
        semester=semester,
        semester_templates=semester_templates,
        year_label=YEAR_LABEL,
        year_for_semester=year_for_semester,
    )


@main.route("/staff/subjects/<int:template_id>/delete", methods=["POST"])
@login_required
@role_required("staff")
def delete_subject_template(template_id):
    department = selected_department()
    if not department:
        return redirect(url_for("main.select_department"))

    template = SubjectTemplate.query.filter_by(id=template_id, department_id=department.id).first_or_404()
    semester_number = template.semester.number
    db.session.delete(template)
    db.session.commit()
    flash("Subject removed from semester.", "info")
    return redirect(url_for("main.staff_subjects", semester=semester_number))


@main.route("/staff/student/<int:student_id>/marks/<int:mark_id>/delete", methods=["POST"])
@login_required
@role_required("staff")
def delete_mark(student_id, mark_id):
    department = selected_department()
    if not department:
        return redirect(url_for("main.select_department"))

    student = Student.query.join(User).filter(Student.id == student_id, User.department_id == department.id).first_or_404()
    mark = Mark.query.filter_by(id=mark_id, student_id=student.id).first_or_404()
    semester = mark.semester.number
    db.session.delete(mark)
    db.session.commit()
    flash("Mark entry deleted.", "info")
    return redirect(url_for("main.manage_marks", student_id=student.id, semester=semester))


@main.route("/student/dashboard")
@login_required
@role_required("student")
def student_dashboard():
    student = Student.query.filter_by(user_id=current_user.id).first_or_404()
    _, stats, _, _ = build_student_academic_context(student.id)

    notifications = Notification.query.filter_by(student_id=student.id).order_by(Notification.created_at.desc()).limit(20).all()
    unread_count = Notification.query.filter_by(student_id=student.id, is_read=False).count()
    role_notifications = (
        BroadcastNotification.query.filter_by(recipient_role="student")
        .order_by(BroadcastNotification.created_at.desc())
        .limit(20)
        .all()
    )
    news_items = News.query.order_by(News.created_at.desc()).limit(8).all()

    cgpa = compute_overall_cgpa(stats)

    return render_template(
        "student/dashboard.html",
        student=student,
        stats=stats,
        notifications=notifications,
        role_notifications=role_notifications,
        news_items=news_items,
        unread_count=unread_count,
        cgpa=cgpa,
    )


@main.route("/student/marks")
@login_required
@role_required("student")
def student_marks():
    student = Student.query.filter_by(user_id=current_user.id).first_or_404()
    department_id = student.user.department_id
    for sem_number in range(1, 7):
        semester = Semester.query.filter_by(number=sem_number).first()
        if semester:
            ensure_default_marks(student, semester, department_id)
    semester_marks, stats, exam_breakdown, feedback_by_semester = build_student_academic_context(student.id)

    return render_template(
        "student/marks.html",
        student=student,
        semester_marks=semester_marks,
        stats=stats,
        exam_breakdown=exam_breakdown,
        feedback_by_semester=feedback_by_semester,
        feedback_exam_labels=FEEDBACK_EXAM_LABELS,
    )


@main.route("/student/performance")
@login_required
@role_required("student")
def student_performance():
    student = Student.query.filter_by(user_id=current_user.id).first_or_404()
    _, stats, _, _ = build_student_academic_context(student.id)

    labels = [f"Semester {sem}" for sem in range(1, 7)]
    percentages = [stats[sem]["percentage"] for sem in range(1, 7)]
    suggestion = performance_suggestion(percentages)

    return render_template(
        "student/performance.html",
        student=student,
        labels=labels,
        percentages=percentages,
        suggestion=suggestion,
    )


@main.route("/student/notifications/read", methods=["POST"])
@login_required
@role_required("student")
def mark_notifications_read():
    student = Student.query.filter_by(user_id=current_user.id).first_or_404()
    Notification.query.filter_by(student_id=student.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return redirect(url_for("main.student_dashboard"))


@main.route("/student/news")
@login_required
@role_required("student")
def student_news():
    student = Student.query.filter_by(user_id=current_user.id).first_or_404()
    news_items = News.query.order_by(News.created_at.desc()).all()
    role_notifications = (
        BroadcastNotification.query.filter_by(recipient_role="student")
        .order_by(BroadcastNotification.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template(
        "student/news.html",
        student=student,
        news_items=news_items,
        role_notifications=role_notifications,
        news_categories=NEWS_CATEGORIES,
    )


@main.route("/admin/news", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_news():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "general").strip()
        content = request.form.get("content", "").strip()
        image_file = request.files.get("image_file")
        pdf_file = request.files.get("pdf_file")

        if not title or not content:
            flash("Title and content are required.", "danger")
            return redirect(url_for("main.admin_news"))

        if category not in NEWS_CATEGORIES:
            flash("Invalid news category.", "danger")
            return redirect(url_for("main.admin_news"))

        image_filename = None
        pdf_filename = None
        if image_file and image_file.filename:
            image_filename = _save_uploaded_file(image_file, "images", ALLOWED_IMAGE_EXTENSIONS)
            if not image_filename:
                flash("Invalid image format. Use JPG, JPEG, PNG, or WEBP.", "danger")
                return redirect(url_for("main.admin_news"))

        if pdf_file and pdf_file.filename:
            pdf_filename = _save_uploaded_file(pdf_file, "pdfs", ALLOWED_PDF_EXTENSIONS)
            if not pdf_filename:
                flash("Invalid PDF format. Upload a .pdf file.", "danger")
                return redirect(url_for("main.admin_news"))

        news_item = News(
            title=title,
            category=category,
            content=content,
            image_filename=image_filename,
            pdf_filename=pdf_filename,
            created_by_id=current_user.id,
        )
        db.session.add(news_item)
        db.session.flush()

        if category in {"announcement", "timetable", "event"}:
            create_role_notifications(
                title="News Update",
                message=f"{NEWS_CATEGORIES[category]} updated: {title}",
                news_id=news_item.id,
            )

        db.session.commit()
        flash("News published successfully.", "success")
        return redirect(url_for("main.admin_news"))

    news_items = News.query.order_by(News.created_at.desc()).all()
    return render_template("admin/news_manage.html", news_items=news_items, news_categories=NEWS_CATEGORIES)


@main.route("/admin/dashboard")
@login_required
@role_required("admin")
def admin_dashboard():
    staff_members = User.query.filter_by(role="staff").order_by(User.full_name).all()
    students = Student.query.join(User).order_by(Student.roll_number).all()
    semesters = list(range(1, 7))

    marks_by_student_sem = {}
    all_marks = Mark.query.order_by(Mark.student_id, Mark.semester_id, Mark.id).all()
    for mark in all_marks:
        key = (mark.student_id, mark.semester.number)
        marks_by_student_sem.setdefault(key, []).append(mark)

    feedback_count = defaultdict(int)
    for feedback in Feedback.query.all():
        feedback_count[(feedback.student_id, feedback.semester.number)] += 1

    notification_count = defaultdict(int)
    for notification in Notification.query.all():
        sem_number = notification.semester.number if notification.semester else None
        notification_count[(notification.student_id, sem_number)] += 1

    rows = []
    for student in students:
        for sem_number in semesters:
            sem_marks = marks_by_student_sem.get((student.id, sem_number), [])
            breakdown = build_exam_breakdown(sem_marks)
            rows.append(
                {
                    "student": student,
                    "semester": sem_number,
                    "subject_count": len(sem_marks),
                    "first_internal_percentage": breakdown["first_internal"]["percentage"],
                    "second_internal_percentage": breakdown["second_internal"]["percentage"],
                    "model_exam_percentage": breakdown["model_exam"]["percentage"],
                    "university_exam_percentage": breakdown["university_exam"]["percentage"],
                    "feedback_count": feedback_count[(student.id, sem_number)],
                    "notification_count": notification_count[(student.id, sem_number)],
                }
            )

    recent_feedback = Feedback.query.order_by(Feedback.created_at.desc()).limit(20).all()
    recent_notifications = Notification.query.order_by(Notification.created_at.desc()).limit(20).all()
    latest_news = News.query.order_by(News.created_at.desc()).limit(10).all()

    return render_template(
        "admin/dashboard.html",
        staff_members=staff_members,
        students=students,
        rows=rows,
        recent_feedback=recent_feedback,
        recent_notifications=recent_notifications,
        latest_news=latest_news,
    )
