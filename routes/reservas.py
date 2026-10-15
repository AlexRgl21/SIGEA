import logging
import os
import smtplib
import threading
from email.message import EmailMessage
import datetime

from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from database.conexion import get_db_connection
from .auth import role_required 

# --- ENVÍO DE NOTIFICACIONES POR CORREO ---
def _enviar_smtp(destinatarios, asunto, contenido):
    correo_emisor = os.getenv('GMAIL_USER')
    password_emisor = os.getenv('GMAIL_PASS')
    if not correo_emisor or not password_emisor:
        logger.error("Faltan GMAIL_USER o GMAIL_PASS: no se envió la notificación de reserva")
        return

    msg = EmailMessage()
    msg['Subject'] = asunto
    msg['From'] = correo_emisor
    if len(destinatarios) == 1:
        msg['To'] = destinatarios[0]
    else:
        msg['To'] = correo_emisor                  # varios destinatarios: van en copia oculta,
        msg['Bcc'] = ', '.join(destinatarios)      # así nadie ve los correos de los demás
    msg.set_content(contenido)

    try:
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as server:
            server.starttls()
            server.login(correo_emisor, password_emisor)
            server.send_message(msg)
        logger.info("Notificación de reserva enviada (%d destinatario(s))", len(destinatarios))
    except Exception:
        logger.exception("Error al enviar la notificación de reserva")


def enviar_notificacion_reserva(destinatarios, asunto, contenido):
    """Envía en segundo plano para no bloquear la petición. Acepta un correo o una lista."""
    if isinstance(destinatarios, str):
        destinatarios = [destinatarios]
    destinatarios = [d for d in destinatarios if d]
    if not destinatarios:
        return
    threading.Thread(target=_enviar_smtp, args=(destinatarios, asunto, contenido), daemon=True).start()


reservas_bp = Blueprint('reservas', __name__)
logger = logging.getLogger(__name__)

@reservas_bp.route('/reservas')
@role_required('ADMIN', 'COORDINADOR', 'MAESTRO') 
def vista_reserva():
    if 'id_usuario' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    if not conn:
        flash("Error de conexión a la base de datos", "danger")
        return render_template('reservas.html', pendientes=[], aprobadas=[], espacios=[])
    
    cursor = conn.cursor()

    # Traer los espacios disponibles para el formulario
    cursor.execute("""
        SELECT e.id_espacio, e.nombre AS espacio_nombre, ed.nombre AS edificio_nombre
        FROM Espacios e
        JOIN Edificios ed ON e.id_edificio = ed.id_edificio
        WHERE e.estatus = 'Activo' AND e.tipo IN ('laboratorio', 'sala de conferencia')
    """)

    cols_esp = [col[0] for col in cursor.description]
    espacios = [dict(zip(cols_esp, row)) for row in cursor.fetchall()]

    rol_actual = session.get('role')
    id_usuario_actual = session.get('id_usuario')
    
    hoy = datetime.date.today() 

    # LÓGICA DE VISTAS POR ROL
    if rol_actual == 'MAESTRO':
        cursor.execute("""
            SELECT r.id_reserva, r.fecha, r.hora_inicio, r.hora_fin, r.motivo, r.estado,
                u.nombre, u.apellidos,
                e.nombre AS espacio_nombre, ed.nombre AS edificio_nombre
            FROM Reservas r
            JOIN Usuarios u ON r.id_usuario = u.id_usuario
            JOIN Espacios e ON r.id_espacio = e.id_espacio
            JOIN Edificios ed ON e.id_edificio = ed.id_edificio
            WHERE r.id_usuario = ? AND (r.fecha >= ? OR r.estado = 'Pendiente')
            ORDER BY r.fecha ASC, r.hora_inicio ASC
        """, (id_usuario_actual, hoy)) 
        
    else:
        cursor.execute("""
            SELECT r.id_reserva, r.fecha, r.hora_inicio, r.hora_fin, r.motivo, r.estado,
                u.nombre, u.apellidos,
                e.nombre AS espacio_nombre, ed.nombre AS edificio_nombre
            FROM Reservas r
            JOIN Usuarios u ON r.id_usuario = u.id_usuario
            JOIN Espacios e ON r.id_espacio = e.id_espacio
            JOIN Edificios ed ON e.id_edificio = ed.id_edificio
            WHERE r.fecha >= ? OR r.estado = 'Pendiente'
            ORDER BY r.fecha ASC, r.hora_inicio ASC
        """, (hoy,))

    cols_res = [col[0] for col in cursor.description]
    todas_reservas = [dict(zip(cols_res, row)) for row in cursor.fetchall()]

    conn.close()
    
    pendientes = [res for res in todas_reservas if str(res['estado']).strip().capitalize() == 'Pendiente']
    aprobadas = [res for res in todas_reservas if str(res['estado']).strip().capitalize() == 'Aprobada']

    return render_template('reservas.html', pendientes=pendientes, aprobadas=aprobadas, espacios=espacios)

