# Lógica de negocio de los periodos (cuatrimestres) y su tiempo de vida.

import datetime
import logging
import threading
import time

import config
from .errores import ErrorNegocio

logger = logging.getLogger(__name__)

_candado = threading.Lock()
_ultima_revision = None          # time.monotonic() de la última revisión automática


# Utilidades
def _a_fecha(valor, campo):
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor
    try:
        return datetime.date.fromisoformat(str(valor).strip())
    except ValueError:
        raise ErrorNegocio(f"La fecha de {campo} no es válida.") from None


def _validar(nombre, fecha_inicio, fecha_fin, hoy):
    nombre = (nombre or '').strip()
    if not nombre:
        raise ErrorNegocio("El nombre del periodo es obligatorio.")
    if len(nombre) > 100:
        raise ErrorNegocio("El nombre del periodo no puede pasar de 100 caracteres.")
    inicio = _a_fecha(fecha_inicio, 'inicio')
    fin = _a_fecha(fecha_fin, 'fin')
    if fin < inicio:
        raise ErrorNegocio("La fecha de fin no puede ser anterior a la fecha de inicio.")
    if fin < hoy:
        raise ErrorNegocio("La fecha de fin ya pasó: el periodo se cerraría de inmediato.")
    return nombre, inicio, fin


def _validar_unicidad(cursor, nombre, inicio, fin, excluir_id=None):
    # Dos periodos activos no pueden traslaparse: el motor de conflictos revisa por periodo.
    excluir = excluir_id if excluir_id is not None else 0
    cursor.execute("SELECT 1 FROM Periodos WITH (UPDLOCK, HOLDLOCK) "
                   "WHERE nombre = ? AND id_periodo <> ?", (nombre, excluir))
    if cursor.fetchone():
        raise ErrorNegocio(f"Ya existe un periodo llamado '{nombre}'.")
    cursor.execute("""
        SELECT nombre FROM Periodos WITH (UPDLOCK, HOLDLOCK)
        WHERE activo = 1 AND id_periodo <> ? AND fecha_inicio <= ? AND fecha_fin >= ?
    """, (excluir, fin, inicio))
    otro = cursor.fetchone()
    if otro:
        raise ErrorNegocio(f"Las fechas se traslapan con el periodo activo '{otro[0]}'.")


def _cerrar(cursor, id_periodo):
    # Borra horarios y asignaciones del periodo y lo marca inactivo. NO hace commit.
    cursor.execute("SELECT COUNT(*) FROM Asignaciones WHERE id_periodo = ?", (id_periodo,))
    borradas = cursor.fetchone()[0] or 0
    cursor.execute("""
        DELETE h FROM Horarios h
        JOIN Asignaciones a ON h.id_asignacion = a.id_asignacion
        WHERE a.id_periodo = ?
    """, (id_periodo,))
    cursor.execute("DELETE FROM Asignaciones WHERE id_periodo = ?", (id_periodo,))
    cursor.execute("UPDATE Periodos SET activo = 0 WHERE id_periodo = ?", (id_periodo,))
    return borradas


