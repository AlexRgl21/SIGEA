from flask import Blueprint, render_template
from database.conexion import get_db_connection

usuarios_bp = Blueprint('usuarios', __name__)

@usuarios_bp.route('/usuarios')
def lista_usuarios():
    conn = get_db_connection()

    if conn:
        cursor = conn.cursor()

        consulta = """
            SELECT 
                nombre + ' ' + apellidos AS nombre_completo,
                correo,
                estado,
                CASE 
                    WHEN id_rol = 1 THEN 'Administrador'
                    WHEN id_rol = 2 THEN 'Coordinador de Carrera' 
                    WHEN id_rol = 3 THEN 'Docente' 
                END AS rol_nombre
            FROM Usuarios
        """

        cursor.execute(consulta)
        filas = cursor.fetchall()

        columnas = [columna[0] for columna in cursor.description]
        usuarios_db = [dict(zip(columnas, fila)) for fila in filas]

        conn.close()

        return render_template('usuarios.html', usuarios=usuarios_db)
    else:
        return render_template('usuarios.html', usuarios=[], error="Sin conexión a BD")