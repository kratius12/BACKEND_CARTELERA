"""conferencias: número de canción por bosquejo

- speaker_outlines.song: canción que usa el conferenciante local con ese bosquejo.
- public_talks.song: canción de cada conferencia (la escribe el visitante o sale del
  bosquejo del hermano que va).

Columnas opcionales (las filas existentes quedan sin canción): es segura antes de
desplegar el código nuevo.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20261110_0002'
down_revision = '20261110_0001'
branch_labels = None
depends_on = None

TABLES = ('speaker_outlines', 'public_talks')


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column('song', sa.SmallInteger(), nullable=True))
        op.create_check_constraint(f'ck_{table}_song', table, 'song IS NULL OR song BETWEEN 1 AND 999')


def downgrade() -> None:
    for table in TABLES:
        op.drop_constraint(f'ck_{table}_song', table, type_='check')
        op.drop_column(table, 'song')