# Consulta
def listar(conn, hoy=None):
    hoy = hoy or datetime.date.today()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id_periodo, p.nombre, p.fecha_inicio, p.fecha_fin, p.activo,
               (SELECT COUNT(*) FROM Asignaciones a WHERE a.id_periodo = p.id_periodo)
        FROM Periodos p
        ORDER BY p.fecha_inicio DESC, p.id_periodo DESC
    """)
    periodos = []
    for id_p, nombre, ini, fin, activo, n_asig in cursor.fetchall():
        ini, fin = _a_fecha(ini, 'inicio'), _a_fecha(fin, 'fin')
        if not activo:
            estado, dias = 'Finalizado', None
        elif ini > hoy:
            estado, dias = 'Programado', (fin - hoy).days
        else:
            estado, dias = 'En curso', (fin - hoy).days
        periodos.append(dict(id_periodo=id_p, nombre=nombre, fecha_inicio=ini, fecha_fin=fin,
                             activo=bool(activo), estado=estado, dias_restantes=dias,
                             asignaciones=n_asig))
    return periodos


# Alta, edición y cierre manual
def crear_periodo(conn, nombre, fecha_inicio, fecha_fin, hoy=None):
    hoy = hoy or datetime.date.today()
    nombre, inicio, fin = _validar(nombre, fecha_inicio, fecha_fin, hoy)
    cursor = conn.cursor()
    try:
        _validar_unicidad(cursor, nombre, inicio, fin)
        cursor.execute("INSERT INTO Periodos (nombre, fecha_inicio, fecha_fin, activo) "
                       "VALUES (?, ?, ?, 1)", (nombre, inicio, fin))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def actualizar_periodo(conn, id_periodo, nombre, fecha_inicio, fecha_fin, hoy=None):
    hoy = hoy or datetime.date.today()
    nombre, inicio, fin = _validar(nombre, fecha_inicio, fecha_fin, hoy)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT activo FROM Periodos WITH (UPDLOCK) WHERE id_periodo = ?", (id_periodo,))
        fila = cursor.fetchone()
        if not fila:
            raise ErrorNegocio("El periodo no existe.")
        if not fila[0]:
            raise ErrorNegocio("Un periodo finalizado no se puede editar.")
        _validar_unicidad(cursor, nombre, inicio, fin, excluir_id=id_periodo)
        cursor.execute("UPDATE Periodos SET nombre = ?, fecha_inicio = ?, fecha_fin = ? "
                       "WHERE id_periodo = ?", (nombre, inicio, fin, id_periodo))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def finalizar_periodo(conn, id_periodo):
    # Cierre manual anticipado. Devuelve (nombre, asignaciones_borradas).
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT nombre, activo FROM Periodos WITH (UPDLOCK) WHERE id_periodo = ?",
                       (id_periodo,))
        fila = cursor.fetchone()
        if not fila:
            raise ErrorNegocio("El periodo no existe.")
        if not fila[1]:
            raise ErrorNegocio("Ese periodo ya estaba finalizado.")
        borradas = _cerrar(cursor, id_periodo)
        conn.commit()
        logger.info("Periodo %s finalizado manualmente; %s asignaciones borradas", id_periodo, borradas)
        return fila[0], borradas
    except Exception:
        conn.rollback()
        raise


# Vencimiento automático
def cerrar_vencidos(conn, hoy=None):
    # Cierra todos los periodos activos cuya fecha de fin ya pasó. Es idempotente.
    # Devuelve una lista de (id_periodo, nombre, asignaciones_borradas).
    hoy = hoy or datetime.date.today()
    cursor = conn.cursor()
    cerrados = []
    try:
        cursor.execute("SELECT id_periodo, nombre FROM Periodos WITH (UPDLOCK, HOLDLOCK) "
                       "WHERE activo = 1 AND fecha_fin < ?", (hoy,))
        for id_p, nombre in cursor.fetchall():
            cerrados.append((id_p, nombre, _cerrar(cursor, id_p)))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    for id_p, nombre, n in cerrados:
        logger.info("Periodo %s '%s' vencido: inactivado y %s asignaciones borradas", id_p, nombre, n)
    return cerrados


def cerrar_vencidos_seguro(conn, hoy=None):
    # Igual que cerrar_vencidos, pero nunca lanza: una falla aquí no debe tumbar la pantalla.
    try:
        return cerrar_vencidos(conn, hoy)
    except Exception:
        logger.exception("No se pudieron cerrar los periodos vencidos")
        return []


def revisar_si_toca(obtener_conn, hoy=None):
    # Se llama en cada petición; como mucho una vez por PERIODOS_REVISION_SEG hace la revisión.
    global _ultima_revision
    ahora = time.monotonic()
    with _candado:
        if _ultima_revision is not None and ahora - _ultima_revision < config.PERIODOS_REVISION_SEG:
            return
        _ultima_revision = ahora
    conn = obtener_conn()
    if conn:
        cerrar_vencidos_seguro(conn, hoy)