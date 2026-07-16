"""add es_anciano and es_siervo boolean fields to students

Replaces the fragile text-search on infoadd with explicit boolean columns.
The data migration populates them from any existing infoadd values.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260714_0001'
down_revision = '84f004c5c0ca'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_cols = [c['name'] for c in sa.inspect(bind).get_columns('students')]

    if 'es_anciano' not in existing_cols:
        op.add_column(
            'students',
            sa.Column('es_anciano', sa.Boolean(), nullable=False, server_default=sa.false())
        )
        op.execute("""
            UPDATE students
            SET es_anciano = TRUE
            WHERE infoadd IS NOT NULL AND UPPER(infoadd) LIKE '%ANCIANO%'
        """)

    if 'es_siervo' not in existing_cols:
        op.add_column(
            'students',
            sa.Column('es_siervo', sa.Boolean(), nullable=False, server_default=sa.false())
        )
        op.execute("""
            UPDATE students
            SET es_siervo = TRUE
            WHERE infoadd IS NOT NULL AND UPPER(infoadd) LIKE '%SIERVO%'
        """)


def downgrade() -> None:
    op.drop_column('students', 'es_siervo')
    op.drop_column('students', 'es_anciano')
