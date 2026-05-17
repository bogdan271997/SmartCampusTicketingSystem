import pymysql.err
from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, render_template, request, session

from attachment_storage import KIND_RESOLUTION, delete_ticket_files, save_uploaded_files
from database import db
from permissions import (
    API_REPORTS,
    API_TICKETS,
    DASHBOARD_ADMIN,
    TICKETS_DELETE,
    TICKETS_EDIT_ANY,
    USERS_MANAGE,
    fetch_all_roles,
    fetch_ticket_status_names,
    fetch_users_for_assignment,
    parse_optional_status_filter,
    role_has_permission,
    session_has,
    session_has_any,
)

admin_bp = Blueprint("admin", __name__)


def _login_required():
    if "user_id" not in session:
        return redirect("/login")
    return None


def _permission_redirect():
    flash("You do not have access to that page.", "danger")
    if session_has(session, DASHBOARD_ADMIN):
        return redirect("/admin/dashboard")
    return redirect("/user/dashboard")


def _require_permissions(*codes: str):
    blocked = _login_required()
    if blocked:
        return blocked
    if not session_has_any(session, *codes):
        return _permission_redirect()
    return None


def _require_all_permissions(*codes: str):
    blocked = _login_required()
    if blocked:
        return blocked
    for code in codes:
        if not session_has(session, code):
            return _permission_redirect()
    return None


@admin_bp.route("/admin/dashboard")
def admin_dashboard():
    blocked = _require_permissions(DASHBOARD_ADMIN)
    if blocked:
        return blocked

    status_filter = parse_optional_status_filter(request.args.get("status"))
    statuses = fetch_ticket_status_names()

    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM tickets")
    total_tickets = cur.fetchone()[0]

    cur.execute(
        """
        SELECT ticket_status.status_name, COUNT(*)
        FROM tickets
        JOIN ticket_status ON tickets.status_id = ticket_status.id
        GROUP BY ticket_status.id, ticket_status.status_name
        ORDER BY ticket_status.id
        """
    )
    status_counts = cur.fetchall()

    base_sql = """
        SELECT tickets.id, tickets.title, users.name, ticket_status.status_name,
               tickets.created_at, tickets.priority, assignee.name
        FROM tickets
        JOIN users ON tickets.created_by = users.id
        JOIN ticket_status ON tickets.status_id = ticket_status.id
        LEFT JOIN users AS assignee ON tickets.assigned_to = assignee.id
    """
    conditions: list[str] = []
    params: list = []
    if status_filter:
        conditions.append("ticket_status.status_name = %s")
        params.append(status_filter)
    where_part = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    cur.execute(
        base_sql + where_part + " ORDER BY tickets.created_at DESC",
        tuple(params),
    )

    tickets = cur.fetchall()
    cur.close()

    return render_template(
        "admin/dashboard.html",
        tickets=tickets,
        total_tickets=total_tickets,
        status_counts=status_counts,
        status_filter=status_filter,
        statuses=statuses,
    )


@admin_bp.route("/admin/reports")
def admin_reports():
    """Reports & API-driven statistics (requires JSON API permissions)."""
    blocked = _require_all_permissions(API_REPORTS, API_TICKETS)
    if blocked:
        return blocked
    statuses = fetch_ticket_status_names()
    return render_template("admin/reports.html", statuses=statuses)


@admin_bp.route("/admin/users", methods=["GET", "POST"])
def admin_users():
    blocked = _require_permissions(USERS_MANAGE)
    if blocked:
        return blocked

    all_roles = fetch_all_roles()
    allowed_ids = {r[0] for r in all_roles}

    if request.method == "POST":
        try:
            uid = int(request.form["user_id"])
            new_role = int(request.form["role_id"])
        except (KeyError, TypeError, ValueError):
            flash("Invalid request.", "danger")
            return redirect("/admin/users")

        if new_role not in allowed_ids:
            flash("Invalid role.", "danger")
            return redirect("/admin/users")

        self_id = int(session["user_id"])
        self_role_id = int(session.get("role_id", 0))
        if uid == self_id:
            if role_has_permission(self_role_id, USERS_MANAGE) and not role_has_permission(
                new_role, USERS_MANAGE
            ):
                flash("You cannot remove your own user-management access here.", "warning")
                return redirect("/admin/users")

        cur = db.cursor()
        cur.execute("UPDATE users SET role_id = %s WHERE id = %s", (new_role, uid))
        db.commit()
        cur.close()
        flash("User role updated.", "success")
        return redirect("/admin/users")

    cur = db.cursor()
    cur.execute(
        """
        SELECT users.id, users.name, users.email, users.role_id, COALESCE(roles.role_name, 'user')
        FROM users
        LEFT JOIN roles ON users.role_id = roles.id
        ORDER BY users.id
        """
    )
    users = cur.fetchall()
    cur.close()

    return render_template("admin/users.html", users=users, roles=all_roles)


