"""
app.py — Main Flask application for Taskify.
Handles authentication, task CRUD, and page serving.
"""

import os
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    flash,
)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

from db import get_db, init_db

# ── Load environment ──────────────────────────────────────────────
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback-secret-key")


# ── Helper: Login Required Decorator ──────────────────────────────
def login_required(f):
    """Decorator to protect routes that need authentication."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


# ══════════════════════════════════════════════════════════════════
#  PAGE ROUTES
# ══════════════════════════════════════════════════════════════════


@app.route("/")
@login_required
def index():
    """Serve the main task dashboard."""
    return render_template("index.html", username=session.get("username"))


@app.route("/login", methods=["GET"])
def login_page():
    """Serve the login page."""
    if "user_id" in session:
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/register", methods=["GET"])
def register_page():
    """Serve the registration page."""
    if "user_id" in session:
        return redirect(url_for("index"))
    return render_template("register.html")


# ══════════════════════════════════════════════════════════════════
#  AUTHENTICATION API
# ══════════════════════════════════════════════════════════════════


@app.route("/register", methods=["POST"])
def register():
    """Register a new user account."""
    data = request.get_json()
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    # Validation
    if not username or not email or not password:
        return jsonify({"error": "All fields are required."}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    hashed = generate_password_hash(password)

    # try:
    conn = get_db()
    conn.execute(
        "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
        (username, email, hashed),
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Registration successful!"}), 201
    # except Exception as e:
    #     error_msg = str(e).upper()
    #     if "UNIQUE" in error_msg:
    #         return jsonify({"error": "Username or email already exists."}), 409
    #     return jsonify({"error": "Registration failed."}), 500


@app.route("/login", methods=["POST"])
def login():
    """Authenticate a user and start a session."""
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "All fields are required."}), 400

    try:
        conn = get_db()
        cursor = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()

        if row:
            user = dict(row)
            if check_password_hash(user["password"], password):
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                return jsonify({"message": "Login successful!"}), 200
        return jsonify({"error": "Invalid username or password."}), 401
    except Exception as e:
        return jsonify({"error": "Login failed."}), 500


@app.route("/logout")
def logout():
    """Clear the session and redirect to login."""
    session.clear()
    return redirect(url_for("login_page"))


# ══════════════════════════════════════════════════════════════════
#  TASK CRUD API
# ══════════════════════════════════════════════════════════════════


@app.route("/api/tasks", methods=["GET"])
@login_required
def get_tasks():
    """Return all tasks for the logged-in user."""
    user_id = session["user_id"]
    try:
        conn = get_db()
        cursor = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        # Convert rows to dicts and serialize for JSON
        tasks = []
        for row in rows:
            t = dict(row)
            t["status"] = bool(t["status"])
            tasks.append(t)

        return jsonify(tasks), 200
    except Exception as e:
        return jsonify({"error": "Could not fetch tasks."}), 500


@app.route("/api/tasks", methods=["POST"])
@login_required
def add_task():
    """Create a new task for the logged-in user."""
    user_id = session["user_id"]
    data = request.get_json()

    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    priority = data.get("priority", "Medium")
    category = data.get("category", "Personal")
    due_date = data.get("due_date") or None

    if not title:
        return jsonify({"error": "Task title is required."}), 400

    try:
        conn = get_db()
        cursor = conn.execute(
            """INSERT INTO tasks (user_id, title, description, priority, category, due_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, title, description, priority, category, due_date),
        )
        conn.commit()
        task_id = cursor.lastrowid
        conn.close()
        return jsonify({"message": "Task created!", "id": task_id}), 201
    except Exception as e:
        return jsonify({"error": "Could not create task."}), 500


@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
@login_required
def update_task(task_id):
    """Update an existing task (only if owned by the logged-in user)."""
    user_id = session["user_id"]
    data = request.get_json()

    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    priority = data.get("priority", "Medium")
    category = data.get("category", "Personal")
    due_date = data.get("due_date") or None
    status = data.get("status", False)

    if not title:
        return jsonify({"error": "Task title is required."}), 400

    try:
        conn = get_db()
        cursor = conn.execute(
            """UPDATE tasks
               SET title=?, description=?, priority=?, category=?,
                   due_date=?, status=?
               WHERE id=? AND user_id=?""",
            (
                title,
                description,
                priority,
                category,
                due_date,
                int(status),
                task_id,
                user_id,
            ),
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()

        if affected == 0:
            return jsonify({"error": "Task not found."}), 404
        return jsonify({"message": "Task updated!"}), 200
    except Exception as e:
        return jsonify({"error": "Could not update task."}), 500


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@login_required
def delete_task(task_id):
    """Delete a task (only if owned by the logged-in user)."""
    user_id = session["user_id"]
    try:
        conn = get_db()
        cursor = conn.execute(
            "DELETE FROM tasks WHERE id=? AND user_id=?", (task_id, user_id)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()

        if affected == 0:
            return jsonify({"error": "Task not found."}), 404
        return jsonify({"message": "Task deleted!"}), 200
    except Exception as e:
        return jsonify({"error": "Could not delete task."}), 500


# TEMPORARY ROUTE TO INITIALIZE CLOUD DATABASE
@app.route("/setup-db-secret-123")
def setup_database():
    try:
        from db import init_db

        init_db()
        return "✅ Database tables created successfully!"
    except Exception as e:
        return f"❌ Error creating database: {str(e)}"


# ══════════════════════════════════════════════════════════════════
#  APP STARTUP
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
