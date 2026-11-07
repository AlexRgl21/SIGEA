# Lógica de negocio de los tickets de Soporte Técnico (sin Flask).
import logging

import config
from .errores import ErrorNegocio

logger = logging.getLogger(__name__)

COLUMNAS = """
    t.id_ticket, t.asunto, t.categoria, t.descripcion, t.prioridad, t.estado,
    t.respuesta, t.creado_en, t.actualizado_en, t.resuelto_en,
    u.nombre, u.apellidos, u.correo,
    s.nombre AS soporte_nombre
"""
JOINS = """
    FROM Tickets t
    JOIN Usuarios u ON t.id_usuario = u.id_usuario
    LEFT JOIN Usuarios s ON t.id_atendido_por = s.id_usuario
"""


def _filas_a_dicts(cursor):
    columnas = [c[0] for c in cursor.description]
    return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


def listar_mios(conn, id_usuario):
    cursor = conn.cursor()
    cursor.execute(f"SELECT TOP (50) {COLUMNAS} {JOINS} WHERE t.id_usuario = ? ORDER BY t.id_ticket DESC",
                   (id_usuario,))
    return _filas_a_dicts(cursor)


def tablero(conn):
    # Abiertos y en proceso completos; resueltos limitados para que el tablero no crezca sin fin.
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT {COLUMNAS} {JOINS}
        WHERE t.estado IN ('Abierto', 'En proceso')
        ORDER BY CASE t.prioridad WHEN 'Alta' THEN 1 WHEN 'Media' THEN 2 ELSE 3 END, t.id_ticket ASC
    """)
    activos = _filas_a_dicts(cursor)
    cursor.execute(f"""
        SELECT TOP (?) {COLUMNAS} {JOINS}
        WHERE t.estado = 'Resuelto'
        ORDER BY t.resuelto_en DESC
    """, (config.TICKET_MAX_RESUELTOS_VISTA,))
    resueltos = _filas_a_dicts(cursor)
    return (
        [t for t in activos if t['estado'] == 'Abierto'],
        [t for t in activos if t['estado'] == 'En proceso'],
        resueltos,
    )


def crear(conn, id_usuario, asunto, categoria, descripcion):
    asunto = (asunto or '').strip()
    descripcion = (descripcion or '').strip()
    categoria = (categoria or '').strip()

    if not asunto or not descripcion:
        raise ErrorNegocio("Escribe el asunto y describe el problema.")
    if len(asunto) > 150:
        raise ErrorNegocio("El asunto no puede pasar de 150 caracteres.")
    if len(descripcion) > 2000:
        raise ErrorNegocio("La descripción no puede pasar de 2000 caracteres.")
    if categoria not in config.TICKET_CATEGORIAS:
        raise ErrorNegocio("La categoría no es válida.")

    cursor = conn.cursor()
    try:
        # La prioridad la define Soporte: el ticket nace con la prioridad por defecto de la tabla (Media).
        cursor.execute("""
            INSERT INTO Tickets (id_usuario, asunto, categoria, descripcion)
            SELECT ?, ?, ?, ?
            WHERE (SELECT COUNT(*) FROM Tickets WHERE id_usuario = ? AND estado <> 'Resuelto') < ?
        """, (id_usuario, asunto, categoria, descripcion,
              id_usuario, config.TICKET_MAX_SIN_RESOLVER))
        if cursor.rowcount == 0:
            conn.rollback()
            raise ErrorNegocio(f"Ya tienes {config.TICKET_MAX_SIN_RESOLVER} tickets sin resolver. "
                               "Espera la respuesta de Soporte antes de abrir otro.")
        conn.commit()
    except ErrorNegocio:
        raise
    except Exception:
        conn.rollback()
        raise


def gestionar(conn, id_ticket, id_soporte, estado, prioridad, respuesta):
    estado = (estado or '').strip()
    prioridad = (prioridad or '').strip()
    respuesta = (respuesta or '').strip()

    if estado not in config.TICKET_ESTADOS:
        raise ErrorNegocio("El estado seleccionado no es válido.")
    if prioridad not in config.TICKET_PRIORIDADES:
        raise ErrorNegocio("La prioridad seleccionada no es válida.")
    if len(respuesta) > 2000:
        raise ErrorNegocio("La respuesta no puede pasar de 2000 caracteres.")
    if estado == 'Resuelto' and not respuesta:
        raise ErrorNegocio("Para marcar el ticket como resuelto escribe la respuesta para el usuario.")

    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE Tickets
            SET estado = ?,
                prioridad = ?,
                respuesta = ?,
                id_atendido_por = ?,
                actualizado_en = SYSDATETIME(),
                resuelto_en = CASE WHEN CAST(? AS VARCHAR(20)) = 'Resuelto' THEN SYSDATETIME() ELSE NULL END
            WHERE id_ticket = ?
        """, (estado, prioridad, respuesta or None, id_soporte, estado, id_ticket))
        if cursor.rowcount == 0:
            conn.rollback()
            raise ErrorNegocio("No se encontró el ticket.")
        conn.commit()
    except ErrorNegocio:
        raise
    except Exception:
        conn.rollback()
        raise