from flask import Blueprint, render_template, session, redirect, url_for
from database.conexion import get_db_connection
from datetime import date

panel_bp = Blueprint('panel', __name__)

@panel_bp.route('/panel')
def inicio():
    #candado para mandarte al login despues del tiempo establecido
    if 'id_usuario' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    if not conn:
        return render_template('principal.html', total_espacios = 0, bloqueados=0, reservas_hoy=[])
    
    cursor = conn.cursor()

    # CALCULO DE KPIs
    # ESPACIOS REGISTRADOS
    cursor.execute("SELECT COUNT(*) FROM Espacios")
    total_espacios = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM Espacios WHERE estatus = 'Mantenimiento' ")
    bloqueados = cursor.fetchone()[0] or 0


    # RESERVAS DE HOY
    hoy = date.today()
    cursor.execute(""" 
        SELECT ed.nombre as edificio, e.nombre as espacio, r.hora_inicio, r.hora_fin
        FROM Reservas r
        JOIN Espacios e ON r.id_espacio = e.id_espacio
        JOIN Edificios ed ON e.id_edificio = ed.id_edificio
        WHERE r.fecha = ? AND r.estado = 'Aprobada'
        ORDER BY r.hora_inicio ASC
     """, (hoy,))
    
    reservas_hoy = cursor.fetchall()

    conn.close()
    
    return render_template('principal.html', total_espacios=total_espacios, bloqueados=bloqueados, reservas_hoy=reservas_hoy)