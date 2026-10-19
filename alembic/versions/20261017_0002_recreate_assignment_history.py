"""recreate assignment_history (historial de asignaciones)

La migración inicial (874d59875fa5) borra la tabla assignment_history y ninguna
migración la volvía a crear. Sin ella, publicar o editar un programa publicado
falla con: relation "assignment_history" does not exist.

Esta migración:
1. Si meeting_programs.id no tiene llave primaria (pasa en bases copiadas sin
   restricciones), se la agrega, siempre que no haya ids repetidos ni vacíos.
2. Crea assignment_history si falta.
3. La reconstruye a partir de los programas ya publicados, con la misma lógica
   que usa la app al publicar (app/crud/program.py -> _sync_assignment_history).
"""
import json

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20261017_0002'
down_revision = '20261017_0001'
branch_labels = None
depends_on = None


def _clean_name(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or "❌" in value:
        return None
    return value[:150]


def _history_rows(program_id, week_start, payload):
    """Igual que _sync_assignment_history: una fila por punto con persona asignada."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            return []
    if not isinstance(payload, dict):
        return []

    rows = []
    for part in payload.get("parts") or []:
        if not isinstance(part, dict) or part.get("type") != "section":
            continue
        for item in part.get("items") or []:
            if not isinstance(item, dict):
                continue
            assigned = item.get("assigned") or []
            if not isinstance(assigned, list):
                continue
            title = (item.get("text") or "").lower()
            is_demo = "empiece" in title or "haga" in title or "explique" in title
            student = _clean_name(assigned[0]) if len(assigned) > 0 else None
            assistant = _clean_name(assigned[1]) if len(assigned) > 1 else None
            if not student:
                continue
            rows.append({
                "program_id": program_id,
                "week_start": week_start,
                "student_name": student,
                "assistant_name": assistant,
                "part_type": "demostracion" if is_demo else "discurso",
            })
    return rows


def _id_is_unique(bind) -> bool:
    """¿meeting_programs.id tiene llave primaria o índice único (lo que exige una FK)?"""
    return bind.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = i.indkey[0]
            WHERE i.indrelid = 'meeting_programs'::regclass
              AND i.indisunique AND i.indnatts = 1 AND i.indpred IS NULL
              AND a.attname = 'id'
        )
    """)).scalar()


def _ensure_meeting_programs_pk(bind) -> bool:
    """Agrega la llave primaria a meeting_programs.id si falta y es seguro. Devuelve True si queda única."""
    if _id_is_unique(bind):
        return True

    nulls = bind.execute(sa.text("SELECT count(*) FROM meeting_programs WHERE id IS NULL")).scalar()
    dups = bind.execute(sa.text(
        "SELECT id FROM meeting_programs WHERE id IS NOT NULL GROUP BY id HAVING count(*) > 1 ORDER BY id"
    )).scalars().all()
    if nulls or dups:
        print(
            "AVISO: meeting_programs.id no tiene llave primaria y no se puede agregar "
            f"(ids vacíos: {nulls}, ids repetidos: {dups}). "
            "Se crea assignment_history sin la relación con meeting_programs."
        )
        return False

    name = "meeting_programs_pkey"
    if bind.execute(sa.text("SELECT to_regclass(:n) IS NOT NULL"), {"n": name}).scalar():
        name = "meeting_programs_id_pkey"
    op.execute(f'ALTER TABLE meeting_programs ADD CONSTRAINT "{name}" PRIMARY KEY (id)')
    print(f"meeting_programs: se agregó la llave primaria en id ({name}).")
    return True


def upgrade() -> None:
    bind = op.get_bind()
    if 'assignment_history' in sa.inspect(bind).get_table_names():
        return

    with_fk = _ensure_meeting_programs_pk(bind)

    columns = [
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('program_id', sa.Integer(), nullable=False),
        sa.Column('week_start', sa.Date(), nullable=False),
        sa.Column('student_name', sa.String(length=150), nullable=False),
        sa.Column('assistant_name', sa.String(length=150), nullable=True),
        sa.Column('part_type', sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    ]
    if with_fk:
        columns.append(sa.ForeignKeyConstraint(['program_id'], ['meeting_programs.id'], ondelete='CASCADE'))
    op.create_table('assignment_history', *columns)
    op.create_index(op.f('ix_assignment_history_id'), 'assignment_history', ['id'], unique=False)

    # Reconstruir el historial desde los programas publicados
    programs = bind.execute(
        sa.text("SELECT id, week_start, payload FROM meeting_programs ORDER BY id")
    ).fetchall()
    rows = []
    for program_id, week_start, payload in programs:
        rows.extend(_history_rows(program_id, week_start, payload))

    if rows:
        history = sa.table(
            'assignment_history',
            sa.column('program_id', sa.Integer),
            sa.column('week_start', sa.Date),
            sa.column('student_name', sa.String),
            sa.column('assistant_name', sa.String),
            sa.column('part_type', sa.String),
        )
        op.bulk_insert(history, rows)
    print(f"assignment_history: tabla creada y {len(rows)} filas reconstruidas desde {len(programs)} programas publicados.")


def downgrade() -> None:
    # La llave primaria de meeting_programs se deja: corresponde a lo que define el modelo.
    op.drop_index(op.f('ix_assignment_history_id'), table_name='assignment_history')
    op.drop_table('assignment_history')
