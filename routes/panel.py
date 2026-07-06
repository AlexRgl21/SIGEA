from flask import Blueprint, render_template, session, redirect, url_for
from database.conexion import get_db_connection
from datetime import date, datetime
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

    # espacios libres y ocupados
    ahora = datetime.now()
    hora_actual = ahora.strftime('%H:%M:%S')
    fecha_hoy = ahora.date()

    dias_semana = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo']
    dia_hoy = dias_semana[ahora.weekday()]

    # SALONES QUE TIENEN CLASE
    cursor.execute("""
        SELECT COUNT(DISTINCT a.id_espacio)
        FROM Asignaciones a
        JOIN Horarios h ON a.id_asignacion = h.id_asignacion
        WHERE h.dia_semana = ? 
          AND h.hora_inicio <= CAST(? AS TIME) 
          AND h.hora_fin > CAST(? AS TIME)
    """, (dia_hoy, hora_actual, hora_actual))
    ocupados_por_clase = cursor.fetchone()[0] or 0

    # RESERVAS ESPECIALES 
    cursor.execute("""
        SELECT COUNT(DISTINCT id_espacio)
        FROM Reservas
        WHERE fecha = ? AND estado = 'Aprobada'
          AND hora_inicio <= CAST(? AS TIME) 
          AND hora_fin > CAST(? AS TIME)
    """, (fecha_hoy, hora_actual, hora_actual))
    ocupados_por_reserva = cursor.fetchone()[0] or 0

    ocupados = ocupados_por_clase + ocupados_por_reserva

    libres = total_espacios - bloqueados - ocupados
    libres = max(0, libres)


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
        ocupados_edificios = row.espacios_ocupados_hoy

        porcentaje = 0
        if total > 0 :
            porcentaje = int((ocupados_edificios / total) * 100)
        
        datos_grafica.append({
            'edificio' : nombre,
            'porcentaje' : porcentaje
        })

    # TABLA DE DISPONIBILIDAD 
    cursor.execute("""
        SELECT e.id_espacio, e.nombre AS espacio, ed.nombre AS edificio
        FROM Espacios e
        JOIN Edificios ed ON e.id_edificio = ed.id_edificio
        WHERE e.estatus = 'Activo' 
          AND e.nombre LIKE 'Salón%' 
        ORDER BY ed.nombre, CAST(SUBSTRING(e.nombre, 7, LEN(e.nombre)) AS INT)
    """)
    todos_espacios = cursor.fetchall()

    # GRUPOS QUE ESTAN EN CLASE 
    cursor.execute("""
        SELECT a.id_espacio, g.nombre_grupo, h.hora_inicio, h.hora_fin
        FROM Asignaciones a
        JOIN Horarios h ON a.id_asignacion = h.id_asignacion
        JOIN Grupos g ON a.id_grupo = g.id_grupo
        WHERE h.dia_semana = ? 
          AND h.hora_inicio <= CAST(? AS TIME) 
          AND h.hora_fin > CAST(? AS TIME)   
    """, (dia_hoy, hora_actual, hora_actual))
    clases_ahora = {row[0]: {'grupo': row[1], 'horario': f"{str(row[2])[:5]} - {str(row[3])[:5]}"} for row in cursor.fetchall()}

    # PROXIMAS CLASES
    cursor.execute("""
        SELECT a.id_espacio, g.nombre_grupo, h.hora_inicio, h.hora_fin
        FROM Asignaciones a
        JOIN Horarios h ON a.id_asignacion = h.id_asignacion
        JOIN Grupos g ON a.id_grupo = g.id_grupo
        WHERE h.dia_semana = ? 
          AND h.hora_inicio > CAST(? AS TIME)
        ORDER BY h.hora_inicio ASC
    """, (dia_hoy, hora_actual))

    clases_proximas = {}
    for row in cursor.fetchall():
        id_esp = row[0]
        if id_esp not in clases_proximas:
            clases_proximas[id_esp] = {'grupo': row[1], 'horario': f"{str(row[2])[:5]} - {str(row[3])[:5]}"}


    tabla_disponibilidad = []
    for esp in todos_espacios:
        id_espacio = esp[0]
        nombre_espacio = esp[1]
        nombre_edificio = esp[2]

        grupo = "-"
        horario = "-"
        estatus_final = "Libre"
        badge_class = "badge-disponible"

        if id_espacio in clases_ahora:
            grupo = clases_ahora[id_espacio]['grupo']
            horario = clases_ahora[id_espacio]['horario']
            estatus_final = "Ocupado"
            badge_class = "badge-ocupado"
        elif id_espacio in clases_proximas:
            grupo = clases_proximas[id_espacio]['grupo']
            horario = clases_proximas[id_espacio]['horario']
            estatus_final = "Próximo"
            badge_class = "badge-proximo"

        tabla_disponibilidad.append({
            'edificio' : nombre_edificio,
            'espacio' : nombre_espacio,
            'grupo' : grupo,
            'horario' : horario,
            'estatus' : estatus_final, 
            'badge_class' : badge_class
        })


    conn.close()
    
    return render_template('principal.html', 
                            total_espacios=total_espacios, 
                            bloqueados=bloqueados,  
                            reservas_hoy=reservas_hoy, 
                            datos_grafica=datos_grafica,
                            dia_hoy=dia_hoy, 
                            ocupados=ocupados, 
                            libres=libres,
                            tabla_disponibilidad=tabla_disponibilidad)
                            