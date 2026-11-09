"""sonido: audio y video, micrófonos y Zoom por semana

- Agrega a students los permisos sonido_audio_video, sonido_microfonos y sonido_zoom
  (por defecto false).
- Crea sound_assignments: una fila por semana, del sábado (date) a la reunión de entre
  semana siguiente (midweek_date), con una persona por columna.

No carga historial. Es segura antes de desplegar el código nuevo: las columnas nuevas
tienen valor por defecto y la tabla nueva no la usa el código anterior.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20261107_0003'
down_revision = '20261107_0002'
branch_labels = None
depends_on = None

FLAGS = ('sonido_audio_video', 'sonido_microfonos', 'sonido_zoom')
ROLES = ('audio', 'micro', 'zoom')


def upgrade() -> None:
    for flag in FLAGS:
        op.add_column('students', sa.Column(flag, sa.Boolean(), nullable=False, server_default=sa.false()))

    columns = [
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('midweek_date', sa.Date(), nullable=False),
    ]
    for role in ROLES:
        columns.append(sa.Column(f'{role}_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='SET NULL'), nullable=True))
        columns.append(sa.Column(f'{role}_name', sa.String(150), nullable=True))
    columns += [
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('date', name='uq_sound_assignments_date'),
        sa.CheckConstraint('EXTRACT(ISODOW FROM date) = 6', name='ck_sound_assignments_sabado'),
        sa.CheckConstraint('midweek_date > date AND midweek_date <= date + 6', name='ck_sound_assignments_entre_semana'),
    ]
    op.create_table('sound_assignments', *columns)
    op.create_index('ix_sound_assignments_id', 'sound_assignments', ['id'])


def downgrade() -> None:
    op.drop_index('ix_sound_assignments_id', table_name='sound_assignments')
    op.drop_table('sound_assignments')
    for flag in reversed(FLAGS):
        op.drop_column('students', flag)
