from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.conexion import get_db_connection
from .auth import role_required # Importamos el decorador

asignaciones_bp = Blueprint('asignaciones', __name__)

@asignaciones_bp.route('/asignaciones')
@role_required('ADMIN', 'COORDINADOR', 'MAESTRO') # Todos pueden ver el calendario
def vista_asignaciones():
    
    if 'id_usuario' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute ("SELECT id_carrera, nombre_carrera, acronimo FROM Carreras")
    carreras = cursor.fetchall()

    cursor.execute("""
        SELECT g.id_grupo, g.nombre_grupo, g.generacion_inicio, g.generacion_fin, c.acronimo, g.id_carrera
        FROM Grupos g
        INNER JOIN Carreras c ON g.id_carrera = c.id_carrera
        WHERE g.estatus = 'Activo' 
    """)
    grupos = cursor.fetchall()

    cursor.execute("SELECT id_espacio, nombre, id_edificio FROM Espacios WHERE estatus = 'Activo' AND tipo = 'Aula Clásica'")
    espacios = cursor.fetchall()

    cursor.execute("SELECT id_periodo, nombre FROM Periodos WHERE activo = 1")
    periodos = cursor.fetchall()

    cursor.execute("""
        SELECT g.nombre_grupo, h.dia_semana, h.hora_inicio, h.hora_fin, a.id_espacio, e.id_edificio
        FROM Horarios h
        JOIN Asignaciones a ON h.id_asignacion = a.id_asignacion
        JOIN Grupos g ON a.id_grupo = g.id_grupo
        JOIN Espacios e ON a.id_espacio = e.id_espacio
    """)
    horarios_db = cursor.fetchall()

    mapa_dias = {'Lunes': 1, 'Martes': 2, 'Miércoles': 3, 'Jueves': 4, 'Viernes': 5, 'Sábado': 6}
    eventos_calendario = []

    for h in horarios_db:
        nombre_grupo = h[0]
        dia_num = mapa_dias.get(h[1], 1)
        hora_inicio_str = h[2].strftime('%H:%M:%S')
        hora_fin_str = h[3].strftime('%H:%M:%S')

        eventos_calendario.append({
            'title': nombre_grupo,
            'daysOfWeek': [dia_num],
            'startTime': hora_inicio_str,
            'endTime': hora_fin_str,
            'color': '#004a98' ,
            'extendedProps': {
                'id_espacio' : h[4],
                'id_edificio' : h[5]
            } 
        })
    
    cursor.execute("SELECT id_edificio, nombre FROM Edificios")
    edificios = cursor.fetchall()

    conn.close()

    return render_template('asignaciones.html', carreras=carreras, grupos=grupos, espacios=espacios, periodos=periodos, edificios=edificios, eventos_calendario=eventos_calendario)

# AGREGAR ASIGNACION
@asignaciones_bp.route('/asignaciones/nueva_asignacion', methods=['POST'])
@role_required('ADMIN', 'COORDINADOR') # Protegido
def nueva_asignacion():
    id_grupo = int(request.form.get('id_grupo'))
    id_espacio = int(request.form.get('id_espacio'))
    id_periodo = int(request.form.get('id_periodo')) 
    hora_inicio = request.form.get('hora_inicio')
    hora_fin = request.form.get('hora_fin')
    dias = request.form.getlist('dias') 

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        for dia in dias:
            cursor.execute("""
                SELECT a.id_grupo, h.hora_inicio, h.hora_fin
                FROM Horarios h
                JOIN Asignaciones a ON h.id_asignacion = a.id_asignacion
                WHERE a.id_espacio = ? 
                  AND a.id_periodo = ?
                  AND h.dia_semana = ?
                  AND (h.hora_fin > CAST(? AS TIME) AND h.hora_inicio < CAST(? AS TIME))
            """, (id_espacio, id_periodo, dia, hora_inicio, hora_fin))
            
            choque = cursor.fetchone()
            
            if choque:
                hora_c_inicio = choque[1].strftime('%H:%M')
                hora_c_fin = choque[2].strftime('%H:%M')
                flash(f"Choque detectado el {dia}: El salón ya está ocupado de {hora_c_inicio} a {hora_c_fin}.", "danger")
                return redirect(url_for('asignaciones.vista_asignaciones'))

        cursor.execute("""
            INSERT INTO Asignaciones (id_grupo, id_espacio, id_periodo)
            OUTPUT INSERTED.id_asignacion
            VALUES (?, ?, ?)
        """, (id_grupo, id_espacio, id_periodo))
        
        id_nueva_asignacion = cursor.fetchone()[0]

        for dia in dias:
            cursor.execute('''
                INSERT INTO Horarios (id_asignacion, dia_semana, hora_inicio, hora_fin)
                VALUES (?, ?, CAST(? AS TIME), CAST(? AS TIME))
            ''', (id_nueva_asignacion, dia, hora_inicio, hora_fin))
            
        conn.commit()
        flash("Horario asignado con éxito. No se detectaron empalmes.", "success")

    except Exception as e:
        conn.rollback()
        print(f"Error crítico en asignación: {e}")
        flash("Ocurrió un error interno al intentar guardar el horario.", "danger")
    finally:
        conn.close()

    return redirect(url_for('asignaciones.vista_asignaciones'))

