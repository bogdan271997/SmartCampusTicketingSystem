-- Smart Campus Service Desk: example JOIN queries for coursework documentation.
-- Run against database: service_desk

-- 1. Tickets with status and submitter (admin queue pattern)
SELECT tickets.id,
       tickets.title,
       users.name        AS submitted_by,
       ticket_status.status_name
FROM tickets
         JOIN users ON tickets.created_by = users.id
         JOIN ticket_status ON tickets.status_id = ticket_status.id
ORDER BY tickets.created_at DESC;

-- 2. Users with role label (Team & roles screen pattern)
SELECT users.id,
       users.name,
       users.email,
       COALESCE(roles.role_name, 'user') AS role_name
FROM users
         LEFT JOIN roles ON users.role_id = roles.id
ORDER BY users.id;

-- 3. Report summary: ticket counts by status (API /reports/summary pattern)
SELECT ticket_status.status_name,
       COUNT(*) AS count
FROM tickets
         JOIN ticket_status ON tickets.status_id = ticket_status.id
GROUP BY ticket_status.status_name;
