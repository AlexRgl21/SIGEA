# Notificaciones de la campana, con estado de leído guardado en la base de datos.

import logging
import pyodbc
import config

logger = logging.getLogger(__name__)

TIPO_SOLICITUD = 'SOLICITUD'
TIPO_RESPUESTA = 'RESPUESTA'


def mensaje_solicitud(nombre, apellidos, espacio, fecha):
    return f"Nueva solicitud de {nombre} {apellidos} para {espacio} el día {fecha}."


def mensaje_respuesta(espacio, id_reserva, estado, fecha):
    estado_limpio = "Aprobada" if "APROBADA" in str(estado).upper() else "Rechazada"
    return f"Tu reserva en {espacio} (Folio: REQ-{id_reserva}) fue {estado_limpio} para el día {fecha}."


def _consultar(cursor, rol, id_usuario, limite):

    if rol in config.ROLES_ADMINISTRATIVOS:
        tipo = TIPO_SOLICITUD
        cursor.execute("""
            SELECT TOP (?) r.id_reserva, u.nombre, u.apellidos, e.nombre, r.fecha,
                   CASE WHEN n.id_reserva IS NULL THEN 0 ELSE 1 END AS leida
            FROM Reservas r
            JOIN Usuarios u ON r.id_usuario = u.id_usuario
            JOIN Espacios e ON r.id_espacio = e.id_espacio
            LEFT JOIN NotificacionesLeidas n
                   ON n.id_usuario = ? AND n.id_reserva = r.id_reserva AND n.tipo = ?
            WHERE UPPER(TRIM(r.estado)) = 'PENDIENTE'
            ORDER BY r.id_reserva DESC
        """, (limite, id_usuario, tipo))
        return tipo, [(f[0], mensaje_solicitud(f[1], f[2], f[3], f[4]), bool(f[5]))
                      for f in cursor.fetchall()]

    if rol == config.ROL_MAESTRO:
        tipo = TIPO_RESPUESTA
        cursor.execute("""
            SELECT TOP (?) r.id_reserva, e.nombre, r.estado, r.fecha,
                   CASE WHEN n.id_reserva IS NULL THEN 0 ELSE 1 END AS leida
            FROM Reservas r
            JOIN Espacios e ON r.id_espacio = e.id_espacio
            LEFT JOIN NotificacionesLeidas n
                   ON n.id_usuario = ? AND n.id_reserva = r.id_reserva AND n.tipo = ?
            WHERE r.id_usuario = ?
              AND UPPER(TRIM(r.estado)) IN ('APROBADA', 'RECHAZADA')
            ORDER BY r.id_reserva DESC
        """, (limite, id_usuario, tipo, id_usuario))
        return tipo, [(f[0], mensaje_respuesta(f[1], f[0], f[2], f[3]), bool(f[4]))
                      for f in cursor.fetchall()]

    return None, []


def obtener(conn, rol, id_usuario, url):
    _, filas = _consultar(conn.cursor(), rol, id_usuario, config.NOTIS_LIMITE)
    lista = [{'mensaje': m, 'url': url, 'leida': leida} for _, m, leida in filas]
    return {'lista': lista, 'sin_leer': sum(1 for n in lista if not n['leida'])}


def marcar_leidas(conn, rol, id_usuario):
    cursor = conn.cursor()
    tipo, filas = _consultar(cursor, rol, id_usuario, config.NOTIS_LIMITE)
    pendientes = [id_reserva for id_reserva, _, leida in filas if not leida]
    try:
        for id_reserva in pendientes:
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM NotificacionesLeidas WITH (UPDLOCK, HOLDLOCK)
                               WHERE id_usuario = ? AND id_reserva = ? AND tipo = ?)
                    INSERT INTO NotificacionesLeidas (id_usuario, id_reserva, tipo)
                    VALUES (?, ?, ?)
            """, (id_usuario, id_reserva, tipo, id_usuario, id_reserva, tipo))
        conn.commit()
    except pyodbc.IntegrityError:
        conn.rollback()      # otra pestaña la marcó al mismo tiempo: ya quedó leída
    except Exception:
        conn.rollback()
        raise
    return len(pendientes)