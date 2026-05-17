-- Optional manual patch: revoke statistics API from service-desk roles (admin keeps it).

DELETE rp FROM role_permissions rp
INNER JOIN roles r ON rp.role_id = r.id
INNER JOIN permissions p ON rp.permission_id = p.id
WHERE r.role_name IN ('technician', 'agent')
  AND p.code IN ('api.tickets', 'api.reports');
