import functools
from flask import session, jsonify, request, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from database import get_db


def login_user(username: str, password: str, conn=None):
    """
    Authenticate a user against SQLite users table.
    Returns (success: bool, user_dict_or_error_msg: Any).
    """
    if conn is None:
        conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ? AND active = 1", (username.strip(),))
    user = cur.fetchone()

    if not user:
        return False, "Invalid username or account inactive."

    if not check_password_hash(user["password_hash"], password):
        return False, "Invalid credentials provided."

    user_info = {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"]
    }
    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["user_role"] = user["role"]
    session.permanent = True

    return True, user_info


def logout_user():
    """Clear session data."""
    session.clear()


def get_current_user():
    """Retrieve current logged-in user from session if authenticated."""
    if "user_id" in session:
        return {
            "id": session.get("user_id"),
            "username": session.get("username"),
            "role": session.get("user_role")
        }
    return None


def login_required(view_func):
    """Decorator requiring a logged-in session."""
    @functools.wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized. Please authenticate.", "authenticated": False}), 401
            return redirect(url_for("login_page"))
        return view_func(*args, **kwargs)
    return wrapped_view


def role_required(*allowed_roles):
    """
    Decorator requiring user to have one of the specified roles.
    Administrators are automatically granted access to all roles.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapped_view(*args, **kwargs):
            if "user_id" not in session:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Unauthorized. Authentication required.", "authenticated": False}), 401
                return redirect(url_for("login_page"))

            user_role = session.get("user_role")
            if user_role == "Administrator" or user_role in allowed_roles:
                return view_func(*args, **kwargs)

            if request.path.startswith("/api/"):
                return jsonify({
                    "error": f"Forbidden: This action requires one of the following roles: {', '.join(allowed_roles)}. Your role is '{user_role}'.",
                    "required_roles": list(allowed_roles),
                    "user_role": user_role
                }), 403
            return redirect(url_for("dashboard_page"))
        return wrapped_view
    return decorator
