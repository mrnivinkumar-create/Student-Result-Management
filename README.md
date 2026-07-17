# Student Result Management System

A full-stack college result portal built with Flask, HTML, CSS, and JavaScript.

## Features
- Separate login for `student` and `staff`
- Account creation for both roles
- Department selection after login:
  - BCA
  - BSc CS
  - BSc AI
  - BA English
  - B.Com General
  - B.Com CA
  - B.Com PA
- Staff dashboard:
  - Add / edit / delete students
  - Organize by year: first, second, final
  - Assign and manage roll numbers
  - Enter and edit marks per semester and subject
- Student dashboard:
  - View all semester marks
  - Semester percentage and SGPA
  - Overall CGPA

## Tech Stack
- Frontend: HTML, CSS, JavaScript
- Backend: Python + Flask
- Database: SQLite by default (`DATABASE_URL` can be set for MySQL)

## Setup
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:5000`

## Optional MySQL
Set environment variable:

```bash
set DATABASE_URL=mysql+pymysql://username:password@localhost/student_result_db
```

Install driver when using MySQL:

```bash
pip install pymysql
```

## Calculation Logic
- Subject average = `(first_internal + second_internal + model_exam + university_exam) / 4`
- Semester percentage = average of all subject averages in that semester
- SGPA = `semester_percentage / 10` (capped at 10)
- Overall CGPA = average of populated semester SGPAs
