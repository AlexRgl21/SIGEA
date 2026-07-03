from flask import Blueprint, render_template, request, redirect, url_for, session
from database.conexion import get_db_connection

gestion_bp = Blueprint('gestion', __name__)


# VISTA PRINCIPAL, SE MUETRAN AULAS Y EDIFICIOS

@gestion_bp.route('/gestion')
def vista_gestion():
    #candado para mandarte al login despues del tiempo establecido
    if 'id_usuario' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id_edificio, nombre, codigo, estatus FROM Edificios")
    edificios = cursor.fetchall()

    cursor.execute( """
        SELECT e.id_espacio, e.nombre, e.capacidad, e.tipo, e.estatus, ed.codigo
        FROM Espacios e
        INNER JOIN Edificios ed ON e.id_edificio = ed.id_edificio
    """)
                
    aulas = cursor.fetchall()
    
    conn.close()
    return render_template('gestion.html', edificios=edificios, aulas=aulas)

# AGREGAR ESPACIO

@gestion_bp.route('/gestion/agregar_espacio', methods=['POST'])
def agregar_espacio():
    if request.method == 'POST':
        id_edificio = request.form['id_edificio']
        nombre = request.form['nombre']
        capacidad = request.form['capacidad']
        tipo = request.form['tipo']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO Espacios (nombre, capacidad, tipo, id_edificio)
            VALUES (?, ?, ?, ?)
        """, (nombre, capacidad, tipo, id_edificio))

        conn.commit()
        conn.close()

        return redirect(url_for('gestion.vista_gestion'))
    
# EDITAR EDIFICIO

@gestion_bp.route('/gestion/editar_edificio', methods=['POST'])
def editar_edificio():
    if request.method == 'POST':
        id_edificio = request.form['id_edificio']
        nombre = request.form['nombre']
        codigo = request.form['codigo']
        estatus = request.form['estatus']

        conn = get_db_connection()
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
        conn.close()
        return redirect(url_for('gestion.vista_gestion'))
    

# EDITAR AULAS

@gestion_bp.route('/gestion/editar_espacio', methods=['POST'])
def editar_espacio():
    if request.method == 'POST':
        id_espacio = request.form['id_espacio']
        id_edificio = request.form['id_edificio']
        nombre = request.form['nombre']
        capacidad = request.form['capacidad']
        tipo = request.form['tipo']
        estatus = request.form['estatus']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Espacios
            SET nombre = ?, capacidad = ?, tipo = ?, estatus = ?, id_edificio = ?
            WHERE id_espacio = ?
            """, (nombre, capacidad, tipo, estatus, id_edificio, id_espacio))
        
        conn.commit()
        conn.close()
        return redirect(url_for('gestion.vista_gestion'))
    
# ELIMINAR AULA
@gestion_bp.route('/gestion/eliminar_espacio/<int:id>', methods=['POST'])
def eliminar_espacio(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Espacios WHERE id_espacio = ?", (id,))

    conn.commit()
    conn.close()
    
    return redirect(url_for('gestion.vista_gestion'))
        
        