from flask import Blueprint, render_template, request, redirect, url_for
from database.conexion import get_db_connection

usuarios_bp = Blueprint('usuarios', __name__)

@usuarios_bp.route('/usuarios')
def lista_usuarios():
    conn = get_db_connection()

    if conn:
        cursor = conn.cursor()

        consulta = """
            SELECT 
                id_usuario,
                nombre, 
                apellidos,
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
    
@usuarios_bp.route('/usuarios/agregar', methods=['POST'])
def agregar_usuario():
    nombre = request.form['nombre']
    apellidos = request.form['apellidos']
    correo = request.form['correo']
    contrasena = request.form['contrasena']
    id_rol = request.form['id_rol']
    estado = 'Activo'

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()

        consulta = """
            INSERT INTO Usuarios (nombre, apellidos, correo, contrasena, id_rol, estado)
            VALUES (?, ?, ?, ?, ?, ?)
        """

        cursor.execute(consulta, (nombre, apellidos, correo, contrasena, id_rol, estado))
        conn.commit()

        cursor.close()
        conn.close()
        
    return redirect(url_for('usuarios.lista_usuarios'))

@usuarios_bp.route('/usuarios/configurar/<int:id>', methods=['POST'])
def configurar_usuario(id):
    # 1. Imprimimos en la terminal negra lo que realmente llegó
    print("====== ATENCIÓN: DATOS RECIBIDOS ======")
    print(request.form)
    print("=======================================")

    # 2. Usamos .get() para evitar que la página colapse
    id_rol = request.form.get('id_rol')
    estado = request.form.get('estado')

    # 3. Si 'estado' viene vacío, pausamos todo y te lo mostramos en pantalla
    if estado is None:
        return f"<h3>¡El navegador sigue mandando los datos viejos!</h3> <p>Esto es lo que llegó a Python: {request.form}</p> <p>Por favor, regresa a la página y presiona <b>Ctrl + F5</b>.</p>"

    # 4. Si todo está bien, guardamos en la base de datos
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Usuarios 
            SET id_rol = ?, estado = ? 
            WHERE id_usuario = ?
        """, (id_rol, estado, id))
        conn.commit()
        cursor.close()
        conn.close()
        
    return redirect(url_for('usuarios.lista_usuarios'))

@usuarios_bp.route('/usuarios/editar/<int:id>', methods=['POST'])
def editar_usuario(id):
    # Usamos .get() para evitar los errores de BadRequestKeyError
    nombre = request.form.get('nombre')
    apellidos = request.form.get('apellidos')
    correo = request.form.get('correo')

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE Usuarios 
            SET nombre = ?, apellidos = ?, correo = ? 
            WHERE id_usuario = ?
        """, (nombre, apellidos, correo, id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    return redirect(url_for('usuarios.lista_usuarios'))