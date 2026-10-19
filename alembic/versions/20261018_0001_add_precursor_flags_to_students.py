"""add precursorado flags to students

Agrega a students:
  es_precursor_aux_camp  -> precursor auxiliar en campaña
  es_precursor_aux_ind   -> precursor auxiliar indefinido
  es_precursor_reg       -> precursor regular
con la regla de que como mucho uno esté marcado.

Igual que con es_anciano / es_siervo, los llena a partir del texto de
"Información adicional" (infoadd) e imprime a quién marcó y a quién conviene
revisar a mano en Estudiantes.
"""
import re
import unicodedata

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20261018_0001'
down_revision = '20261017_0003'
branch_labels = None
depends_on = None

FLAGS = ('es_precursor_aux_camp', 'es_precursor_aux_ind', 'es_precursor_reg')
CHECK_NAME = 'ck_students_un_solo_precursorado'


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).upper()


def _classify(infoadd: str):
    """Devuelve la columna a marcar, 'revisar' si es ambiguo, o None si no habla de precursorado."""
    t = _normalize(infoadd)
    if not re.search(r"PRECURSOR|PIONER|\bP\s*\.?\s*(REG|AUX)", t):
        return None
    if "REG" in t:
        return 'es_precursor_reg'
    if "INDEF" in t:
        return 'es_precursor_aux_ind'
    if "CAMP" in t:
        return 'es_precursor_aux_camp'
    if "AUX" in t:
        return 'revisar'  # auxiliar, pero no dice si es en campaña o indefinido
    return 'es_precursor_reg'  # "Precursor" / "Pionero" a secas


def upgrade() -> None:
    bind = op.get_bind()
    existing_cols = [c['name'] for c in sa.inspect(bind).get_columns('students')]

    for col in FLAGS:
        if col not in existing_cols:
            op.add_column('students', sa.Column(col, sa.Boolean(), nullable=False, server_default=sa.false()))

    # Llenar desde "Información adicional" (solo a quien todavía no tiene ninguna marca)
    rows = bind.execute(sa.text(f"""
        SELECT id, name, infoadd FROM students
        WHERE infoadd IS NOT NULL AND infoadd <> ''
          AND NOT ({' OR '.join(FLAGS)})
        ORDER BY name
    """)).fetchall()

    marked = {col: [] for col in FLAGS}
    review = []
    for student_id, name, infoadd in rows:
        kind = _classify(infoadd)
        if kind is None:
            continue
        if kind == 'revisar':
            review.append(f"{name} ('{infoadd}')")
            continue
        bind.execute(sa.text(f"UPDATE students SET {kind} = TRUE WHERE id = :id"), {"id": student_id})
        marked[kind].append(f"{name} ('{infoadd}')")

    existing_checks = [c['name'] for c in sa.inspect(bind).get_check_constraints('students')]
    if CHECK_NAME not in existing_checks:
        op.create_check_constraint(
            CHECK_NAME,
            'students',
            '(es_precursor_aux_camp::int + es_precursor_aux_ind::int + es_precursor_reg::int) <= 1',
        )

    labels = {
        'es_precursor_reg': 'Precursor regular',
        'es_precursor_aux_ind': 'Precursor auxiliar indefinido',
        'es_precursor_aux_camp': 'Precursor auxiliar en campaña',
    }
    print("\nPrecursorado tomado de 'Información adicional':")
    for col in ('es_precursor_reg', 'es_precursor_aux_ind', 'es_precursor_aux_camp'):
        print(f"  {labels[col]} ({len(marked[col])}): " + (", ".join(marked[col]) or "nadie"))
    if review:
        print(f"  REVISAR A MANO en Estudiantes ({len(review)}): " + ", ".join(review))
    print()


def downgrade() -> None:
    op.drop_constraint(CHECK_NAME, 'students', type_='check')
    for col in FLAGS:
        op.drop_column('students', col)
