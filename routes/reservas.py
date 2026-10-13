from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from database.conexion import get_db_connection
from .auth import role_required 
import datetime 
import os
import smtplib
from email.message import EmailMessage

# --- FUNCION PARA ENVIAR CORREOS ---
def enviar_notificacion_reserva(correo_destino, asunto, contenido):
    correo_emisor = os.getenv('GMAIL_USER')
    password_emisor = os.getenv('GMAIL_PASS')

    msg = EmailMessage()
    msg['Subject'] = asunto
    msg['From'] = correo_emisor
    msg['To'] = correo_destino 
    msg.set_content(contenido)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(correo_emisor, password_emisor)
        server.send_message(msg)
        server.quit()
        print(f"Notificación enviada con éxito a: {correo_destino}")
    except Exception as e:
        print(f"Error enviando notificación: {e}")

reservas_bp = Blueprint('reservas', __name__)

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
@role_required('ADMIN', 'MAESTRO') 
def crear_reserva():
    if 'id_usuario' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for('reservas.vista_reserva'))

    id_usuario = session.get('id_usuario') 
    id_espacio = request.form.get('id_espacio')
    fecha = request.form.get('fecha')
    hora_inicio = request.form.get('hora_inicio')
    hora_fin = request.form.get('hora_fin')
    motivo = request.form.get('motivo')

    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO Reservas (id_usuario, id_espacio, fecha, hora_inicio, hora_fin, motivo, estado)
            VALUES (?, ?, ?, ?, ?, ?, 'Pendiente')
        ''', (id_usuario, id_espacio, fecha, hora_inicio, hora_fin, motivo))
        
        conn.commit()
        flash("Solicitud de reserva enviada correctamente a revisión.", "success")
        
        # --- NOTIFICAR A ADMINISTRADORES/COORDINADORES ---
        cursor.execute("""
            SELECT u.correo 
            FROM Usuarios u 
            JOIN Roles r ON u.id_rol = r.id_rol 
            WHERE r.nombre_rol IN ('Administrador', 'Coordinador') AND u.estado = 'Activo'
        """)
        correos_admins = [row[0] for row in cursor.fetchall()]
        
        if correos_admins:
            asunto = "SIGEA - Nueva Solicitud de Reserva Especial"
            mensaje = f"Se ha registrado una nueva solicitud para el día {fecha}. Ingresa a SIGEA para revisarla."
            # Enviamos el correo a la lista de admins
            enviar_notificacion_reserva(", ".join(correos_admins), asunto, mensaje)

    except Exception as e:
        flash(f"Error al guardar la reserva: {str(e)}", "danger")
    finally:
        conn.close()
    
    return redirect(url_for('reservas.vista_reserva'))

# APROBAR RESERVA (SOLO ADMIN Y COORDINADOR)
@reservas_bp.route('/reservas/aceptar/<int:id>', methods=['POST'])
@role_required('ADMIN', 'COORDINADOR') # Protegido
def aceptar_reserva(id):
    conn = get_db_connection()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for('reservas.vista_reserva'))
    
    try:
        cursor = conn.cursor()

        # Obtenemos también el correo del maestro para notificarle
        cursor.execute("""
            SELECT r.id_espacio, r.fecha, r.hora_inicio, r.hora_fin, u.correo, u.nombre, e.nombre as espacio
            FROM Reservas r
            JOIN Usuarios u ON r.id_usuario = u.id_usuario
            JOIN Espacios e ON r.id_espacio = e.id_espacio
            WHERE r.id_reserva = ?
        """, (id,))
        reserva_pendiente = cursor.fetchone()
        
        if not reserva_pendiente:
            flash("Error: No se encontró la solicitud de reserva.", "danger")
            return redirect(url_for('reservas.vista_reserva'))
        
        id_espacio, fecha, hora_inicio, hora_fin, correo_maestro, nombre_maestro, nombre_espacio = reserva_pendiente
            
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
            cursor.execute("UPDATE Reservas SET estado = 'Aprobada' WHERE id_reserva = ?", (id,))
            conn.commit()
            flash("La reserva fue aprobada con éxito.", "success")
            
            # --- NOTIFICAR AL MAESTRO ---
            asunto = "SIGEA - Tu reserva ha sido Aprobada"
            mensaje = f"Hola {nombre_maestro},\n\nTu solicitud para el espacio '{nombre_espacio}' el día {fecha} de {hora_inicio} a {hora_fin} ha sido APROBADA.\n\nSaludos."
            enviar_notificacion_reserva(correo_maestro, asunto, mensaje)
            
    except Exception as e:
        conn.rollback()
        flash(f"Error al aceptar la reserva: {str(e)}", "danger")
    finally:
        conn.close()
            
    return redirect(url_for('reservas.vista_reserva'))

# RECHAZAR RESERVA (SOLO ADMIN Y COORDINADOR)
@reservas_bp.route('/reservas/rechazar/<int:id>', methods=['POST'])
@role_required('ADMIN', 'COORDINADOR') 
def rechazar_reserva(id):
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

        cursor.execute("UPDATE Reservas SET estado = 'Rechazada' WHERE id_reserva = ?", (id,))
        conn.commit()
        flash("La reserva fue rechazada y eliminada del panel.", "success")
        
        # --- NOTIFICAR AL MAESTRO ---
        if datos_reserva:
            correo_maestro, nombre_maestro, nombre_espacio, fecha = datos_reserva
            asunto = "SIGEA - Tu reserva ha sido Rechazada"
            mensaje = f"Hola {nombre_maestro},\n\nLamentablemente tu solicitud para el espacio '{nombre_espacio}' el día {fecha} ha sido RECHAZADA.\n\nContacta a coordinación para más detalles."
            enviar_notificacion_reserva(correo_maestro, asunto, mensaje)

    except Exception as e:
        conn.rollback()
        flash(f"Error al rechazar la reserva: {str(e)}", "danger")
    finally:
        conn.close()
            
    return redirect(url_for('reservas.vista_reserva'))