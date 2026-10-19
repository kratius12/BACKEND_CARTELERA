"""add preaching_reports table (Informes de predicación)

Una fila por persona y mes: tipo de publicador (publicador / auxiliar / regular),
participación (SP/NP), horas, estudios, servicio sagrado y observaciones.
Solo crea una tabla nueva; no toca ninguna tabla existente.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20261017_0001'
down_revision = '20260714_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if 'preaching_reports' in sa.inspect(bind).get_table_names():
        return

    op.create_table(
        'preaching_reports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('month', sa.Date(), nullable=False),
        sa.Column('publisher_type', sa.String(length=20), server_default='publicador', nullable=False),
        sa.Column('participated', sa.Boolean(), nullable=True),
        sa.Column('hours', sa.Integer(), nullable=True),
        sa.Column('bible_studies', sa.Integer(), nullable=True),
        sa.Column('sacred_service_hours', sa.Integer(), nullable=True),
        sa.Column('observations', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('student_id', 'month', name='uq_preaching_reports_student_month'),
    )
    op.create_index(op.f('ix_preaching_reports_id'), 'preaching_reports', ['id'], unique=False)
    op.create_index(op.f('ix_preaching_reports_student_id'), 'preaching_reports', ['student_id'], unique=False)
    op.create_index(op.f('ix_preaching_reports_month'), 'preaching_reports', ['month'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_preaching_reports_month'), table_name='preaching_reports')
    op.drop_index(op.f('ix_preaching_reports_student_id'), table_name='preaching_reports')
    op.drop_index(op.f('ix_preaching_reports_id'), table_name='preaching_reports')
    op.drop_table('preaching_reports')