@admin_bp.route("/admin/users/delete/<int:user_id>", methods=["POST"])
def admin_delete_user(user_id):
    blocked = _require_permissions(USERS_MANAGE)
    if blocked:
        return blocked

    if user_id == int(session["user_id"]):
        flash("You cannot delete your own account.", "warning")
        return redirect("/admin/users")

    cur = db.cursor()
    cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
    if not cur.fetchone():
        cur.close()
        flash("User not found.", "danger")
        return redirect("/admin/users")

    upload_root = Path(current_app.config["UPLOAD_FOLDER"])

    try:
        cur.execute(
            "SELECT id FROM tickets WHERE created_by = %s", (user_id,)
        )
        for (tid,) in cur.fetchall():
            delete_ticket_files(upload_root, int(tid))

        cur.execute(
            """
            DELETE c FROM comments c
            INNER JOIN tickets t ON c.ticket_id = t.id
            WHERE t.created_by = %s
            """,
            (user_id,),
        )
        cur.execute("DELETE FROM tickets WHERE created_by = %s", (user_id,))
        cur.execute(
            "UPDATE tickets SET assigned_to = NULL WHERE assigned_to = %s",
            (user_id,),
        )
        cur.execute("DELETE FROM comments WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        db.commit()
    except pymysql.err.Error:
        db.rollback()
        cur.close()
        flash("Could not delete user. Try again or check database constraints.", "danger")
        return redirect("/admin/users")
    cur.close()
    flash("User deleted.", "success")
    return redirect("/admin/users")


@admin_bp.route("/admin/ticket/edit/<int:ticket_id>", methods=["GET", "POST"])
def admin_edit_ticket(ticket_id):
    blocked = _require_permissions(TICKETS_EDIT_ANY)
    if blocked:
        return blocked

    cur = db.cursor()
    cur.execute(
        """
        SELECT id, title, description, resolution, status_id, priority, assigned_to
        FROM tickets
        WHERE id = %s
        """,
        (ticket_id,),
    )
    ticket = cur.fetchone()
    if not ticket:
        cur.close()
        flash("Ticket not found.", "danger")
        return redirect("/admin/dashboard")

    cur.execute("SELECT id, status_name FROM ticket_status ORDER BY id")
    statuses = cur.fetchall()
    assign_users = fetch_users_for_assignment()

    if request.method == "POST":
        title = request.form["title"].strip()
        description = request.form["description"].strip()
        priority = (request.form.get("priority") or "Medium").strip()
        if priority not in ("Low", "Medium", "High", "Urgent"):
            priority = "Medium"

        try:
            status_id = int(request.form["status_id"])
        except (KeyError, ValueError):
            cur.close()
            flash("Invalid status.", "danger")
            return redirect(f"/admin/ticket/edit/{ticket_id}")

        resolution = (request.form.get("resolution") or "").strip()
        res_files = request.files.getlist("resolution_files")
        has_res_files = any(
            f and f.filename and str(f.filename).strip() for f in res_files
        )

        cur.execute("SELECT status_name FROM ticket_status WHERE id = %s", (status_id,))
        strow = cur.fetchone()
        if strow and (strow[0] or "").strip().lower() == "closed" and not resolution and not has_res_files:
            cur.close()
            flash(
                "Before closing, add a resolution (text and/or attachments) for the requester.",
                "warning",
            )
            return redirect(f"/admin/ticket/edit/{ticket_id}")

        assign_raw = (request.form.get("assigned_to") or "").strip()
        assigned_to: int | None
        if assign_raw in ("", "none", "unassigned"):
            assigned_to = None
        else:
            try:
                assigned_to = int(assign_raw)
            except ValueError:
                cur.close()
                flash("Invalid assignee.", "danger")
                return redirect(f"/admin/ticket/edit/{ticket_id}")
            cur.execute("SELECT id FROM users WHERE id = %s LIMIT 1", (assigned_to,))
            if not cur.fetchone():
                cur.close()
                flash("That user does not exist.", "danger")
                return redirect(f"/admin/ticket/edit/{ticket_id}")

        cur.execute(
            """
            UPDATE tickets
            SET title = %s, description = %s, resolution = %s, status_id = %s,
                priority = %s, assigned_to = %s
            WHERE id = %s
            """,
            (
                title,
                description,
                resolution or None,
                status_id,
                priority,
                assigned_to,
                ticket_id,
            ),
        )
        upload_root = Path(current_app.config["UPLOAD_FOLDER"])
        errs = save_uploaded_files(
            upload_root,
            cur,
            ticket_id,
            int(session["user_id"]),
            KIND_RESOLUTION,
            None,
            res_files,
        )
        db.commit()
        cur.close()
        for msg in errs:
            flash(msg, "warning")
        flash("Ticket updated.", "success")
        return redirect("/admin/dashboard")

    cur.close()
    return render_template(
        "admin/edit_ticket.html",
        ticket=ticket,
        statuses=statuses,
        assign_users=assign_users,
    )


@admin_bp.route("/admin/ticket/delete/<int:ticket_id>", methods=["POST"])
def admin_delete_ticket(ticket_id):
    blocked = _require_permissions(TICKETS_DELETE)
    if blocked:
        return blocked

    upload_root = Path(current_app.config["UPLOAD_FOLDER"])
    delete_ticket_files(upload_root, ticket_id)

    cur = db.cursor()
    cur.execute("DELETE FROM comments WHERE ticket_id = %s", (ticket_id,))
    cur.execute("DELETE FROM tickets WHERE id = %s", (ticket_id,))
    db.commit()
    cur.close()

    flash("Ticket deleted.", "success")
    return redirect("/admin/dashboard")
