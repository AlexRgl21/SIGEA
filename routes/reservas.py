from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from database.conexion import get_db_connection

reservas_bp = Blueprint('reservas', __name__)

@reservas_bp.route('/reservas')
def vista_reserva():

    #candado para mandarte al login despues del tiempo establecido
    if 'id_usuario' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    if not conn:
        flash("Error de conexión a la base de datos", "danger")
        return render_template('reservas.html', pendientes=[], aprobadas=[], espacios =[])
    
    cursor = conn.cursor()

    cursor.execute("""
        SELECT e.id_espacio, e.nombre AS espacio_nombre, ed.nombre AS edificio_nombre
        FROM Espacios e
        JOIN Edificios ed ON e.id_edificio = ed.id_edificio
        WHERE e.estatus = 'Activo' AND e.tipo IN ('laboratorio', 'sala de conferencia')
    """)

    espacios = cursor.fetchall()

    cursor.execute("""
        SELECT r.id_reserva, r.fecha, r.hora_inicio, r.hora_fin, r.motivo, r.estado,
            u.nombre, u.apellidos,
            e.nombre AS espacio_nombre, ed.nombre AS edificio_nombre
        FROM Reservas r
        JOIN Usuarios u ON r.id_usuario = u.id_usuario
        JOIN Espacios e ON r.id_espacio = e.id_espacio
        JOIN Edificios ed ON e.id_edificio = ed.id_edificio
        ORDER BY R.fecha ASC, r.hora_inicio ASC
    """)

    todas_reservas = cursor.fetchall()

    pendientes = [res for res in todas_reservas if res.estado == 'Pendiente']
    aprobadas = [res for res in todas_reservas if res.estado == 'Aprobada']

    conn.close()

    return render_template('reservas.html', pendientes = pendientes, 
                                            aprobadas = aprobadas,
                                            espacios = espacios)

@reservas_bp.route('/reservas/nueva', methods=['POST'])
def crear_reserva():
    # Candado de seguridad
    if 'id_usuario' not in session:
        return redirect(url_for('auth.login'))

    # datos del formulario
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