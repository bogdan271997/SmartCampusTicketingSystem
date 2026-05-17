import pymysql
from flask import Blueprint, flash, redirect, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from database import db
from permissions import DASHBOARD_ADMIN, fetch_default_user_role_id, fetch_permissions_for_role

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method != "POST":
        return render_template("register.html")

    name = request.form["name"].strip()
    email = request.form["email"].strip().lower()
    password = request.form["password"]

    default_role_id = fetch_default_user_role_id()
    if default_role_id is None:
        flash("Registration is temporarily unavailable.", "danger")
        return render_template("register.html")

    try:
        cur = db.cursor()
        cur.execute(
            """
            INSERT INTO users (name, email, password_hash, role_id)
            VALUES (%s, %s, %s, %s)
            """,
            (name, email, generate_password_hash(password), default_role_id),
        )
        db.commit()
        cur.close()
    except pymysql.err.IntegrityError:
        db.rollback()
        flash("That email is already registered.", "danger")
        return render_template("register.html")

    flash("Registration successful. You can log in now.", "success")
    return redirect("/login")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method != "POST":
        return render_template("login.html")

    email = request.form["email"].strip().lower()
    password = request.form["password"]

    cur = db.cursor()
    cur.execute(
        """
        SELECT users.id, users.name, users.email, users.password_hash, users.role_id,
               COALESCE(roles.role_name, 'user')
        FROM users
        LEFT JOIN roles ON users.role_id = roles.id
        WHERE users.email = %s
        """,
        (email,),
    )
    user = cur.fetchone()
    cur.close()

    if not user or not check_password_hash(user[3], password):
        flash("Invalid email or password.", "danger")
        return render_template("login.html")

    role_id = int(user[4] or 0)
    role_name = (user[5] or "user").strip()

    session["user_id"] = user[0]
    session["role_id"] = role_id
    session["role_name"] = role_name
    session["name"] = user[1]
    session["permissions"] = fetch_permissions_for_role(role_id)

    if DASHBOARD_ADMIN in session["permissions"]:
        return redirect("/admin/dashboard")
    return redirect("/user/dashboard")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/login")
