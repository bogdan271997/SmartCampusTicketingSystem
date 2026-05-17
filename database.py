from __future__ import annotations

from pathlib import Path

import pymysql
import pymysql.err
from werkzeug.security import generate_password_hash

# Shared connection; route modules import this instead of `app` to avoid import cycles.

db = pymysql.connect(
    host="localhost",
    user="flaskuser",
    password="password123",
    database="service_desk",
    cursorclass=pymysql.cursors.Cursor,
    autocommit=False,
)

_BUILTIN_ACCOUNTS = (
    # (email, display_name, roles.role_name)
    ("admin@mail.com", "Admin", "admin"),
    ("service.desk@mail.com", "Service desk technician", "technician"),
)


def _schema_sql_path() -> Path:
    return Path(__file__).resolve().parent / "db" / "schema.sql"


def init_schema_if_needed() -> None:
    """Apply db/schema.sql when the database is empty; safe on a fresh MySQL database."""
    cur = db.cursor()
    try:
        cur.execute("SHOW TABLES")
        tables = {row[0] for row in cur.fetchall()}
        if "users" in tables:
            return
        if tables:
            raise RuntimeError(
                "Database 'service_desk' has tables but no 'users' table. "
                "Fix with: mysql -u YOUR_USER -p service_desk < db/schema.sql "
                "(or drop the database and recreate it)."
            )
    finally:
        cur.close()

    path = _schema_sql_path()
    if not path.is_file():
        raise FileNotFoundError(f"Schema file not found: {path}")

    raw = path.read_text(encoding="utf-8")
    # Drop full-line SQL comments (this file only uses -- at line start).
    lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("--")]
    script = "\n".join(lines)
    statements = [s.strip() for s in script.split(";") if s.strip()]
    for stmt in statements:
        cur = db.cursor()
        try:
            cur.execute(stmt)
        finally:
            cur.close()
    db.commit()


def apply_schema_patches() -> None:
    """Idempotent upgrades for DBs created before `resolution`, Pending status, etc."""
    cur = db.cursor()
    try:
        cur.execute("SHOW TABLES LIKE 'tickets'")
        if not cur.fetchone():
            return

        cur.execute(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'tickets'
              AND COLUMN_NAME = 'resolution'
            """
        )
        if cur.fetchone()[0] == 0:
            try:
                cur.execute("ALTER TABLE tickets ADD COLUMN resolution TEXT NULL")
                db.commit()
            except pymysql.err.OperationalError as exc:
                db.rollback()
                if exc.args[0] != 1060:
                    raise

        cur.execute(
            "SELECT COUNT(*) FROM ticket_status WHERE status_name = %s", ("Pending",)
        )
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO ticket_status (status_name) VALUES (%s)", ("Pending",)
            )
            db.commit()

        cur.execute(
            """
            DELETE rp FROM role_permissions rp
            INNER JOIN roles r ON rp.role_id = r.id
            INNER JOIN permissions p ON rp.permission_id = p.id
            WHERE r.role_name IN ('technician', 'agent')
              AND p.code IN ('api.tickets', 'api.reports')
            """
        )
        db.commit()

        cur.execute("SHOW TABLES LIKE 'ticket_attachments'")
        if not cur.fetchone():
            cur.execute(
                """
                CREATE TABLE ticket_attachments (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    ticket_id INT NOT NULL,
                    comment_id INT NULL,
                    kind VARCHAR(20) NOT NULL,
                    stored_path VARCHAR(512) NOT NULL,
                    original_name VARCHAR(255) NOT NULL,
                    content_type VARCHAR(128) NULL,
                    file_size INT NULL,
                    uploaded_by INT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
                    FOREIGN KEY (comment_id) REFERENCES comments(id) ON DELETE CASCADE,
                    FOREIGN KEY (uploaded_by) REFERENCES users(id)
                )
                """
            )
            db.commit()
    finally:
        cur.close()


def seed_builtin_users() -> None:
    """Create default admin and service-desk technician logins if missing (password: 1234 for both)."""
    pw_hash = generate_password_hash("1234")
    cur = db.cursor()
    try:
        for email, name, role_name in _BUILTIN_ACCOUNTS:
            cur.execute("SELECT id FROM users WHERE email = %s LIMIT 1", (email,))
            if cur.fetchone():
                continue
            cur.execute(
                "SELECT id FROM roles WHERE role_name = %s LIMIT 1",
                (role_name,),
            )
            row = cur.fetchone()
            if not row:
                continue
            role_id = int(row[0])
            try:
                cur.execute(
                    """
                    INSERT INTO users (name, email, password_hash, role_id)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (name, email, pw_hash, role_id),
                )
                db.commit()
            except pymysql.err.IntegrityError:
                db.rollback()
    finally:
        cur.close()
