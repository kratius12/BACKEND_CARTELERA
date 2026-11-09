CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    full_name VARCHAR(120),
    hashed_password VARCHAR NOT NULL,
    role VARCHAR NOT NULL DEFAULT 'user',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    is_superadmin BOOLEAN NOT NULL DEFAULT false,
    permissions JSON NOT NULL DEFAULT '[]',
    created_at TIMESTAMP DEFAULT now(),
    approved_at TIMESTAMP,
    approved_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    last_login_at TIMESTAMP,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMP,
    password_changed_at TIMESTAMP,
    reset_token VARCHAR,
    reset_token_expires TIMESTAMP
);

-- Primer superadministrador (cámbiale la contraseña al entrar: menú de usuario → Cambiar contraseña)
INSERT INTO users (email, full_name, hashed_password, role, status, is_superadmin, permissions, approved_at)
VALUES (
    'admin@example.com',
    'Administrador',
    crypt('secureAdminPassword123', gen_salt('bf')),
    'admin',
    'active',
    true,
    '["programs", "students", "groups", "assignments", "weekend", "sound", "reports", "users"]',
    now()
)
ON CONFLICT (email) DO NOTHING;
