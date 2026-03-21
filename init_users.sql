CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR NOT NULL,
    role VARCHAR NOT NULL DEFAULT 'admin',
    reset_token VARCHAR,
    reset_token_expires TIMESTAMP
);

INSERT INTO users (email, hashed_password, role) 
VALUES ('admin@example.com', crypt('secureAdminPassword123', gen_salt('bf')), 'admin')
ON CONFLICT (email) DO NOTHING;
