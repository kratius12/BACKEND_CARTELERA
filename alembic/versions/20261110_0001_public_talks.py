"""conferencias: conferenciantes que vienen y que van, por mes

- talk_outlines: catálogo de bosquejos (número → título), se llena solo con el uso.
- local_speakers: conferenciantes de la congregación (estudiantes) con su teléfono.
- speaker_outlines: bosquejos que puede presentar cada conferenciante local.
- public_talks: cada conferencia (incoming = viene, outgoing = va) con fecha,
  congregación, conferenciante, teléfono, bosquejo, título e imágenes.

Solo crea tablas nuevas: es segura antes de desplegar el código nuevo.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20261110_0001'
down_revision = '20261107_0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'talk_outlines',
        sa.Column('number', sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        'local_speakers',
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('phone', sa.String(30), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        'speaker_outlines',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('local_speakers.student_id', ondelete='CASCADE'), nullable=False),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('has_images', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint('student_id', 'number', name='uq_speaker_outlines_student_number'),
    )
    op.create_index('ix_speaker_outlines_id', 'speaker_outlines', ['id'])
    op.create_index('ix_speaker_outlines_student_id', 'speaker_outlines', ['student_id'])
    op.create_table(
        'public_talks',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('direction', sa.String(10), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('congregation', sa.String(120), nullable=False),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='SET NULL'), nullable=True),
        sa.Column('speaker_name', sa.String(150), nullable=False),
        sa.Column('phone', sa.String(30), nullable=True),
        sa.Column('outline_number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('has_images', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("direction IN ('incoming', 'outgoing')", name='ck_public_talks_direction'),
    )
    op.create_index('ix_public_talks_id', 'public_talks', ['id'])
    op.create_index('ix_public_talks_direction', 'public_talks', ['direction'])
    op.create_index('ix_public_talks_date', 'public_talks', ['date'])


def downgrade() -> None:
    op.drop_index('ix_public_talks_date', table_name='public_talks')
    op.drop_index('ix_public_talks_direction', table_name='public_talks')
    op.drop_index('ix_public_talks_id', table_name='public_talks')
    op.drop_table('public_talks')
    op.drop_index('ix_speaker_outlines_student_id', table_name='speaker_outlines')
    op.drop_index('ix_speaker_outlines_id', table_name='speaker_outlines')
    op.drop_table('speaker_outlines')
    op.drop_table('local_speakers')
    op.drop_table('talk_outlines')
