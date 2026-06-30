from flask import Blueprint, render_template, request, redirect, url_for
from database.conexion import get_db_connection

asignaciones_bp = Blueprint('asignaciones', __name__)

@asignaciones_bp.route('/asignaciones')
def vista_asignaciones():
    
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute ("SELECT id_carrera, nombre_carrera FROM Carreras")
    carreras = cursor.fetchall()

    cursor.execute("""
        SELECT g.id_grupo, g.nombre_grupo, g.generacion_inicio, g.generacion_fin, c.acronimo
        FROM Grupos g
        INNER JOIN Carreras c ON g.id_carrera = c.id_carrera
        WHERE g.estatus = 'Activo' 
    """)

    grupos = cursor.fetchall()
    conn.close()

    return render_template('asignaciones.html', carreras=carreras, grupos=grupos)

@asignaciones_bp.route('/asignaciones/agregar_grupo', methods=['POST'])
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
    except Exception as e:
        print(f"Error al guardar el grupo {e}")
        conn.rollback()
    finally:
        conn.close()

    return redirect(url_for('asignaciones.vista_asignaciones'))
