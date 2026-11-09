"""acceso al panel por usuario: registro con aprobación, permisos por módulo y bloqueo

- Agrega a users: full_name, status (pending | active | disabled), is_superadmin,
  permissions (lista JSON de módulos), created_at, approved_at, approved_by_id,
  last_login_at, failed_login_attempts, locked_until y password_changed_at.
- Las cuentas que ya existían quedan activas; las que tenían rol "admin" (todas,
  hasta ahora) quedan como superadministradores con todos los módulos, así nadie
  pierde el acceso que ya tenía.
- Borra los tokens de recuperación pendientes: antes se guardaban en claro y ahora
  se guarda solo su hash.

Es seguro aplicarla antes de desplegar el código nuevo: todas las columnas nuevas
tienen valor por defecto en la base de datos.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20261107_0001'
down_revision = '20261019_0001'
branch_labels = None
depends_on = None

ALL_MODULES = '["programs", "students", "groups", "assignments", "reports", "users"]'


def upgrade() -> None:
    op.add_column('users', sa.Column('full_name', sa.String(120), nullable=True))
    op.add_column('users', sa.Column('status', sa.String(20), nullable=False, server_default='pending'))
    op.add_column('users', sa.Column('is_superadmin', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('permissions', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column('users', sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()))
    op.add_column('users', sa.Column('approved_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('approved_by_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('password_changed_at', sa.DateTime(), nullable=True))
    op.create_foreign_key(
        'users_approved_by_id_fkey', 'users', 'users', ['approved_by_id'], ['id'], ondelete='SET NULL'
    )
    op.create_index('ix_users_status', 'users', ['status'])

    bind = op.get_bind()
    # Quienes ya usaban el panel conservan su acceso
    bind.execute(sa.text("UPDATE users SET status = 'active', approved_at = now()"))
    bind.execute(sa.text(
        f"UPDATE users SET is_superadmin = true, permissions = '{ALL_MODULES}' WHERE role = 'admin'"
    ))
    # Los tokens de recuperación anteriores estaban en claro: se invalidan
    bind.execute(sa.text("UPDATE users SET reset_token = NULL, reset_token_expires = NULL"))

    total = bind.execute(sa.text("SELECT count(*) FROM users WHERE is_superadmin")).scalar()
    print(f"Usuarios existentes convertidos en superadministradores: {total}")


def downgrade() -> None:
    op.drop_index('ix_users_status', table_name='users')
    op.drop_constraint('users_approved_by_id_fkey', 'users', type_='foreignkey')
    for column in (
        'password_changed_at', 'locked_until', 'failed_login_attempts', 'last_login_at',
        'approved_by_id', 'approved_at', 'created_at', 'permissions', 'is_superadmin',
        'status', 'full_name',
    ):
        op.drop_column('users', column)
