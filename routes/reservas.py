from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from database.conexion import get_db_connection
from .auth import role_required # Importamos el decorador

reservas_bp = Blueprint('reservas', __name__)

@reservas_bp.route('/reservas')
@role_required('ADMIN', 'COORDINADOR', 'MAESTRO') # Todos pueden ver el estatus
def vista_reserva():
    
    if 'id_usuario' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    if not conn:
        flash("Error de conexión a la base de datos", "danger")
        return render_template('reservas.html', pendientes=[], aprobadas=[], espacios=[])
    
    cursor = conn.cursor()

    # 1. Traer los espacios disponibles para el formulario
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

    if rol_actual == 'MAESTRO':
        # El maestro ve sus reservas (Futuras o que sigan Pendientes)
        cursor.execute("""
            SELECT r.id_reserva, r.fecha, r.hora_inicio, r.hora_fin, r.motivo, r.estado,
                u.nombre, u.apellidos,
                e.nombre AS espacio_nombre, ed.nombre AS edificio_nombre
            FROM Reservas r
            JOIN Usuarios u ON r.id_usuario = u.id_usuario
            JOIN Espacios e ON r.id_espacio = e.id_espacio
            JOIN Edificios ed ON e.id_edificio = ed.id_edificio
            WHERE r.id_usuario = ? AND (r.fecha >= CAST(GETDATE() AS DATE) OR r.estado = 'Pendiente')
            ORDER BY r.fecha ASC, r.hora_inicio ASC
        """, (id_usuario_actual,))
       
    else:
        # Admin y Coordinador ven TODO lo futuro y TODAS las pendientes sin importar la fecha
        cursor.execute("""
            SELECT r.id_reserva, r.fecha, r.hora_inicio, r.hora_fin, r.motivo, r.estado,
                u.nombre, u.apellidos,
                e.nombre AS espacio_nombre, ed.nombre AS edificio_nombre
            FROM Reservas r
            JOIN Usuarios u ON r.id_usuario = u.id_usuario
            JOIN Espacios e ON r.id_espacio = e.id_espacio
            JOIN Edificios ed ON e.id_edificio = ed.id_edificio
            WHERE r.fecha >= CAST(GETDATE() AS DATE) OR r.estado = 'Pendiente'
            ORDER BY r.fecha ASC, r.hora_inicio ASC
        """)

    cols_res = [col[0] for col in cursor.description]
    todas_reservas = [dict(zip(cols_res, row)) for row in cursor.fetchall()]
    
    pendientes = [res for res in todas_reservas if str(res['estado']).strip().capitalize() == 'Pendiente']
    aprobadas = [res for res in todas_reservas if str(res['estado']).strip().capitalize() == 'Aprobada']

    conn.close()

    return render_template('reservas.html', pendientes=pendientes, 
                                            aprobadas=aprobadas,
                                            espacios=espacios)

# CREAR RESERVA (SOLO ADMIN Y MAESTRO)
@reservas_bp.route('/reservas/nueva', methods=['POST'])
@role_required('ADMIN', 'MAESTRO') # Protegido
def crear_reserva():
    if 'id_usuario' not in session:
        return redirect(url_for('auth.login'))

    id_usuario = session['id_usuario'] 
    id_espacio = request.form.get('id_espacio')
    fecha = request.form.get('fecha')
    hora_inicio = request.form.get('hora_inicio')
    hora_fin = request.form.get('hora_fin')
    motivo = request.form.get('motivo')

    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO Reservas (id_usuario, id_espacio, fecha, hora_inicio, hora_fin, motivo, estado)
                VALUES (?, ?, ?, ?, ?, ?, 'Pendiente')
            ''', (id_usuario, id_espacio, fecha, hora_inicio, hora_fin, motivo))
            
            conn.commit()
            flash("Solicitud de reserva enviada correctamente a revisión.", "success")
        except Exception as e:
            flash(f"Error al guardar la reserva: {str(e)}", "error")
        finally:
            conn.close()
    
    return redirect(url_for('reservas.vista_reserva'))

# APROBAR RESERVA (SOLO ADMIN Y COORDINADOR)
@reservas_bp.route('/reservas/aceptar/<int:id>', methods=['POST'])
@role_required('ADMIN', 'COORDINADOR') # Protegido
def aceptar_reserva(id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id_espacio, fecha, hora_inicio, hora_fin 
                FROM Reservas 
                WHERE id_reserva = ?
            """, (id,))
            reserva_pendiente = cursor.fetchone()
            
            if reserva_pendiente:
                id_espacio, fecha, hora_inicio, hora_fin = reserva_pendiente
                
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM Reservas
                    WHERE id_espacio = ? 
                      AND fecha = ? 
                      AND estado = 'Aprobada'
                      AND hora_inicio < ? -- La nueva hora fin
                      AND hora_fin > ?    -- La nueva hora inicio
                """, (id_espacio, fecha, hora_fin, hora_inicio))
                
                empalmes = cursor.fetchone()[0]
                
                if empalmes > 0:
                    flash("No se puede aprobar: El espacio ya cuenta con una reserva en ese horario.", "danger")
                else:
                    cursor.execute("UPDATE Reservas SET estado = 'Aprobada' WHERE id_reserva = ?", (id,))
                    conn.commit()
                    flash("La reserva fue aprobada con éxito.", "success")
            else:
                flash("Error: No se encontró la solicitud de reserva.", "danger")
                
        except Exception as e:
            conn.rollback()
            flash(f"Error al aceptar la reserva: {str(e)}", "danger")
        finally:
            conn.close()
            
    return redirect(url_for('reservas.vista_reserva'))

# RECHAZAR RESERVA (SOLO ADMIN Y COORDINADOR)
@reservas_bp.route('/reservas/rechazar/<int:id>', methods=['POST'])
@role_required('ADMIN', 'COORDINADOR') # Protegido
def rechazar_reserva(id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE Reservas SET estado = 'Rechazada' WHERE id_reserva = ?", (id,))
            conn.commit()
            flash("La reserva fue rechazada y eliminada del panel.", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Error al rechazar la reserva: {str(e)}", "danger")
        finally:
            conn.close()
            
    return redirect(url_for('reservas.vista_reserva'))