import datetime
import logging
import threading
import time

import config
from .errores import ErrorNegocio

logger = logging.getLogger(__name__)
auditoria = logging.getLogger('sigea.auditoria')

_candado = threading.Lock()
_ultima_revision = None


def _a_fecha(valor, campo):
    if isinstance(valor, datetime.datetime):
        return valor.date()

    if isinstance(valor, datetime.date):
        return valor

    try:
        return datetime.date.fromisoformat(
            str(valor).strip()
        )
    except ValueError:
        raise ErrorNegocio(
            f"La fecha de {campo} no es válida."
        ) from None


def _validar(
    nombre,
    fecha_inicio,
    fecha_fin,
    hoy
):
    nombre = (nombre or '').strip()

    if not nombre:
        raise ErrorNegocio(
            "El nombre del periodo es obligatorio."
        )

    if len(nombre) > 100:
        raise ErrorNegocio(
            "El nombre del periodo no puede pasar de 100 caracteres."
        )

    inicio = _a_fecha(fecha_inicio, 'inicio')
    fin = _a_fecha(fecha_fin, 'fin')

    if fin < inicio:
        raise ErrorNegocio(
            "La fecha de fin no puede ser anterior "
            "a la fecha de inicio."
        )

    if fin < hoy:
        raise ErrorNegocio(
            "La fecha de fin ya pasó: "
            "el periodo se cerraría de inmediato."
        )

    return nombre, inicio, fin


def _validar_unicidad(
    cursor,
    nombre,
    inicio,
    fin,
    excluir_id=None
):
    excluir = (
        excluir_id
        if excluir_id is not None
        else 0
    )

    cursor.execute("""
        SELECT 1
        FROM Periodos
        WHERE nombre = %s
          AND id_periodo <> %s
    """, (
        nombre,
        excluir
    ))

    if cursor.fetchone():
        raise ErrorNegocio(
            f"Ya existe un periodo llamado '{nombre}'."
        )

    cursor.execute("""
        SELECT nombre
        FROM Periodos
        WHERE activo = TRUE
          AND id_periodo <> %s
          AND fecha_inicio <= %s
          AND fecha_fin >= %s
    """, (
        excluir,
        fin,
        inicio
    ))

    otro = cursor.fetchone()

    if otro:
        raise ErrorNegocio(
            "Las fechas se traslapan con el "
            f"periodo activo '{otro[0]}'."
        )


def _cerrar(cursor, id_periodo):
    cursor.execute("""
        SELECT COUNT(*)
        FROM Asignaciones
        WHERE id_periodo = %s
    """, (id_periodo,))

    total_asignaciones = cursor.fetchone()[0] or 0

    # Solución AUD-005: Se elimina el borrado físico (DELETE) de Asignaciones y Horarios 
    # para conservar de forma íntegra el historial académico y los reportes institucionales.
    cursor.execute("""
        UPDATE Periodos
        SET activo = FALSE
        WHERE id_periodo = %s
    """, (id_periodo,))

    return total_asignaciones


