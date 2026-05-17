-- Run once against `service_desk` to add more workflow statuses (safe if re-run).
INSERT INTO ticket_status (status_name)
SELECT 'On hold' FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM ticket_status WHERE status_name = 'On hold');

INSERT INTO ticket_status (status_name)
SELECT 'Cancelled' FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM ticket_status WHERE status_name = 'Cancelled');
