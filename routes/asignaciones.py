from flask import Blueprint, render_template, request, redirect, url_for
from database.conexion import get_db_connection

asignaciones_bp = Blueprint('asignaciones', __name__)

@asignaciones_bp.route('/asignaciones')
def vista_asignaciones():
    return render_template('asignaciones.html')

@asignaciones_bp.route('/asignaciones/agregar_grupo', methods=['POST'])
def agregar_grupo():
    nombre_grupo = request.form('nombre_grupo')
    generacion_inicio = request.form('generacion_inicio')
    generacion_fin = request.form('generacion_fin')
    id_carrera = request.form('id_carrera')

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
