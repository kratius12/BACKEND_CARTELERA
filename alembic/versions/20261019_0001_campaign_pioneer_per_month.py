"""precursorado del mes en los informes; la campaña deja de ser fija

- Agrega preaching_reports.pioneer_status (regular | aux_ind | aux_camp | NULL):
  el precursorado de ESE mes. Así "auxiliar en campaña" queda solo en el mes en
  que se asigna.
- Llena pioneer_status de los informes que ya estaban guardados.
- Quita la marca fija es_precursor_aux_camp de Estudiantes (la columna se queda,
  pero ya no se usa) e imprime a quién se la quitó y si ya tiene un mes asignado.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20261019_0001'
down_revision = '20261018_0001'
branch_labels = None
depends_on = None

MONTHS = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def _month_label(d) -> str:
    return f"{MONTHS[d.month - 1]} {d.year}"


def upgrade() -> None:
    bind = op.get_bind()
    cols = [c['name'] for c in sa.inspect(bind).get_columns('preaching_reports')]
    if 'pioneer_status' not in cols:
        op.add_column('preaching_reports', sa.Column('pioneer_status', sa.String(10), nullable=True))

    # Informes ya guardados: el auxiliar es indefinido si así está en Estudiantes; si no, de campaña
    bind.execute(sa.text("""
        UPDATE preaching_reports r SET pioneer_status = CASE
            WHEN r.publisher_type = 'regular' THEN 'regular'
            WHEN r.publisher_type = 'auxiliar' AND s.es_precursor_aux_ind THEN 'aux_ind'
            WHEN r.publisher_type = 'auxiliar' THEN 'aux_camp'
            ELSE NULL END
        FROM students s
        WHERE s.id = r.student_id AND r.pioneer_status IS NULL
    """))

    # La campaña ya no es fija: se quita de Estudiantes (los meses ya guardados la conservan)
    campaign = bind.execute(sa.text("""
        SELECT s.id, s.name FROM students s WHERE s.es_precursor_aux_camp ORDER BY s.name
    """)).fetchall()
    months_by_student = {}
    if campaign:
        for student_id, month in bind.execute(sa.text("""
            SELECT student_id, month FROM preaching_reports
            WHERE pioneer_status = 'aux_camp' AND student_id = ANY(:ids)
            ORDER BY month
        """), {"ids": [c[0] for c in campaign]}).fetchall():
            months_by_student.setdefault(student_id, []).append(_month_label(month))
        bind.execute(sa.text("UPDATE students SET es_precursor_aux_camp = FALSE WHERE es_precursor_aux_camp"))

    print("\nAuxiliar en campaña: ahora es solo del mes en que se asigna (en Informes de predicación).")
    if not campaign:
        print("  Nadie tenía la campaña marcada como fija en Estudiantes.")
    else:
        print(f"  Se quitó la campaña fija de Estudiantes a {len(campaign)} persona(s):")
        for student_id, name in campaign:
            months = months_by_student.get(student_id)
            if months:
                print(f"    - {name}: queda como campaña en {', '.join(months)}")
            else:
                print(f"    - {name}: no tenía un mes asignado. Asígnale la campaña en el mes que corresponda.")
    print()


def downgrade() -> None:
    op.drop_column('preaching_reports', 'pioneer_status')
