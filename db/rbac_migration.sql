-- Run once on an existing `service_desk` DB to add RBAC (safe to re-run where noted).

CREATE TABLE IF NOT EXISTS permissions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(64) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id INT NOT NULL,
    permission_id INT NOT NULL,
    PRIMARY KEY (role_id, permission_id),
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
);

UPDATE roles SET role_name = 'technician' WHERE role_name = 'agent';

INSERT INTO roles (role_name)
SELECT 'technician' FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE role_name = 'technician');

INSERT INTO permissions (code)
SELECT 'dashboard.admin' FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'dashboard.admin');
INSERT INTO permissions (code)
SELECT 'tickets.view_all' FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'tickets.view_all');
INSERT INTO permissions (code)
SELECT 'tickets.edit_any' FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'tickets.edit_any');
INSERT INTO permissions (code)
SELECT 'tickets.delete' FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'tickets.delete');
INSERT INTO permissions (code)
SELECT 'users.manage' FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'users.manage');
INSERT INTO permissions (code)
SELECT 'api.tickets' FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'api.tickets');
INSERT INTO permissions (code)
SELECT 'api.reports' FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'api.reports');

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
WHERE r.role_name = 'admin'
AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp2 WHERE rp2.role_id = r.id AND rp2.permission_id = p.id
);

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r
JOIN permissions p ON p.code IN (
    'dashboard.admin',
    'tickets.view_all',
    'tickets.edit_any'
)
WHERE r.role_name = 'technician'
AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp2 WHERE rp2.role_id = r.id AND rp2.permission_id = p.id
);

-- Statistics JSON API: admin only (revoke if previously granted to technicians)
DELETE rp FROM role_permissions rp
INNER JOIN roles r ON rp.role_id = r.id
INNER JOIN permissions p ON rp.permission_id = p.id
WHERE r.role_name IN ('technician', 'agent')
  AND p.code IN ('api.tickets', 'api.reports');