# AGREGAR GRUPO
@asignaciones_bp.route('/asignaciones/agregar_grupo', methods=['POST'])
@role_required('ADMIN', 'COORDINADOR') # Protegido
def agregar_grupo():
    nombre_grupo = request.form.get('nombre_grupo')
    generacion_inicio = request.form.get('generacion_inicio')
    generacion_fin = request.form.get('generacion_fin')
    id_carrera = request.form.get('id_carrera')

    if not generacion_fin or generacion_fin.strip() == "":
        generacion_fin = None
    else:
        generacion_fin = int(generacion_fin)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO Grupos (nombre_grupo, generacion_inicio, generacion_fin, id_carrera, estatus)
            VALUES (?, ?, ?, ?, 'Activo') 
        """, (nombre_grupo, int(generacion_inicio), generacion_fin, int(id_carrera) ))

        conn.commit()
        flash(f"El grupo {nombre_grupo} se registro correctamente.", "success")
    except Exception as e:
        print(f"Error al guardar el grupo {e}")
        conn.rollback()
        flash(f"Ocurrio un error al intentar guardar el grupo. Intentalo de nuevo.", "danger")
    finally:
        conn.close()

    return redirect(url_for('asignaciones.vista_asignaciones'))

# ELIMINAR GRUPO
@asignaciones_bp.route('/asignaciones/eliminar_grupo/<int:id_grupo>', methods=['POST'])
@role_required('ADMIN', 'COORDINADOR') # Protegido
def eliminar_grupo(id_grupo):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("UPDATE Grupos SET estatus = 'Inactivo' WHERE id_grupo = ?", (id_grupo,))
        conn.commit()
        flash(f"El grupo ha sido eliminado.", "success")
    except Exception as e:
        print(f"Error al eliminar el grupo: {e}")
        conn.rollback()
        flash(f"No se pudo eliminar el grupo. Intentalo de nuevo.", "danger")
    finally:
        conn.close()

    return redirect(url_for('asignaciones.vista_asignaciones'))

# EDITAR GRUPO
@asignaciones_bp.route('/asignaciones/editar_grupo/<int:id_grupo>', methods=['POST'])
@role_required('ADMIN', 'COORDINADOR') # Protegido
def editar_grupo(id_grupo):
    nombre_grupo = request.form.get('nombre_grupo')
    generacion_inicio = request.form.get('generacion_inicio')
    generacion_fin = request.form.get('generacion_fin')
    id_carrera = request.form.get('id_carrera')

    if not generacion_fin or generacion_fin.strip() == "":
        generacion_fin = None
    else:
        generacion_fin = int(generacion_fin)
    
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE Grupos
            SET nombre_grupo = ?, generacion_inicio = ?, generacion_fin = ?, id_carrera = ?
            WHERE id_grupo = ? 
        """, (nombre_grupo, int(generacion_inicio), generacion_fin, int(id_carrera), id_grupo))

        conn.commit()
        flash('El grupo fue actualizado correctamente.', 'success')
    except Exception as e:
        print(f"Error al actualizar el grupo {e}")
        conn.rollback()
        flash(f"Error al intentar actualizar los datos del grupo.", "danger")
    finally:
        conn.close()

    return redirect(url_for('asignaciones.vista_asignaciones'))