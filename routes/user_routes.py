from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from attachment_storage import (
    KIND_REMARK,
    KIND_RESOLUTION,
    KIND_TICKET,
    save_uploaded_files,
)
from database import db
from permissions import (
    TICKETS_EDIT_ANY,
    TICKETS_VIEW_ALL,
    fetch_ticket_status_names,
    fetch_users_for_assignment,
    parse_optional_status_filter,
    session_has,
)

user_bp = Blueprint("user", __name__)


def _default_new_ticket_status_id(cur) -> int:
    """New submissions start as Open until staff changes status or assignment."""
    cur.execute(
        "SELECT id FROM ticket_status WHERE status_name = %s LIMIT 1",
        ("Open",),
    )
    row = cur.fetchone()
    return int(row[0]) if row else 1


def _can_view_ticket_row(row) -> bool:
    """row: created_by at index 7 in detail query."""
    if not row:
        return False
    created_by = row[7]
    if session_has(session, TICKETS_VIEW_ALL):
        return True
    return created_by == session.get("user_id")


def _group_attachments(rows):
    ticket_files: list[dict] = []
    resolution_files: list[dict] = []
    by_remark: dict[int, list[dict]] = {}
    for row in rows:
        aid, cid, kind, oname, fsize = row[0], row[1], row[2], row[3], row[4]
        item = {"id": aid, "name": oname, "size": fsize}
        if kind == KIND_TICKET:
            ticket_files.append(item)
        elif kind == KIND_RESOLUTION:
            resolution_files.append(item)
        elif kind == KIND_REMARK and cid:
            by_remark.setdefault(int(cid), []).append(item)
    return ticket_files, resolution_files, by_remark


@user_bp.route("/user/dashboard")
def user_dashboard():
    if "user_id" not in session:
        return redirect("/login")

    status_filter = parse_optional_status_filter(request.args.get("status"))
    statuses = fetch_ticket_status_names()

    cur = db.cursor()
    status_clause = ""
    params: list = [session["user_id"]]
    if status_filter:
        status_clause = " AND ticket_status.status_name = %s"
        params.append(status_filter)

    cur.execute(
        f"""
        SELECT tickets.id, tickets.title, ticket_status.status_name,
               tickets.created_at, tickets.priority
        FROM tickets
        JOIN ticket_status ON tickets.status_id = ticket_status.id
        WHERE tickets.created_by = %s
        {status_clause}
        ORDER BY tickets.created_at DESC
        """,
        tuple(params),
    )
    tickets = cur.fetchall()
    cur.close()

    return render_template(
        "user/dashboard.html",
        tickets=tickets,
        statuses=statuses,
        status_filter=status_filter,
    )


