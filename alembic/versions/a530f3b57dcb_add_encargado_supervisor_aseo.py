"""add_encargado_supervisor_aseo

Revision ID: a530f3b57dcb
Revises: e0ba195c73fb
Create Date: 2026-04-24 20:21:15.475005

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a530f3b57dcb'
down_revision: Union[str, Sequence[str], None] = 'e0ba195c73fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = [c['name'] for c in inspector.get_columns('historial_emparejamientos')]
    existing_fk_cols = [
        col
        for fk in inspector.get_foreign_keys('historial_emparejamientos')
        for col in fk['constrained_columns']
    ]

    if 'encargado_id' not in existing_cols:
        op.add_column('historial_emparejamientos', sa.Column('encargado_id', sa.Integer(), nullable=True))
    if 'encargado_id' not in existing_fk_cols:
        op.create_foreign_key(None, 'historial_emparejamientos', 'students', ['encargado_id'], ['id'])

    if 'supervisor_id' not in existing_cols:
        op.add_column('historial_emparejamientos', sa.Column('supervisor_id', sa.Integer(), nullable=True))
    if 'supervisor_id' not in existing_fk_cols:
        op.create_foreign_key(None, 'historial_emparejamientos', 'students', ['supervisor_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(None, 'historial_emparejamientos', type_='foreignkey')
    op.drop_constraint(None, 'historial_emparejamientos', type_='foreignkey')
    op.drop_column('historial_emparejamientos', 'supervisor_id')
    op.drop_column('historial_emparejamientos', 'encargado_id')