# CREAR RESERVA (SOLO ADMIN Y MAESTRO)
@reservas_bp.route('/reservas/nueva', methods=['POST'])
@role_required('COORDINADOR', 'ADMIN', 'MAESTRO') 
def crear_reserva():
    id_usuario = session.get('id_usuario')
    id_espacio = request.form.get('id_espacio')
    fecha = request.form.get('fecha')
    hora_inicio = request.form.get('hora_inicio')
    hora_fin = request.form.get('hora_fin')
    motivo = (request.form.get('motivo') or '').strip()

    if not all([id_espacio, fecha, hora_inicio, hora_fin, motivo]):
        flash("Completa todos los campos de la solicitud.", "danger")
        return redirect(url_for('reservas.vista_reserva'))

    try:
        id_espacio = int(id_espacio)
        fecha_obj = datetime.date.fromisoformat(fecha)
        inicio = datetime.time.fromisoformat(hora_inicio)
        fin = datetime.time.fromisoformat(hora_fin)
    except ValueError:
        flash("Hay datos con formato inválido en la solicitud.", "danger")
        return redirect(url_for('reservas.vista_reserva'))

    if fecha_obj < datetime.date.today():
        flash("No puedes solicitar una fecha pasada.", "danger")
        return redirect(url_for('reservas.vista_reserva'))
    if fin <= inicio:
        flash("La hora de fin debe ser posterior a la hora de inicio.", "danger")
        return redirect(url_for('reservas.vista_reserva'))
    if len(motivo) > 255:
        flash("El motivo no puede pasar de 255 caracteres.", "danger")
        return redirect(url_for('reservas.vista_reserva'))

    conn = get_db_connection()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for('reservas.vista_reserva'))

    correos_admins = []
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1 FROM Espacios
            WHERE id_espacio = ? AND estatus = 'Activo'
              AND tipo IN ('laboratorio', 'sala de conferencia')
        """, (id_espacio,))
        if not cursor.fetchone():
            flash("El espacio seleccionado no está disponible para reservas.", "danger")
            return redirect(url_for('reservas.vista_reserva'))

        cursor.execute('''
            INSERT INTO Reservas (id_usuario, id_espacio, fecha, hora_inicio, hora_fin, motivo, estado)
            VALUES (?, ?, ?, ?, ?, ?, 'Pendiente')
        ''', (id_usuario, id_espacio, fecha, hora_inicio, hora_fin, motivo))
        conn.commit()
        flash("Solicitud de reserva enviada correctamente a revisión.", "success")
        
        # Destinatarios de la notificación. Si esta consulta falla, la reserva ya quedó guardada.
        try:
            cursor.execute("SELECT correo FROM Usuarios WHERE id_rol IN (1, 2) AND estado = 'Activo'")
            correos_admins = [fila[0] for fila in cursor.fetchall()]
        except Exception:
            logger.exception("No se pudo consultar a quién notificar la nueva reserva")

    except Exception:
        conn.rollback()
        logger.exception("Error al guardar la reserva")
        flash("Error al guardar la reserva. Inténtalo de nuevo o avisa al administrador.", "danger")
    finally:
        conn.close()

    if correos_admins:
        enviar_notificacion_reserva(
            correos_admins,
            "SIGEA - Nueva Solicitud de Reserva Especial",
            f"Se ha registrado una nueva solicitud para el día {fecha}. Ingresa a SIGEA para revisarla.")

    return redirect(url_for('reservas.vista_reserva'))

# APROBAR RESERVA (SOLO ADMIN Y COORDINADOR)
@reservas_bp.route('/reservas/aceptar/<int:id>', methods=['POST'])
@role_required('ADMIN', 'COORDINADOR')
def aceptar_reserva(id):
    notificar = None
    conn = get_db_connection()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for('reservas.vista_reserva'))

    try:
        cursor = conn.cursor()

        # Unimos las dos consultas: traemos estado de la reserva y los datos del maestro
        cursor.execute("""
            SELECT r.id_espacio, r.fecha, r.hora_inicio, r.hora_fin, r.estado, u.correo, u.nombre, e.nombre as espacio
            FROM Reservas r
            JOIN Usuarios u ON r.id_usuario = u.id_usuario
            JOIN Espacios e ON r.id_espacio = e.id_espacio
            WHERE r.id_reserva = ?
        """, (id,))
        reserva = cursor.fetchone()

        if not reserva:
            flash("Error: No se encontró la solicitud de reserva.", "danger")
            return redirect(url_for('reservas.vista_reserva'))

        id_espacio, fecha, hora_inicio, hora_fin, estado, correo_maestro, nombre_maestro, nombre_espacio = reserva

        # Solo se pueden aprobar solicitudes que sigan pendientes
        if str(estado).strip().capitalize() != 'Pendiente':
            flash("Esta solicitud ya fue atendida.", "danger")
            return redirect(url_for('reservas.vista_reserva'))

        cursor.execute("""
            SELECT COUNT(*)
            FROM Reservas
            WHERE id_espacio = ?
              AND fecha = ?
              AND estado = 'Aprobada'
              AND hora_inicio < ?
              AND hora_fin > ?
        """, (id_espacio, fecha, hora_fin, hora_inicio))

        empalmes = cursor.fetchone()[0]

        if empalmes > 0:
            flash("No se puede aprobar: El espacio ya cuenta con una reserva en ese horario.", "danger")
        else:
            cursor.execute("UPDATE Reservas SET estado = 'Aprobada' "
                           "WHERE id_reserva = ? AND estado = 'Pendiente'", (id,))
            if cursor.rowcount == 0:
                flash("Esta solicitud ya fue atendida.", "danger")
            else:
                conn.commit()
                flash("La reserva fue aprobada con éxito.", "success")
                notificar = (correo_maestro,
                             "SIGEA - Tu reserva ha sido Aprobada",
                             f"Hola {nombre_maestro},\n\nTu solicitud para el espacio '{nombre_espacio}' el día {fecha} de {hora_inicio} a {hora_fin} ha sido APROBADA.\n\nSaludos.")

    except Exception:
        conn.rollback()
        logger.exception("Error al aceptar la reserva")
        flash("Error al aceptar la reserva. Inténtalo de nuevo o avisa al administrador.", "danger")
    finally:
        conn.close()

    if notificar:
        enviar_notificacion_reserva(*notificar)

    return redirect(url_for('reservas.vista_reserva'))


# RECHAZAR RESERVA (SOLO ADMIN Y COORDINADOR)
@reservas_bp.route('/reservas/rechazar/<int:id>', methods=['POST'])
@role_required('ADMIN', 'COORDINADOR')
def rechazar_reserva(id):
    notificar = None
    conn = get_db_connection()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for('reservas.vista_reserva'))
    try:
        cursor = conn.cursor()
        
        # Obtenemos los datos antes de actualizar para notificar
        cursor.execute("""
            SELECT u.correo, u.nombre, e.nombre as espacio, r.fecha
            FROM Reservas r
            JOIN Usuarios u ON r.id_usuario = u.id_usuario
            JOIN Espacios e ON r.id_espacio = e.id_espacio
            WHERE r.id_reserva = ?
        """, (id,))
        datos_reserva = cursor.fetchone()

        cursor.execute("UPDATE Reservas SET estado = 'Rechazada' "
                       "WHERE id_reserva = ? AND estado = 'Pendiente'", (id,))
        if cursor.rowcount == 0:
            flash("Esta solicitud ya fue atendida o no existe.", "danger")
        else:
            conn.commit()
            flash("La reserva fue rechazada y eliminada del panel.", "success")

            if datos_reserva:
                correo_maestro, nombre_maestro, nombre_espacio, fecha = datos_reserva
                notificar = (correo_maestro,
                             "SIGEA - Tu reserva ha sido Rechazada",
                             f"Hola {nombre_maestro},\n\nLamentablemente tu solicitud para el espacio '{nombre_espacio}' el día {fecha} ha sido RECHAZADA.\n\nContacta a coordinación para más detalles.")
                
    except Exception:
        conn.rollback()
        logger.exception("Error al rechazar la reserva")
        flash("Error al rechazar la reserva. Inténtalo de nuevo o avisa al administrador.", "danger")
    finally:
        conn.close()

    if notificar:
        enviar_notificacion_reserva(*notificar)

    return redirect(url_for('reservas.vista_reserva'))