@user_bp.route("/tickets/<int:ticket_id>")
def ticket_detail(ticket_id):
    if "user_id" not in session:
        return redirect("/login")

    cur = db.cursor()
    cur.execute(
        """
        SELECT tickets.id, tickets.title, tickets.description, tickets.resolution,
               ticket_status.status_name, tickets.created_at, tickets.priority,
               tickets.created_by, users.name, users.email, tickets.status_id,
               tickets.assigned_to, assignee.name, assignee.email
        FROM tickets
        JOIN ticket_status ON tickets.status_id = ticket_status.id
        JOIN users ON tickets.created_by = users.id
        LEFT JOIN users AS assignee ON tickets.assigned_to = assignee.id
        WHERE tickets.id = %s
        """,
        (ticket_id,),
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        flash("Ticket not found.", "danger")
        return redirect("/user/dashboard")

    if not _can_view_ticket_row(row):
        cur.close()
        flash("You do not have access to that ticket.", "danger")
        return redirect("/user/dashboard")

    cur.execute(
        """
        SELECT comments.id, comments.comment_text, comments.created_at, users.name
        FROM comments
        JOIN users ON comments.user_id = users.id
        WHERE comments.ticket_id = %s
        ORDER BY comments.created_at ASC
        """,
        (ticket_id,),
    )
    remarks = cur.fetchall()

    cur.execute(
        """
        SELECT id, comment_id, kind, original_name, file_size
        FROM ticket_attachments
        WHERE ticket_id = %s
        ORDER BY created_at ASC
        """,
        (ticket_id,),
    )
    ticket_files, resolution_files, remark_files = _group_attachments(cur.fetchall())

    staff_can_edit = session_has(session, TICKETS_EDIT_ANY)
    statuses = []
    assignment_choices = []
    if staff_can_edit:
        cur.execute("SELECT id, status_name FROM ticket_status ORDER BY id")
        statuses = cur.fetchall()
        assignment_choices = fetch_users_for_assignment()

    cur.close()

    return render_template(
        "user/ticket_detail.html",
        t=row,
        remarks=remarks,
        ticket_files=ticket_files,
        resolution_files=resolution_files,
        remark_files=remark_files,
        staff_can_edit=staff_can_edit,
        statuses=statuses,
        assignment_choices=assignment_choices,
    )


@user_bp.route("/attachments/<int:attachment_id>")
def attachment_download(attachment_id):
    if "user_id" not in session:
        return redirect("/login")

    cur = db.cursor()
    cur.execute(
        """
        SELECT ta.stored_path, ta.original_name, t.created_by
        FROM ticket_attachments ta
        JOIN tickets t ON ta.ticket_id = t.id
        WHERE ta.id = %s
        """,
        (attachment_id,),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        abort(404)

    stored_path, original_name, created_by = row
    if not session_has(session, TICKETS_VIEW_ALL) and int(created_by) != int(
        session["user_id"]
    ):
        abort(403)

    root = Path(current_app.config["UPLOAD_FOLDER"])
    full_path = root / stored_path
    if not full_path.is_file():
        abort(404)

    return send_file(
        full_path,
        as_attachment=True,
        download_name=original_name or "attachment",
    )


@user_bp.route("/tickets/<int:ticket_id>/remark", methods=["POST"])
def ticket_add_remark(ticket_id):
    if "user_id" not in session:
        return redirect("/login")

    text = (request.form.get("remark") or "").strip()
    files = request.files.getlist("remark_files")
    has_files = any(
        f and f.filename and str(f.filename).strip() for f in files
    )

    if not text and not has_files:
        flash("Add some text and/or at least one attachment.", "warning")
        return redirect(f"/tickets/{ticket_id}")

    cur = db.cursor()
    cur.execute(
        """
        SELECT tickets.id, tickets.created_by
        FROM tickets WHERE tickets.id = %s
        """,
        (ticket_id,),
    )
    trow = cur.fetchone()
    if not trow:
        cur.close()
        flash("Ticket not found.", "danger")
        return redirect("/user/dashboard")

    if not session_has(session, TICKETS_VIEW_ALL) and trow[1] != session["user_id"]:
        cur.close()
        flash("You cannot add remarks on this ticket.", "danger")
        return redirect("/user/dashboard")

    cur.execute(
        """
        INSERT INTO comments (ticket_id, user_id, comment_text)
        VALUES (%s, %s, %s)
        """,
        (ticket_id, session["user_id"], text),
    )
    comment_id = cur.lastrowid

    upload_root = Path(current_app.config["UPLOAD_FOLDER"])
    errs = save_uploaded_files(
        upload_root,
        cur,
        ticket_id,
        int(session["user_id"]),
        KIND_REMARK,
        int(comment_id),
        files,
    )
    db.commit()
    cur.close()

    for msg in errs:
        flash(msg, "warning")
    flash("Remark added.", "success")
    return redirect(f"/tickets/{ticket_id}")


@user_bp.route("/tickets/<int:ticket_id>/staff-update", methods=["POST"])
def ticket_staff_update(ticket_id):
    if "user_id" not in session:
        return redirect("/login")
    if not session_has(session, TICKETS_EDIT_ANY):
        flash("You do not have permission to update this ticket.", "danger")
        return redirect(f"/tickets/{ticket_id}")

    cur = db.cursor()
    cur.execute(
        """
        SELECT tickets.created_by, tickets.status_id
        FROM tickets WHERE id = %s
        """,
        (ticket_id,),
    )
    trow = cur.fetchone()
    if not trow:
        cur.close()
        flash("Ticket not found.", "danger")
        return redirect("/user/dashboard")

    if not session_has(session, TICKETS_VIEW_ALL) and trow[0] != session["user_id"]:
        cur.close()
        flash("You do not have access to this ticket.", "danger")
        return redirect("/user/dashboard")

    try:
        status_id = int(request.form["status_id"])
    except (KeyError, ValueError):
        cur.close()
        flash("Invalid status.", "danger")
        return redirect(f"/tickets/{ticket_id}")

    resolution = (request.form.get("resolution") or "").strip()
    res_files = request.files.getlist("resolution_files")
    has_res_files = any(
        f and f.filename and str(f.filename).strip() for f in res_files
    )

    cur.execute("SELECT status_name FROM ticket_status WHERE id = %s", (status_id,))
    srow = cur.fetchone()
    if not srow:
        cur.close()
        flash("Invalid status.", "danger")
        return redirect(f"/tickets/{ticket_id}")

    status_name = (srow[0] or "").strip().lower()
    if status_name == "closed" and not resolution and not has_res_files:
        cur.close()
        flash(
            "Before closing, add a resolution (text and/or attachments) summarizing the outcome.",
            "warning",
        )
        return redirect(f"/tickets/{ticket_id}")

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
            return redirect(f"/tickets/{ticket_id}")
        cur.execute("SELECT id FROM users WHERE id = %s LIMIT 1", (assigned_to,))
        if not cur.fetchone():
            cur.close()
            flash("That user does not exist.", "danger")
            return redirect(f"/tickets/{ticket_id}")

    cur.execute(
        """
        UPDATE tickets
        SET status_id = %s, resolution = %s, assigned_to = %s
        WHERE id = %s
        """,
        (status_id, resolution or None, assigned_to, ticket_id),
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
    return redirect(f"/tickets/{ticket_id}")


@user_bp.route("/tickets/create", methods=["GET", "POST"])
def create_ticket():
    if "user_id" not in session:
        return redirect("/login")

    if request.method != "POST":
        return render_template("user/create_ticket.html")

    title = request.form["title"].strip()
    description = request.form["description"].strip()
    priority = (request.form.get("priority") or "Medium").strip()

    if priority not in ("Low", "Medium", "High", "Urgent"):
        priority = "Medium"

    if not title or not description:
        flash("Title and description are required.", "danger")
        return render_template("user/create_ticket.html")

    cur = db.cursor()
    status_id = _default_new_ticket_status_id(cur)
    cur.execute(
        """
        INSERT INTO tickets (title, description, created_by, status_id, priority)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (title, description, session["user_id"], status_id, priority),
    )
    ticket_id = cur.lastrowid

    upload_root = Path(current_app.config["UPLOAD_FOLDER"])
    errs = save_uploaded_files(
        upload_root,
        cur,
        int(ticket_id),
        int(session["user_id"]),
        KIND_TICKET,
        None,
        request.files.getlist("attachments"),
    )
    db.commit()
    cur.close()

    for msg in errs:
        flash(msg, "warning")
    flash("Ticket submitted.", "success")
    return redirect(url_for("user.ticket_detail", ticket_id=ticket_id))
