from flask import Blueprint, render_template, request, redirect, url_for
from database.conexion import get_db_connection

gestion_bp = Blueprint('gestion', __name__)


# VISTA PRINCIPAL, SE MUETRAN AULAS Y EDIFICIOS

@gestion_bp.route('/gestion')
def vista_gestion():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id_edificio, nombre, codigo FROM Edificios")
    edificios = cursor.fetchall()

    cursor.execute
    ( """
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
        id_edificio = request.forn['id_edificio']
        nombre = request.form['nombre']
        capacidad = request.form['capacidad']
        tipo = request.form['tipo']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute
        ("""
            INSERT INTO Espacios (nombre, capacidad, tipo, estatus, id_edificio)
            VALUES (?, ?, ?, 'Activo', ?)
        """, (nombre, capacidad, tipo, id_edificio))

        return redirect(url_for('gestion.vista_gestion'))