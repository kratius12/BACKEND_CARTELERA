"""add group_report_links (link secreto de informes por grupo)

Una fila por grupo con un código aleatorio. Con ese link el encargado del grupo
ve y llena los informes de predicación de su grupo sin iniciar sesión.
Solo crea una tabla nueva; no toca ninguna tabla existente.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20261017_0003'
down_revision = '20261017_0002'
branch_labels = None
depends_on = None


def _groups_id_is_unique(bind) -> bool:
    """¿groups.id tiene llave primaria o índice único? (lo exige la relación)"""
    return bind.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = i.indkey[0]
            WHERE i.indrelid = 'groups'::regclass
              AND i.indisunique AND i.indnatts = 1 AND i.indpred IS NULL
              AND a.attname = 'id'
        )
    """)).scalar()


def upgrade() -> None:
    bind = op.get_bind()
    if 'group_report_links' in sa.inspect(bind).get_table_names():
        return

    columns = [
        sa.Column('group_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('group_id'),
    ]
    if _groups_id_is_unique(bind):
        columns.append(sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'))
    else:
        print("AVISO: groups.id no tiene llave primaria; group_report_links se crea sin la relación con groups.")

    op.create_table('group_report_links', *columns)
    op.create_index(op.f('ix_group_report_links_token'), 'group_report_links', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_group_report_links_token'), table_name='group_report_links')
    op.drop_table('group_report_links')
