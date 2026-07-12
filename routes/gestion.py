from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database.conexion import get_db_connection

gestion_bp = Blueprint('gestion', __name__)

colores_edificios = {
        'Edi - 1' : '#324F85',
        'Edi - 2' : '#D12424',
        'Edi - 3' : '#3A7824',
        'Metra' : '#F2E052',
        'Learning' : '#6F0EB5'
    }

# VISTA PRINCIPAL, SE MUETRAN AULAS Y EDIFICIOS
@gestion_bp.route('/gestion')
def vista_gestion():
    #candado para mandarte al login despues del tiempo establecido
    if 'id_usuario' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()

    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for('gestion.html', edificios=[], aulas=[])
                        )
    cursor = conn.cursor()

    cursor.execute("SELECT id_edificio, nombre, codigo, estatus FROM Edificios")
    edificios_db = cursor.fetchall()

    cursor.execute( """
        SELECT e.id_espacio, e.nombre, e.capacidad, e.tipo, e.estatus, ed.codigo
        FROM Espacios e
        INNER JOIN Edificios ed ON e.id_edificio = ed.id_edificio
    """)
                
    aulas_db = cursor.fetchall()
    conn.close()

    edificios = [
        tuple(ed) + (colores_edificios.get(str(ed[2]).strip(), '#004a98'),)
        for ed in edificios_db
    ]
    
    aulas = [
        tuple(au) + (colores_edificios.get(str(au[5]).strip(), '#004a98'),)
        for au in aulas_db
    ]

    return render_template('gestion.html', edificios=edificios, aulas=aulas)


# AGREGAR ESPACIO
@gestion_bp.route('/gestion/agregar_espacio', methods=['POST'])
def agregar_espacio():

    id_edificio = request.form.get('id_edificio')
    nombre = request.form.get('nombre')
    capacidad = request.form.get('capacidad')
    tipo = request.form.get('tipo')

    conn = get_db_connection()
    if not conn:
        flash("Error de conexión en la base de datos.", "danger")
        return redirect(url_for('gestion.vista_gestion'))
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Espacios (nombre, capacidad, tipo, id_edificio)
            VALUES (?, ?, ?, ?)
        """, (nombre, capacidad, tipo, id_edificio))
        conn.commit()
        flash("Espacio agregado exitosamente al catálogo.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error al agregar el espacio: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for('gestion.vista_gestion'))
    

# EDITAR EDIFICIO
@gestion_bp.route('/gestion/editar_edificio', methods=['POST'])
def editar_edificio():

    id_edificio = request.form['id_edificio']
    nombre = request.form['nombre']
    codigo = request.form['codigo']
    estatus = request.form['estatus']

    conn = get_db_connection()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for('gestion.vista_gestion'))
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
                UPDATE Edificios
                SET nombre = ?, codigo = ?, estatus = ?
                WHERE id_edificio = ? 
                """, (nombre, codigo, estatus, id_edificio))
    
        # EFECTO CASACA DEPENDIENDO DEL ESTATUS DEL EDIFICIO
        cursor.execute("""
                UPDATE Espacios
            SET estatus = ?
                WHERE id_edificio = ?
            """, (estatus, id_edificio))
        conn.commit()
        flash("Edificio y sus espacios actualizados correctamente.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error al actualizar el edificio: {str(e)}", "danger")
    finally:
        conn.close()
    
    return redirect(url_for('gestion.vista_gestion'))
    

# EDITAR AULAS
@gestion_bp.route('/gestion/editar_espacio', methods=['POST'])
def editar_espacio():
    
    id_espacio = request.form['id_espacio']
    id_edificio = request.form['id_edificio']
    nombre = request.form['nombre']
    capacidad = request.form['capacidad']
    tipo = request.form['tipo']
    estatus = request.form['estatus']

    conn = get_db_connection()
    if not conn:
        flash("Error de conexión en la base de datos.", "danger")
        return redirect(url_for('gestion.vista_gestion'))
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Espacios
            SET nombre = ?, capacidad = ?, tipo = ?, estatus = ?, id_edificio = ?
            WHERE id_espacio = ?
            """, (nombre, capacidad, tipo, estatus, id_edificio, id_espacio))
        conn.commit()
        flash("Información del espacio modificada con éxito.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error al actualizar el espacio: {str(e)}", "danger")
    finally:
        conn.close()
        
    return redirect(url_for('gestion.vista_gestion'))
    
# ELIMINAR AULA
@gestion_bp.route('/gestion/eliminar_espacio/<int:id>', methods=['POST'])
def eliminar_espacio(id):
    conn = get_db_connection()
    if not conn:
        flash("Error de conexión en la base de datos.", "danger")
        return redirect(url_for('gestion.vista_gestion'))
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Espacios WHERE id_espacio = ?", (id,))
        conn.commit()
        flash("El espacio fue eliminado del sistema.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error al eliminar el espacio: {str(e)}", "danger")
    finally:
        conn.close()
    
    return redirect(url_for('gestion.vista_gestion'))

        
        