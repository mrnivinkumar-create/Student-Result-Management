from app import db
from app.models import Department, Semester, SubjectTemplate, User

DEPARTMENTS = [
    ("BCA", "BCA"),
    ("BSC_CS", "BSc CS"),
    ("BSC_AI", "BSc AI"),
    ("BA_ENG", "BA English"),
    ("BCOM_GEN", "B.Com General"),
    ("BCOM_CA", "B.Com CA"),
    ("BCOM_PA", "B.Com PA"),
]

SEMESTERS = [(1, "Semester 1"), (2, "Semester 2"), (3, "Semester 3"), (4, "Semester 4"), (5, "Semester 5"), (6, "Semester 6")]

DEFAULT_SUBJECTS = {
    "core": ["Core Subject 1", "Core Subject 2", "Core Subject 3", "Language", "Elective"],
}


def seed_reference_data():
    if Department.query.count() == 0:
        for code, name in DEPARTMENTS:
            db.session.add(Department(code=code, name=name))

    if Semester.query.count() == 0:
        for number, label in SEMESTERS:
            db.session.add(Semester(number=number, label=label))

    db.session.commit()

    if SubjectTemplate.query.count() == 0:
        departments = Department.query.all()
        semesters = Semester.query.all()
        for dept in departments:
            for semester in semesters:
                year = 1 if semester.number in (1, 2) else 2 if semester.number in (3, 4) else 3
                for subject in DEFAULT_SUBJECTS["core"]:
                    db.session.add(
                        SubjectTemplate(
                            department_id=dept.id,
                            year=year,
                            semester_id=semester.id,
                            subject_name=subject,
                        )
                    )
        db.session.commit()

    admin_user = User.query.filter_by(role="admin", username="admin").first()
    if not admin_user:
        admin_user = User(role="admin", full_name="System Administrator", username="admin")
        admin_user.set_password("admin123")
        db.session.add(admin_user)
        db.session.commit()
