# Lógica de negocio de las reservas especiales.

import datetime
import logging

import config
from . import conflictos, correo
from .errores import ErrorNegocio

logger = logging.getLogger(__name__)


def _estado(valor):
    return str(valor).strip().capitalize()


def _filas_a_dicts(cursor):
    columnas = [c[0] for c in cursor.description]
    return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


# Consulta
def datos_vista(conn, rol, id_usuario, hoy=None):
    # Devuelve (pendientes, aprobadas, espacios) para la pantalla de reservas.
    hoy = hoy or datetime.date.today()
    cursor = conn.cursor()

    marcas = ','.join('?' * len(config.TIPOS_ESPACIO_RESERVABLES))
    cursor.execute(f"""
        SELECT e.id_espacio, e.nombre AS espacio_nombre, ed.nombre AS edificio_nombre
        FROM Espacios e
        JOIN Edificios ed ON e.id_edificio = ed.id_edificio
        WHERE e.estatus = 'Activo' AND e.tipo IN ({marcas})
    """, config.TIPOS_ESPACIO_RESERVABLES)
    espacios = _filas_a_dicts(cursor)

    base = """
        SELECT r.id_reserva, r.fecha, r.hora_inicio, r.hora_fin, r.motivo, r.estado,
            u.nombre, u.apellidos,
            e.nombre AS espacio_nombre, ed.nombre AS edificio_nombre
        FROM Reservas r
        JOIN Usuarios u ON r.id_usuario = u.id_usuario
        JOIN Espacios e ON r.id_espacio = e.id_espacio
        JOIN Edificios ed ON e.id_edificio = ed.id_edificio
    """
    orden = " ORDER BY r.fecha ASC, r.hora_inicio ASC"
    if rol == config.ROL_MAESTRO:
        cursor.execute(base + " WHERE r.id_usuario = ? AND (r.fecha >= ? OR r.estado = 'Pendiente')" + orden,
                    (id_usuario, hoy))
    else:
        cursor.execute(base + " WHERE r.fecha >= ? OR r.estado = 'Pendiente'" + orden, (hoy,))
    todas = _filas_a_dicts(cursor)

    pendientes = [r for r in todas if _estado(r['estado']) == 'Pendiente']
    aprobadas = [r for r in todas if _estado(r['estado']) == 'Aprobada']
    return pendientes, aprobadas, espacios


# Crear
def validar_solicitud(id_espacio, fecha, hora_inicio, hora_fin, motivo, hoy=None):
    
    hoy = hoy or datetime.date.today()
    motivo = (motivo or '').strip()
    if not all([id_espacio, fecha, hora_inicio, hora_fin, motivo]):
        raise ErrorNegocio("Completa todos los campos de la solicitud.")
    try:
        id_espacio = int(id_espacio)
        fecha_obj = datetime.date.fromisoformat(fecha)
        inicio = datetime.time.fromisoformat(hora_inicio)
        fin = datetime.time.fromisoformat(hora_fin)
    except ValueError:
        raise ErrorNegocio("Hay datos con formato inválido en la solicitud.") from None

    if fecha_obj < hoy:
        raise ErrorNegocio("No puedes solicitar una fecha pasada.")
    if fin <= inicio:
        raise ErrorNegocio("La hora de fin debe ser posterior a la hora de inicio.")
    if len(motivo) > 255:
        raise ErrorNegocio("El motivo no puede pasar de 255 caracteres.")
    return id_espacio, fecha_obj, inicio, fin, motivo


