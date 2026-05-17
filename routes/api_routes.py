from flask import Blueprint, jsonify, request, session

from database import db
from permissions import (
    API_REPORTS,
    API_TICKETS,
    parse_optional_status_filter,
    session_has,
)

api_bp = Blueprint("api", __name__)


def _json_forbidden():
    return jsonify({"error": "Forbidden"}), 403


def _json_unauthorized():
    return jsonify({"error": "Unauthorized"}), 401


@api_bp.route("/api/tickets")
def api_tickets():
    if "user_id" not in session:
        return _json_unauthorized()
    if not session_has(session, API_TICKETS):
        return _json_forbidden()

    status_name = parse_optional_status_filter(request.args.get("status"))
    where = ""
    params: tuple = ()
    if status_name:
        where = " WHERE ticket_status.status_name = %s"
        params = (status_name,)

    cur = db.cursor()
    try:
        sql = f"""
            SELECT tickets.id,
                   tickets.title,
                   tickets.description,
                   tickets.priority,
                   tickets.created_at,
                   ticket_status.id,
                   ticket_status.status_name,
                   creator.name,
                   creator.email,
                   assignee.name
            FROM tickets
            JOIN ticket_status ON tickets.status_id = ticket_status.id
            LEFT JOIN users AS creator ON tickets.created_by = creator.id
            LEFT JOIN users AS assignee ON tickets.assigned_to = assignee.id
            {where}
            ORDER BY tickets.created_at DESC
        """
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        rows = cur.fetchall()
    except Exception as exc:
        cur.close()
        return jsonify({"error": str(exc)}), 500
    cur.close()

    payload = []
    for r in rows:
        created = r[4]
        if hasattr(created, "isoformat"):
            created = created.isoformat()
        payload.append(
            {
                "id": r[0],
                "title": r[1],
                "description": r[2],
                "priority": r[3] or "Medium",
                "created_at": created,
                "status_id": r[5],
                "status": r[6],
                "created_by_name": r[7] or "—",
                "created_by_email": r[8],
                "assigned_to_name": r[9],
            }
        )

    return jsonify(payload), 200


@api_bp.route("/api/reports/summary")
def api_report_summary():
    if "user_id" not in session:
        return _json_unauthorized()
    if not session_has(session, API_REPORTS):
        return _json_forbidden()

    status_name = parse_optional_status_filter(request.args.get("status"))
    where = ""
    params: tuple = ()
    if status_name:
        where = " WHERE ticket_status.status_name = %s"
        params = (status_name,)

    cur = db.cursor()
    sql = f"""
        SELECT ticket_status.status_name, COUNT(*)
        FROM tickets
        JOIN ticket_status ON tickets.status_id = ticket_status.id
        {where}
        GROUP BY ticket_status.status_name
    """
    if params:
        cur.execute(sql, params)
    else:
        cur.execute(sql)
    rows = cur.fetchall()
    cur.close()

    return jsonify([{"status": r[0], "count": r[1]} for r in rows]), 200
