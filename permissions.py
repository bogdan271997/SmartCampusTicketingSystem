"""Permission codes and helpers; aligns with `permissions` / `role_permissions` tables."""

from __future__ import annotations

from typing import Iterable

from database import db

# Seeded in db/schema.sql — keep in sync
DASHBOARD_ADMIN = "dashboard.admin"
TICKETS_VIEW_ALL = "tickets.view_all"
TICKETS_EDIT_ANY = "tickets.edit_any"
TICKETS_DELETE = "tickets.delete"
USERS_MANAGE = "users.manage"
API_TICKETS = "api.tickets"
API_REPORTS = "api.reports"

ALL_CODES: tuple[str, ...] = (
    DASHBOARD_ADMIN,
    TICKETS_VIEW_ALL,
    TICKETS_EDIT_ANY,
    TICKETS_DELETE,
    USERS_MANAGE,
    API_TICKETS,
    API_REPORTS,
)


def fetch_permissions_for_role(role_id: int | None) -> list[str]:
    if not role_id:
        return []
    cur = db.cursor()
    cur.execute(
        """
        SELECT p.code
        FROM permissions p
        JOIN role_permissions rp ON rp.permission_id = p.id
        WHERE rp.role_id = %s
        ORDER BY p.code
        """,
        (role_id,),
    )
    rows = cur.fetchall()
    cur.close()
    return [r[0] for r in rows]


def role_has_permission(role_id: int | None, code: str) -> bool:
    if not role_id:
        return False
    cur = db.cursor()
    cur.execute(
        """
        SELECT 1
        FROM role_permissions rp
        JOIN permissions p ON p.id = rp.permission_id
        WHERE rp.role_id = %s AND p.code = %s
        LIMIT 1
        """,
        (role_id, code),
    )
    ok = cur.fetchone() is not None
    cur.close()
    return ok


def fetch_all_roles() -> list[tuple[int, str]]:
    cur = db.cursor()
    cur.execute(
        """
        SELECT id, role_name FROM roles ORDER BY id
        """
    )
    rows = cur.fetchall()
    cur.close()
    return [(int(r[0]), str(r[1])) for r in rows]


def fetch_ticket_status_names() -> list[str]:
    """Ordered status labels for filter dropdowns."""
    cur = db.cursor()
    cur.execute("SELECT status_name FROM ticket_status ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    return [str(r[0]) for r in rows]


def parse_optional_status_filter(raw: str | None) -> str | None:
    """Validate ?status= query against `ticket_status.status_name` (exact match)."""
    if not raw:
        return None
    name = raw.strip()
    if not name:
        return None
    cur = db.cursor()
    cur.execute(
        "SELECT status_name FROM ticket_status WHERE status_name = %s LIMIT 1",
        (name,),
    )
    row = cur.fetchone()
    cur.close()
    return str(row[0]) if row else None


def fetch_users_for_assignment() -> list[tuple[int, str, str, str]]:
    """Users who may appear in an 'assign to' list: id, name, email, role_name."""
    cur = db.cursor()
    cur.execute(
        """
        SELECT users.id, users.name, users.email, COALESCE(roles.role_name, 'user')
        FROM users
        LEFT JOIN roles ON users.role_id = roles.id
        ORDER BY users.name
        """
    )
    rows = cur.fetchall()
    cur.close()
    return [(int(r[0]), str(r[1]), str(r[2]), str(r[3])) for r in rows]


def fetch_default_user_role_id() -> int | None:
    cur = db.cursor()
    cur.execute(
        "SELECT id FROM roles WHERE role_name = %s LIMIT 1",
        ("user",),
    )
    row = cur.fetchone()
    cur.close()
    return int(row[0]) if row else None


def session_has(session: dict, code: str) -> bool:
    perms: Iterable[str] | None = session.get("permissions")
    if not perms:
        return False
    return code in perms


def session_has_any(session: dict, *codes: str) -> bool:
    perms: Iterable[str] | None = session.get("permissions")
    if not perms:
        return False
    return any(c in perms for c in codes)
