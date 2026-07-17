from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from app import db, login_manager


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(20), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student_profile = db.relationship("Student", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)


class Semester(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False, unique=True)
    label = db.Column(db.String(40), nullable=False)


class SubjectTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    semester_id = db.Column(db.Integer, db.ForeignKey("semester.id"), nullable=False)
    subject_name = db.Column(db.String(120), nullable=False)

    department = db.relationship("Department")
    semester = db.relationship("Semester")


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    roll_number = db.Column(db.String(30), nullable=False, unique=True)
    phone_number = db.Column(db.String(15), nullable=False)
    year = db.Column(db.Integer, nullable=False, default=1)

    user = db.relationship("User", back_populates="student_profile")
    marks = db.relationship("Mark", back_populates="student", cascade="all, delete-orphan")
    feedback_entries = db.relationship("Feedback", back_populates="student", cascade="all, delete-orphan")
    notifications = db.relationship("Notification", back_populates="student", cascade="all, delete-orphan")


class Mark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    semester_id = db.Column(db.Integer, db.ForeignKey("semester.id"), nullable=False)
    subject_name = db.Column(db.String(120), nullable=False)
    first_internal = db.Column(db.Float, nullable=False, default=0.0)
    second_internal = db.Column(db.Float, nullable=False, default=0.0)
    model_exam = db.Column(db.Float, nullable=False, default=0.0)
    university_exam = db.Column(db.Float, nullable=False, default=0.0)

    student = db.relationship("Student", back_populates="marks")
    semester = db.relationship("Semester")

    @property
    def subject_average(self):
        values = [self.first_internal, self.second_internal, self.model_exam, self.university_exam]
        return round(sum(values) / 4.0, 2)


class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    semester_id = db.Column(db.Integer, db.ForeignKey("semester.id"), nullable=False)
    exam_type = db.Column(db.String(30), nullable=False)
    feedback_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    comments = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    student = db.relationship("Student", back_populates="feedback_entries")
    semester = db.relationship("Semester")
    feedback_by = db.relationship("User")


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    semester_id = db.Column(db.Integer, db.ForeignKey("semester.id"), nullable=True)
    exam_type = db.Column(db.String(30), nullable=True)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    student = db.relationship("Student", back_populates="notifications")
    semester = db.relationship("Semester")


class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(30), nullable=False, default="general")
    content = db.Column(db.Text, nullable=False)
    image_filename = db.Column(db.String(255), nullable=True)
    pdf_filename = db.Column(db.String(255), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    created_by = db.relationship("User")


class BroadcastNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient_role = db.Column(db.String(20), nullable=False)  # staff or student
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    news_id = db.Column(db.Integer, db.ForeignKey("news.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    news = db.relationship("News")
