# Lógica de negocio de los tickets de Soporte Técnico (sin Flask).
import logging

import config
from . import correo
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
            OUTPUT INSERTED.id_ticket
            SELECT ?, ?, ?, ?
            WHERE (SELECT COUNT(*) FROM Tickets WHERE id_usuario = ? AND estado <> 'Resuelto') < ?
        """, (id_usuario, asunto, categoria, descripcion,
              id_usuario, config.TICKET_MAX_SIN_RESOLVER))
        fila = cursor.fetchone()
        if not fila:
            conn.rollback()
            raise ErrorNegocio(f"Ya tienes {config.TICKET_MAX_SIN_RESOLVER} tickets sin resolver. "
                               "Espera la respuesta de Soporte antes de abrir otro.")
        id_ticket = fila[0]
        conn.commit()
    except ErrorNegocio:
        raise
    except Exception:
        conn.rollback()
        raise

    _avisar_a_soporte(conn, id_ticket, id_usuario, asunto, categoria, descripcion)
    return id_ticket


def _avisar_a_soporte(conn, id_ticket, id_usuario, asunto, categoria, descripcion):
    # El ticket ya está guardado: si el aviso falla, solo se registra y no se le muestra error al usuario.
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT correo FROM Usuarios WHERE id_rol = ? AND estado = 'Activo'",
                       (config.ID_ROL_SOPORTE,))
        correos = [f[0] for f in cursor.fetchall()]
        cursor.execute("SELECT nombre, apellidos FROM Usuarios WHERE id_usuario = ?", (id_usuario,))
        u = cursor.fetchone()
        solicitante = f"{u[0]} {u[1]}" if u else "Usuario desconocido"
        correo.notificar_nuevo_ticket(correos, id_ticket, asunto, categoria, solicitante, descripcion)
    except Exception:
        logger.exception("No se pudo avisar a Soporte del ticket %s", id_ticket)


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