# Consulta de periodos
def listar(conn, hoy=None):
    hoy = hoy or config.fecha_actual()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            p.id_periodo,
            p.nombre,
            p.fecha_inicio,
            p.fecha_fin,
            p.activo,
            (
                SELECT COUNT(*)
                FROM Asignaciones a
                WHERE a.id_periodo = p.id_periodo
            )
        FROM Periodos p
        ORDER BY
            p.fecha_inicio DESC,
            p.id_periodo DESC
    """)

    periodos = []

    for (
        id_p,
        nombre,
        ini,
        fin,
        activo,
        n_asig
    ) in cursor.fetchall():

        ini = _a_fecha(ini, 'inicio')
        fin = _a_fecha(fin, 'fin')

        if not activo:
            estado = 'Finalizado'
            dias = None

        elif ini > hoy:
            estado = 'Programado'
            dias = (fin - hoy).days

        else:
            estado = 'En curso'
            dias = (fin - hoy).days

        periodos.append({
            'id_periodo': id_p,
            'nombre': nombre,
            'fecha_inicio': ini,
            'fecha_fin': fin,
            'activo': bool(activo),
            'estado': estado,
            'dias_restantes': dias,
            'asignaciones': n_asig
        })

    return periodos


def crear_periodo(
    conn,
    nombre,
    fecha_inicio,
    fecha_fin,
    hoy=None
):
    hoy = hoy or config.fecha_actual()

    nombre, inicio, fin = _validar(
        nombre,
        fecha_inicio,
        fecha_fin,
        hoy
    )

    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT pg_advisory_xact_lock(42003, 1)
        """)

        _validar_unicidad(
            cursor,
            nombre,
            inicio,
            fin
        )

        cursor.execute("""
            INSERT INTO Periodos (
                nombre,
                fecha_inicio,
                fecha_fin,
                activo
            )
            VALUES (%s, %s, %s, TRUE)
        """, (
            nombre,
            inicio,
            fin
        ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise


def actualizar_periodo(
    conn,
    id_periodo,
    nombre,
    fecha_inicio,
    fecha_fin,
    hoy=None
):
    hoy = hoy or config.fecha_actual()

    nombre, inicio, fin = _validar(
        nombre,
        fecha_inicio,
        fecha_fin,
        hoy
    )

    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT activo
            FROM Periodos
            WHERE id_periodo = %s
            FOR UPDATE
        """, (id_periodo,))

        fila = cursor.fetchone()

        if not fila:
            raise ErrorNegocio(
                "El periodo no existe."
            )

        if not fila[0]:
            raise ErrorNegocio(
                "Un periodo finalizado no se puede editar."
            )

        cursor.execute("""
            SELECT pg_advisory_xact_lock(42003, 1)
        """)

        _validar_unicidad(
            cursor,
            nombre,
            inicio,
            fin,
            excluir_id=id_periodo
        )

        cursor.execute("""
            UPDATE Periodos
            SET nombre = %s,
                fecha_inicio = %s,
                fecha_fin = %s
            WHERE id_periodo = %s
        """, (
            nombre,
            inicio,
            fin,
            id_periodo
        ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise


def finalizar_periodo(conn, id_periodo):
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT nombre, activo
            FROM Periodos
            WHERE id_periodo = %s
            FOR UPDATE
        """, (id_periodo,))

        fila = cursor.fetchone()

        if not fila:
            raise ErrorNegocio(
                "El periodo no existe."
            )

        if not fila[1]:
            raise ErrorNegocio(
                "Ese periodo ya estaba finalizado."
            )

        total_asig = _cerrar(
            cursor,
            id_periodo
        )

        conn.commit()

        auditoria.info(
            "Periodo %s finalizado manualmente; "
            "%s asignaciones conservadas históricamente",
            id_periodo,
            total_asig
        )

        return fila[0], total_asig

    except Exception:
        conn.rollback()
        raise


# Vencimiento automático con candado consultivo distribuido (AUD-004)
def cerrar_vencidos(conn, hoy=None):
    hoy = hoy or config.fecha_actual()

    cursor = conn.cursor()
    cerrados = []

    try:
        # Candado consultivo de PostgreSQL: si otro worker ya está cerrando periodos, este saldrá inmediatamente
        cursor.execute("SELECT pg_try_advisory_xact_lock(998888);")
        if not cursor.fetchone()[0]:
            return []

        cursor.execute("""
            SELECT
                id_periodo,
                nombre
            FROM Periodos
            WHERE activo = TRUE
              AND fecha_fin < %s
            FOR UPDATE
        """, (hoy,))

        for id_p, nombre in cursor.fetchall():
            cerrados.append((
                id_p,
                nombre,
                _cerrar(cursor, id_p)
            ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    for id_p, nombre, n in cerrados:
        auditoria.info(
            "Periodo %s '%s' vencido e inactivado; "
            "%s asignaciones conservadas históricamente",
            id_p,
            nombre,
            n
        )

    return cerrados


def cerrar_vencidos_seguro(conn, hoy=None):
    try:
        return cerrar_vencidos(
            conn,
            hoy
        )

    except Exception:
        conn.rollback()

        logger.exception(
            "No se pudieron cerrar los periodos vencidos"
        )

        return []


def revisar_si_toca(obtener_conn, hoy=None):
    global _ultima_revision

    ahora = time.monotonic()

    with _candado:
        if (
            _ultima_revision is not None
            and ahora - _ultima_revision
            < config.PERIODOS_REVISION_SEG
        ):
            return

        _ultima_revision = ahora

    conn = obtener_conn()

    if conn:
        cerrar_vencidos_seguro(
            conn,
            hoy
        )