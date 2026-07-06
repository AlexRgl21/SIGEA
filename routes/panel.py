from flask import Blueprint, render_template, session, redirect, url_for
from database.conexion import get_db_connection
from datetime import date
from .auth import role_required # Importamos el decorador

panel_bp = Blueprint('panel', __name__)

@panel_bp.route('/panel')
@role_required('ADMIN', 'COORDINADOR') # Protegido: El maestro no entra aquí
def inicio():
    
    if 'id_usuario' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    if not conn:
        return render_template('principal.html', total_espacios = 0, bloqueados=0, reservas_hoy=[])
    
    cursor = conn.cursor()

    # CALCULO DE KPIs
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

    # GRAFICAS DE OCUPACIÓN 
    dias_semana = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo']
    dia_hoy = dias_semana[hoy.weekday()]

    cursor.execute("""
        SELECT 
            ed.nombre AS nombre_edificio,
            COUNT(DISTINCT es.id_espacio) AS total_espacios,
            COUNT(DISTINCT CASE WHEN h.dia_semana = ? THEN a.id_espacio END) AS espacios_ocupados_hoy
        FROM Edificios ed
        LEFT JOIN Espacios es ON ed.id_edificio = es.id_edificio AND es.estatus = 'Activo'
        LEFT JOIN Asignaciones a ON es.id_espacio = a.id_espacio
        LEFT JOIN Horarios h ON a.id_asignacion = h.id_asignacion
        GROUP BY ed.nombre
        HAVING COUNT(DISTINCT CASE WHEN h.dia_semana = ? THEN a.id_espacio END) > 0
    """, (dia_hoy, dia_hoy))
    resultados_ocupacion = cursor.fetchall()

    datos_grafica = []
    for row in resultados_ocupacion:
        nombre = row.nombre_edificio
        total = row.total_espacios
        ocupados = row.espacios_ocupados_hoy

        porcentaje = 0
        if total > 0 :
            porcentaje = int((ocupados / total) * 100)
        
        datos_grafica.append({
            'edificio' : nombre,
            'porcentaje' : porcentaje
        })

    conn.close()
    
    return render_template('principal.html', 
                            total_espacios=total_espacios, 
                            bloqueados=bloqueados,  
                            reservas_hoy=reservas_hoy, 
                            datos_grafica=datos_grafica,
                            dia_hoy=dia_hoy)