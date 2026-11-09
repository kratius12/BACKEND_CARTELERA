"""fin de semana: presidente y lector del estudio de La Atalaya cada sábado

- Agrega a students los permisos fds_presidente y fds_lector (por defecto false).
- Crea weekend_assignments: una fila por sábado con presidente y lector.
- Carga las 14 semanas ya programadas (15 de agosto a 14 de noviembre de 2026).
  Cada nombre se busca entre los estudiantes sin distinguir mayúsculas ni tildes;
  si coincide con un solo varón, la semana queda vinculada a él y se le activa el
  permiso correspondiente. Si no coincide, la semana guarda el nombre tal cual y
  el panel la marca "Sin vincular" para elegir al estudiante a mano. Al final se
  imprime la lista de nombres que no coincidieron.

Es seguro aplicarla antes de desplegar el código nuevo: las columnas nuevas tienen
valor por defecto y la tabla nueva no la usa el código anterior.
"""
import difflib
import re
import unicodedata
from datetime import date

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20261107_0002'
down_revision = '20261107_0001'
branch_labels = None
depends_on = None

# (sábado, presidente, lector) tal como aparecen en la hoja impresa
HISTORIAL = [
    (date(2026, 8, 15), "GABRIEL ALVAREZ", "ROBINSON URAN"),
    (date(2026, 8, 22), "SAMUEL GALLEGO", "RONALD ORTIZ"),
    (date(2026, 8, 29), "FRANCISCO AVILÉZ", "SAMUEL GALLEGO"),
    (date(2026, 9, 5), "ROBINSON URAN", "OLIVERIO MARIN"),
    (date(2026, 9, 12), "HERNY BLANCO", "JULIO FERNANDEZ"),
    (date(2026, 9, 19), "CESAR ORTIZ", "SANTIAGO FERNANDEZ"),
    (date(2026, 9, 26), "JHONNIS AVILÉZ", "DANIEL CURIEL"),
    (date(2026, 10, 3), "JULIO FERNANDEZ", "CRISTIAN AVILEZ"),
    (date(2026, 10, 10), "ENALGE GOMEZ", "OLIVERIO MARIN"),
    (date(2026, 10, 17), "DANIEL RESTREPO", "RIGOLUIS SOTO"),
    (date(2026, 10, 24), "EMILIO DURANGO", "CESAR ORTIZ"),
    (date(2026, 10, 31), "VICTOR VASQUEZ", "SAMUEL GALLEGO"),
    (date(2026, 11, 7), "CRISTIAN AVILÉZ", "FRANCISCO AVILÉZ"),
    (date(2026, 11, 14), "ELIO AGAMEZ", "ROBINSON URAN"),
]


def _clave(nombre: str) -> str:
    """Minúsculas, sin tildes ni signos; z y s se igualan (Avilez / Avilés)."""
    sin_tildes = unicodedata.normalize("NFKD", nombre or "")
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    limpio = re.sub(r"[^a-z ]+", " ", sin_tildes.lower()).replace("z", "s")
    return " ".join(limpio.split())


def _buscar(nombre: str, estudiantes: list[dict]):
    """Devuelve (estudiante, motivo). estudiante es None si no hay una única coincidencia."""
    clave = _clave(nombre)
    exactos = [e for e in estudiantes if e["clave"] == clave]
    if len(exactos) == 1:
        candidatos = exactos
    else:
        # "Samuel Gallego" coincide con "Samuel Gallego Ruiz": todas las palabras presentes
        palabras = set(clave.split())
        candidatos = exactos or [e for e in estudiantes if palabras <= set(e["clave"].split())]
    if len(candidatos) > 1:
        # Si varios coinciden pero solo uno está activo, se toma el activo
        activos = [e for e in candidatos if e["status"] == "Activo"]
        if len(activos) == 1:
            candidatos = activos
    if len(candidatos) == 1:
        estudiante = candidatos[0]
        if estudiante["gender"] == 0:
            return None, f"coincide con {estudiante['name']}, que no está registrado como varón"
        return estudiante, None
    if len(candidatos) > 1:
        nombres = ", ".join(e["name"] for e in candidatos[:4])
        return None, f"coincide con varios estudiantes ({nombres})"
    parecidos = difflib.get_close_matches(clave, [e["clave"] for e in estudiantes], n=2, cutoff=0.8)
    if parecidos:
        sugerencias = ", ".join(e["name"] for e in estudiantes if e["clave"] in parecidos)
        return None, f"sin coincidencia; ¿quizá {sugerencias}?"
    return None, "sin coincidencia"


def upgrade() -> None:
    op.add_column('students', sa.Column('fds_presidente', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('students', sa.Column('fds_lector', sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_table(
        'weekend_assignments',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('president_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reader_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='SET NULL'), nullable=True),
        sa.Column('president_name', sa.String(150), nullable=True),
        sa.Column('reader_name', sa.String(150), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('date', name='uq_weekend_assignments_date'),
        sa.CheckConstraint('EXTRACT(ISODOW FROM date) = 6', name='ck_weekend_assignments_sabado'),
    )
    op.create_index('ix_weekend_assignments_id', 'weekend_assignments', ['id'])

    bind = op.get_bind()
    filas = bind.execute(sa.text("SELECT id, name, gender, status FROM students")).mappings().all()
    estudiantes = [dict(f, clave=_clave(f["name"])) for f in filas]

    vinculados: dict[str, set[int]] = {"fds_presidente": set(), "fds_lector": set()}
    sin_vincular: dict[str, str] = {}

    def resolver(nombre: str, permiso: str):
        estudiante, motivo = _buscar(nombre, estudiantes)
        if estudiante is None:
            sin_vincular.setdefault(nombre, motivo)
            return None, nombre.title()
        vinculados[permiso].add(estudiante["id"])
        return estudiante["id"], estudiante["name"]

    insertar = sa.text(
        "INSERT INTO weekend_assignments (date, president_id, president_name, reader_id, reader_name) "
        "VALUES (:date, :president_id, :president_name, :reader_id, :reader_name) "
        "ON CONFLICT (date) DO NOTHING"
    )
    for sabado, presidente, lector in HISTORIAL:
        president_id, president_name = resolver(presidente, "fds_presidente")
        reader_id, reader_name = resolver(lector, "fds_lector")
        bind.execute(insertar, {
            "date": sabado,
            "president_id": president_id,
            "president_name": president_name,
            "reader_id": reader_id,
            "reader_name": reader_name,
        })

    for permiso, ids in vinculados.items():
        if ids:
            bind.execute(
                sa.text(f"UPDATE students SET {permiso} = true WHERE id = ANY(:ids)"),
                {"ids": sorted(ids)},
            )

    print(
        "Fin de semana: semanas cargadas = "
        f"{len(HISTORIAL)}; con permiso de presidencia = {len(vinculados['fds_presidente'])}; "
        f"con permiso de lectura = {len(vinculados['fds_lector'])}"
    )
    if sin_vincular:
        print("Nombres sin vincular (quedan como texto; elige al estudiante en el panel):")
        for nombre, motivo in sin_vincular.items():
            print(f"  - {nombre}: {motivo}")


def downgrade() -> None:
    op.drop_index('ix_weekend_assignments_id', table_name='weekend_assignments')
    op.drop_table('weekend_assignments')
    op.drop_column('students', 'fds_lector')
    op.drop_column('students', 'fds_presidente')
