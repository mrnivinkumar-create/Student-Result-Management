from app import create_app, db
from app.models import Department, Semester, SubjectTemplate, User, Student, Mark

app = create_app()


@app.cli.command("init-db")
def init_db_command():
    db.drop_all()
    db.create_all()
    from app.seed import seed_reference_data

    seed_reference_data()
    print("Database initialized and seeded.")


if __name__ == "__main__":
    app.run(debug=True)
