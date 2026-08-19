from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
from functools import wraps
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-in-production")

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
DB_PATH = BASE_DIR / "schedule_portal.db"

SCHEDULES = {
    "current": UPLOAD_DIR / "current.pdf",
    "next": UPLOAD_DIR / "next_week.pdf",
}

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee',
            job_title TEXT DEFAULT 'Employee',
            password_hash TEXT NOT NULL,
            must_change_password INTEGER NOT NULL DEFAULT 1,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    admin = conn.execute("SELECT id FROM users WHERE employee_id = ?", ("admin",)).fetchone()
    if not admin:
        conn.execute("""
            INSERT INTO users
            (employee_id, name, role, job_title, password_hash, must_change_password)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "admin",
            "Administrator",
            "admin",
            "System Administrator",
            generate_password_hash("password"),
            1,
        ))
    conn.commit()
    conn.close()

def get_user(employee_id):
    conn = db()
    user = conn.execute(
        "SELECT * FROM users WHERE employee_id = ? AND active = 1",
        (employee_id,)
    ).fetchone()
    conn.close()
    return user

def current_user():
    employee_id = session.get("employee_id")
    return get_user(employee_id) if employee_id else None

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("employee_id"):
            return redirect(url_for("login"))
        user = current_user()
        if not user:
            session.clear()
            return redirect(url_for("login"))
        if user["must_change_password"] and request.endpoint != "change_password":
            return redirect(url_for("change_password"))
        return view(*args, **kwargs)
    return wrapped

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("employee_id"):
            return redirect(url_for("login"))
        user = current_user()
        if not user or user["role"] != "admin":
            flash("Administrator access is required.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped

@app.context_processor
def inject_globals():
    return {
        "schedule_exists": SCHEDULES["current"].exists(),
        "next_schedule_exists": SCHEDULES["next"].exists(),
        "current_user": current_user(),
    }

@app.get("/")
def index():
    return redirect(url_for("dashboard") if session.get("employee_id") else url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        employee_id = request.form.get("employee_id", "").strip()
        password = request.form.get("password", "")
        user = get_user(employee_id)

        if user and check_password_hash(user["password_hash"], password):
            session["employee_id"] = user["employee_id"]
            if user["must_change_password"]:
                return redirect(url_for("change_password"))
            return redirect(url_for("admin_dashboard") if user["role"] == "admin" else url_for("dashboard"))

        error = "We couldn't sign you in. Please check your employee ID and password."

    return render_template("login.html", error=error)

@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    if not session.get("employee_id"):
        return redirect(url_for("login"))

    user = current_user()
    if not user:
        session.clear()
        return redirect(url_for("login"))

    error = None
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")

        if not check_password_hash(user["password_hash"], current):
            error = "Your current password is incorrect."
        elif len(new) < 8:
            error = "Your new password must be at least 8 characters."
        elif new != confirm:
            error = "The new passwords do not match."
        elif new == current:
            error = "Your new password must be different from your temporary password."
        else:
            conn = db()
            conn.execute("""
                UPDATE users
                SET password_hash = ?, must_change_password = 0
                WHERE id = ?
            """, (generate_password_hash(new), user["id"]))
            conn.commit()
            conn.close()
            return redirect(url_for("admin_dashboard") if user["role"] == "admin" else url_for("dashboard"))

    return render_template("change_password.html", error=error, forced=bool(user["must_change_password"]))

@app.get("/dashboard")
@login_required
def dashboard():
    user = current_user()
    return render_template(
        "dashboard.html",
        employee_name=user["name"],
        employee_role=user["job_title"],
    )

@app.get("/schedule")
@login_required
def schedule():
    return render_template("schedule.html")

@app.get("/schedule/view/<which>")
@login_required
def schedule_view(which):
    if which not in SCHEDULES:
        return "Not found", 404
    path = SCHEDULES[which]
    if not path.exists():
        flash("That schedule hasn't been uploaded yet.", "error")
        return redirect(url_for("schedule"))
    title = "Current Schedule" if which == "current" else "Next Week"
    return render_template("schedule_view.html", which=which, title=title)

@app.get("/account")
@login_required
def account():
    user = current_user()
    return render_template("account.html")

@app.get("/schedule/<which>")
@login_required
def schedule_pdf(which):
    if which not in SCHEDULES:
        return "Not found", 404
    path = SCHEDULES[which]
    if not path.exists():
        return "Schedule not uploaded yet.", 404
    return send_from_directory(path.parent, path.name, mimetype="application/pdf")

@app.get("/admin")
@admin_required
def admin_dashboard():
    conn = db()
    total = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'employee'").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'employee' AND active = 1").fetchone()[0]
    conn.close()
    return render_template("admin.html", total_users=total, active_users=active)

@app.route("/admin/upload", methods=["GET", "POST"])
@admin_required
def admin_upload():
    error = None
    success = None
    if request.method == "POST":
        schedule_type = request.form.get("schedule_type")
        pdf = request.files.get("pdf")
        if schedule_type not in SCHEDULES or not pdf or not pdf.filename.lower().endswith(".pdf"):
            error = "Please select a schedule type and PDF file."
        else:
            pdf.save(SCHEDULES[schedule_type])
            success = "Schedule published successfully."
    return render_template("admin_upload.html", error=error, success=success)

@app.get("/admin/users")
@admin_required
def admin_users():
    conn = db()
    users = conn.execute("""
        SELECT id, employee_id, name, role, job_title, must_change_password, active, created_at
        FROM users ORDER BY role DESC, name COLLATE NOCASE
    """).fetchall()
    conn.close()
    return render_template("admin_users.html", users=users)

@app.route("/admin/users/new", methods=["GET", "POST"])
@admin_required
def admin_user_new():
    error = None
    if request.method == "POST":
        employee_id = request.form.get("employee_id", "").strip()
        name = request.form.get("name", "").strip()
        job_title = request.form.get("job_title", "").strip() or "Employee"
        role = request.form.get("role", "employee")

        if not employee_id or not name:
            error = "Employee ID and name are required."
        elif role not in ("employee", "admin"):
            error = "Invalid role."
        else:
            conn = db()
            try:
                conn.execute("""
                    INSERT INTO users
                    (employee_id, name, role, job_title, password_hash, must_change_password)
                    VALUES (?, ?, ?, ?, ?, 1)
                """, (
                    employee_id, name, role, job_title,
                    generate_password_hash("password")
                ))
                conn.commit()
            except sqlite3.IntegrityError:
                error = "That employee ID is already in use."
            finally:
                conn.close()

            if not error:
                flash(f"{name} was created with the temporary password 'password'.", "success")
                return redirect(url_for("admin_users"))

    return render_template("admin_user_form.html", error=error, editing=None)

@app.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_user_edit(user_id):
    conn = db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if not user:
        return "User not found", 404

    error = None
    if request.method == "POST":
        employee_id = request.form.get("employee_id", "").strip()
        name = request.form.get("name", "").strip()
        job_title = request.form.get("job_title", "").strip() or "Employee"
        role = request.form.get("role", "employee")
        active = 1 if request.form.get("active") == "1" else 0

        if not employee_id or not name:
            error = "Employee ID and name are required."
        elif role not in ("employee", "admin"):
            error = "Invalid role."
        elif user["employee_id"] == session.get("employee_id") and (role != "admin" or not active):
            error = "You cannot remove your own administrator access."
        else:
            conn = db()
            try:
                conn.execute("""
                    UPDATE users
                    SET employee_id = ?, name = ?, job_title = ?, role = ?, active = ?
                    WHERE id = ?
                """, (employee_id, name, job_title, role, active, user_id))
                conn.commit()
            except sqlite3.IntegrityError:
                error = "That employee ID is already in use."
            finally:
                conn.close()

            if not error:
                flash("User updated successfully.", "success")
                return redirect(url_for("admin_users"))

    return render_template("admin_user_form.html", error=error, editing=user)

@app.post("/admin/users/<int:user_id>/reset-password")
@admin_required
def admin_reset_password(user_id):
    conn = db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return "User not found", 404
    conn.execute("""
        UPDATE users SET password_hash = ?, must_change_password = 1 WHERE id = ?
    """, (generate_password_hash("password"), user_id))
    conn.commit()
    conn.close()
    flash(f"{user['name']}'s password was reset to the temporary password 'password'.", "success")
    return redirect(url_for("admin_users"))

@app.post("/admin/users/<int:user_id>/toggle")
@admin_required
def admin_toggle_user(user_id):
    conn = db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return "User not found", 404
    if user["employee_id"] == session.get("employee_id"):
        conn.close()
        flash("You cannot deactivate your own account.", "error")
        return redirect(url_for("admin_users"))
    conn.execute("UPDATE users SET active = ? WHERE id = ?", (0 if user["active"] else 1, user_id))
    conn.commit()
    conn.close()
    flash("User status updated.", "success")
    return redirect(url_for("admin_users"))

@app.post("/admin/users/<int:user_id>/delete")
@admin_required
def admin_delete_user(user_id):
    conn = db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return "User not found", 404
    if user["employee_id"] == session.get("employee_id"):
        conn.close()
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("admin_users"))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash(f"{user['name']} has been deleted.", "success")
    return redirect(url_for("admin_users"))

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
