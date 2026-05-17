from pathlib import Path

from flask import Flask, flash, redirect, request, session
from werkzeug.exceptions import RequestEntityTooLarge

app = Flask(__name__)
app.secret_key = "super_secret_key"

_UPLOAD_ROOT = Path(__file__).resolve().parent / "uploads" / "ticket_files"
_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
app.config["UPLOAD_FOLDER"] = str(_UPLOAD_ROOT)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

from permissions import fetch_permissions_for_role

from routes.admin_routes import admin_bp
from routes.api_routes import api_bp
from routes.auth_routes import auth_bp
from routes.user_routes import user_bp

app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)


@app.errorhandler(RequestEntityTooLarge)
def _upload_too_large(_exc):
    flash("Total upload is too large (max about 32 MB per request).", "danger")
    return redirect(request.referrer or "/user/dashboard")

with app.app_context():
    try:
        from database import apply_schema_patches, init_schema_if_needed, seed_builtin_users

        init_schema_if_needed()
        apply_schema_patches()
        seed_builtin_users()
    except Exception as exc:
        app.logger.warning("Builtin user seed skipped: %s", exc)


@app.before_request
def _ensure_permissions_in_session():
    if session.get("user_id") and session.get("permissions") is None and session.get("role_id") is not None:
        session["permissions"] = fetch_permissions_for_role(int(session["role_id"]))


@app.route("/")
def home():
    return redirect("/login")


if __name__ == "__main__":
    app.run(debug=True)
