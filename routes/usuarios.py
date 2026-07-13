from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database.conexion import get_db_connection
import string
import secrets
import smtplib
from email.message import EmailMessage
from werkzeug.security import generate_password_hash
import threading

usuarios_bp = Blueprint('usuarios', __name__)

def enviar_correo_bienvenida(correo_destino, nombre_usuario, password_temporal):
    correo_emisor = "cuentapruebasigea@gmail.com"
    password_emisor = "ndaz qtsz wxvv ejbq"

    msg = EmailMessage()
    msg['Subject'] = 'Bienvenido a SIGEA - Tus credenciales de acceso'
    msg['From'] = correo_emisor
    msg['To'] = correo_destino
    
    contenido = f""" Hola {nombre_usuario}, 
Has sido registrado exitosamente en el Sistema Integral de Gestión de Espacios Académicos (SIGEA).

Tus credenciales de acceso son:
Usuario / Correo: {correo_destino}
Contraseña Temporal: {password_temporal}

Te recomendamos iniciar sesión lo antes posible. 

Saludos, 
El equipo de SIGEA. 
"""

    msg.set_content(contenido)

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(correo_emisor, password_emisor)
        server.send_message(msg)
        server.quit()

    except Exception as e:
        print(f"Error asícrono al enviar el correo: {e}")

# SOLICITAR TODOS LOS USUARIOS REGISTRADOS
@usuarios_bp.route('/usuarios')
def lista_usuarios():

    #candado para mandarte al login despues del tiempo establecido
    if 'id_usuario' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()

    if not conn:
        return render_template('usuarios.html', usuarios = [], error = "Sin conexión a la base de datos")
    
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

    
# AGREGAR A UN NUEVO USUARIO
@usuarios_bp.route('/usuarios/agregar', methods=['POST'])
def agregar_usuario():
    nombre = request.form['nombre']
    apellidos = request.form['apellidos']
    correo = request.form['correo']
    id_rol = request.form['id_rol']
    estado = 'Activo'

    if session.get('role') != 'ADMIN':
        id_rol = '3'

    alfabeto = string.ascii_letters + string.digits
    password_temporal = ''.join(secrets.choice(alfabeto) for i in range(8))
    password_hash = generate_password_hash(password_temporal)

    conn = get_db_connection()
    if not conn:
        flash("Error de conexión con la base de datos.", "danger")
        return redirect(url_for('usuarios.lista_usuarios'))
    
    try:
        cursor = conn.cursor()

        consulta = """
            INSERT INTO Usuarios (nombre, apellidos, correo, contrasena, id_rol, estado)
            VALUES (?, ?, ?, ?, ?, ?)
        """

        cursor.execute(consulta, (nombre, apellidos, correo, password_hash, id_rol, estado))
        conn.commit()

        hilo_correo = threading.Thread(
            target=enviar_correo_bienvenida,
            args=(correo, nombre, password_temporal)
        )
        hilo_correo.start()

        flash("Usuario registrado correctamente. El correo se siendo enviado.", "success")

        correo_enviado = enviar_correo_bienvenida(correo, nombre, password_temporal)
     
    except Exception as e:
        conn.rollback()
        flash(f"Error al registrar: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('usuarios.lista_usuarios'))

# Editar permisos de usuarios registrados
@usuarios_bp.route('/usuarios/configurar/<int:id>', methods=['POST'])
def configurar_usuario(id):

    id_rol = request.form.get('id_rol')
    estado = request.form.get('estado')

    if estado is None:
        return f"<h3>¡El navegador sigue mandando los datos viejos!</h3> <p>Por favor, regresa a la página y presiona <b>Ctrl + F5</b>.</p>"
    
    if session.get('role') != 'ADMIN':

        if str(id_rol) in ['1', '2']:
            flash("Alerta de seguridad: No tienes permisos para asignar este rol.", "danger")
            return redirect(url_for('usuarios.lista_usuarios'))
        id_rol = '3'

    conn = get_db_connection()

    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for('usuarios.lista_usuarios'))
    
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

# EDITAR DATOS DE USUARIOS REGISTRADOS
@usuarios_bp.route('/usuarios/editar/<int:id>', methods=['POST'])
def editar_usuario(id):
    
    nombre = request.form.get('nombre')
    apellidos = request.form.get('apellidos')
    correo = request.form.get('correo')

    conn = get_db_connection()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return(url_for('usuarios.lista_usuarios'))
    
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