def crear_reserva(conn, id_usuario, id_espacio, fecha, hora_inicio, hora_fin, motivo):
    # Guarda la solicitud como Pendiente y avisa por correo a admins y coordinadores.
    id_espacio, fecha_obj, inicio, fin, motivo = validar_solicitud(
        id_espacio, fecha, hora_inicio, hora_fin, motivo)

    cursor = conn.cursor()
    try:
        marcas = ','.join('?' * len(config.TIPOS_ESPACIO_RESERVABLES))
        cursor.execute(f"""
            SELECT 1 FROM Espacios
            WHERE id_espacio = ? AND estatus = 'Activo' AND tipo IN ({marcas})
        """, (id_espacio, *config.TIPOS_ESPACIO_RESERVABLES))
        if not cursor.fetchone():
            raise ErrorNegocio("El espacio seleccionado no está disponible para reservas.")

        cursor.execute("""
            INSERT INTO Reservas (id_usuario, id_espacio, fecha, hora_inicio, hora_fin, motivo, estado)
            VALUES (?, ?, ?, ?, ?, ?, 'Pendiente')
        """, (id_usuario, id_espacio, fecha_obj, inicio, fin, motivo))
        conn.commit()
    except ErrorNegocio:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise

    # La reserva ya está guardada: si falla el aviso, no se deshace nada.
    try:
        cursor.execute("SELECT correo FROM Usuarios WHERE id_rol IN (1, 2) AND estado = 'Activo'")
        correos = [f[0] for f in cursor.fetchall()]
        correo.notificar_nueva_reserva(correos, fecha_obj)
    except Exception:
        logger.exception("No se pudo avisar a coordinación de la nueva reserva")


# Aprobar / rechazar
def _reserva_con_datos(cursor, id_reserva):
    cursor.execute("""
        SELECT r.id_espacio, r.fecha, r.hora_inicio, r.hora_fin, r.estado,
               u.correo, u.nombre, e.nombre AS espacio
        FROM Reservas r
        JOIN Usuarios u ON r.id_usuario = u.id_usuario
        JOIN Espacios e ON r.id_espacio = e.id_espacio
        WHERE r.id_reserva = ?
    """, (id_reserva,))
    fila = cursor.fetchone()
    if not fila:
        return None
    return dict(id_espacio=fila[0], fecha=fila[1], hora_inicio=fila[2], hora_fin=fila[3],
                estado=fila[4], correo=fila[5], nombre=fila[6], espacio=fila[7])


def aprobar_reserva(conn, id_reserva):
    cursor = conn.cursor()
    try:
        reserva = _reserva_con_datos(cursor, id_reserva)
        if not reserva:
            raise ErrorNegocio("Error: No se encontró la solicitud de reserva.")
        if _estado(reserva['estado']) != 'Pendiente':
            raise ErrorNegocio("Esta solicitud ya fue atendida.")

        cursor.execute("""
            SELECT hora_inicio, hora_fin
            FROM Reservas WITH (UPDLOCK, HOLDLOCK)
            WHERE id_espacio = ? AND fecha = ? AND estado = 'Aprobada'
        """, (reserva['id_espacio'], reserva['fecha']))
        aprobadas = [dict(hora_inicio=f[0], hora_fin=f[1]) for f in cursor.fetchall()]
        if conflictos.buscar_traslapes(reserva['hora_inicio'], reserva['hora_fin'], aprobadas):
            raise ErrorNegocio("No se puede aprobar: El espacio ya cuenta con una reserva en ese horario.")

        cursor.execute("UPDATE Reservas SET estado = 'Aprobada' "
                       "WHERE id_reserva = ? AND estado = 'Pendiente'", (id_reserva,))
        if cursor.rowcount == 0:
            raise ErrorNegocio("Esta solicitud ya fue atendida.")
        conn.commit()
    except ErrorNegocio:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise

    correo.notificar_reserva_aprobada(reserva['correo'], reserva['nombre'], reserva['espacio'],
                                      reserva['fecha'], reserva['hora_inicio'], reserva['hora_fin'])


def rechazar_reserva(conn, id_reserva):
    cursor = conn.cursor()
    try:
        reserva = _reserva_con_datos(cursor, id_reserva)
        cursor.execute("UPDATE Reservas SET estado = 'Rechazada' "
                       "WHERE id_reserva = ? AND estado = 'Pendiente'", (id_reserva,))
        if cursor.rowcount == 0:
            raise ErrorNegocio("Esta solicitud ya fue atendida o no existe.")
        conn.commit()
    except ErrorNegocio:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise

    if reserva:
        correo.notificar_reserva_rechazada(reserva['correo'], reserva['nombre'],
                                           reserva['espacio'], reserva['fecha'])