import string
import secrets
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session
from database.conexion import get_db_connection
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint('auth', __name__)

def enviar_correo_codigo(correo_destino, codigo):
    correo_emisor = "cuentapruebasigea@gmail.com"
    password_emisor = "ndaz qtsz wxvv ejbq"

    msg = EmailMessage()
    msg['Subject'] = 'Código de verificación - Restablecer Contraseña SIGEA'
    msg['From'] = correo_emisor
    msg['To'] = correo_destino

    contenido = f"""Hola,
    
Has solicitado restablecer tu contraseña en el Sistema Integral de Gestión de Espacios Académicos (SIGEA).
    
Tu código de verificación es: {codigo}

Este código es válido durante los próximos 10 minutos. Si no solicitaste este cambio, puedes ignorar este correo de forma segura.
    
Saludos,
El equipo de SIGEA.
"""
    msg.set_content(contenido)

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(correo_emisor, password_emisor)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error al enviar el correo de restablecimiento: {e}")
        return False

# --- DECORADOR DE ROLES ---
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            rol_actual = session.get('role')
            # Si no hay rol o el rol no tiene permiso para esta ruta:
            if not rol_actual or rol_actual not in roles:
                session.clear() # Limpiamos cualquier dato atorado
                # Redirigimos al login enviando un mensaje de error por la URL para evitar bucles
                return redirect(url_for('auth.login', error="Acceso denegado o sesión expirada."))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# SOLICITAR RECUPERACIÓN
@auth_bp.route('/olvide-contrasena', methods=['GET', 'POST'])
def olvide_contrasena():
    error = request.args.get('error')
    if request.method == 'POST':
        correo = request.form.get('correo').strip()

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()

            cursor.execute("SELECT id_usuario FROM Usuarios WHERE correo = ? AND estado = 'Activo'", (correo,))
            usuario = cursor.fetchone()
            conn.close()

            if usuario:
                alfabeto = string.ascii_uppercase + string.digits
                codigo = ''.join(secrets.choice(alfabeto) for i in range(6))

                session.permanent = False
                session['reset_correo'] = correo
                session['reset_codigo'] = codigo
                session['reset_expiracion'] = (datetime.now() + timedelta(minutes=10))

                if enviar_correo_codigo(correo, codigo):
                    return redirect(url_for('auth.restablecer_contrasena'))
                else:
                    error = "Hubo un problema al enviar el correo. Intentalo más tarde."
            else: 
                error = "El correo electrónico no se encuentra registrado o la cuenta esta inactiva."
        else:
            error = "Error de conexión con la base de datos."
    return render_template('olvide_contrasena.html', error=error)

# REENVIAR CODIGO
@auth_bp.route('/reenviar-codigo')
def reenviar_codigo():
    correo = session.get('reset_correo')
    if not correo:
        return redirect(url_for('auth.olvide_contrasena'))
    
    alfabeto = string.ascii_uppercase + string.digits
    nuevo_codigo = ''.join(secrets.choice(alfabeto) for i in range (6))

    session.permanent = False
    session['reset_codigo'] = nuevo_codigo
    session['reset_expiracion'] = (datetime.now() + timedelta(minutes=10))

    if enviar_correo_codigo(correo, nuevo_codigo):
        return redirect(url_for('auth.restablecer_contrasena', success ="Se ha enviado un nuevo código a tu correo."))
    else:
        return redirect(url_for('auth.restablecer_contrasena', error="Error al intentar reenviar el correo."))



@auth_bp.route('/restablecer-contrasena', methods=['GET', 'POST'])
def restablecer_contrasena():

    if 'reset_correo' not in session or 'reset_codigo' not in session:
        return redirect(url_for('auth.olvide_contrasena'))
        
    error = request.args.get('error')
    success = request.args.get('success')

    if request.method == 'POST':
        codigo_ingresado = request.form.get('codigo').strip().upper()
        nueva_contrasena = request.form.get('nueva_contrasena')
        confirmar_contrasena = request.form.get('confirmar_contrasena')
        
        expiracion = session.get('reset_expiracion')
        if expiracion:

            if isinstance(expiracion, str):
                fecha_expiracion = datetime.fromisoformat(expiracion)
            else:
                fecha_expiracion = expiracion
                
            fecha_expiracion_limpia = fecha_expiracion.replace(tzinfo=None)
            if datetime.now() > fecha_expiracion_limpia:
                session.clear()
                return redirect(url_for('auth.olvide_contrasena', error="El código de verificación ha expirado. Solicita uno nuevo."))
            
        if codigo_ingresado != session.get('reset_codigo'):
            error = "El código de verificación introducido es incorrecto."
            
        elif nueva_contrasena != confirmar_contrasena:
            error = "Las contraseñas no coinciden. Verifícalas."
            
        else:
            password_hash = generate_password_hash(nueva_contrasena)
            correo_usuario = session.get('reset_correo')
            
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE Usuarios SET contrasena = ? WHERE correo = ?", (password_hash, correo_usuario))
                conn.commit()
                cursor.close()
                conn.close()
                
                session.pop('reset_correo', None)
                session.pop('reset_codigo', None)
                session.pop('reset_expiracion', None)
            
                return redirect(url_for('auth.login', success="Contraseña restablecida con éxito. Ya puedes iniciar sesión."))
            else:
                error = "Error al actualizar los datos. Inténtalo de nuevo."
                
    return render_template('restablecer_contrasena.html', error=error, success = success)
# --- RUTA DE LOGIN ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Capturamos el error si fuimos rebotados por el decorador
    error = request.args.get('error')
    success = request.args.get('success')

    if request.method == 'POST':
        correo = request.form['correo']
        contrasena_ingresada = request.form['contrasena']

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            # Solo pedimos el id_rol (1, 2 o 3) 
            cursor.execute("SELECT id_usuario, nombre, estado, id_rol, contrasena FROM Usuarios WHERE correo = ?", (correo,))
            usuario = cursor.fetchone()
            conn.close()

            if usuario and (check_password_hash(usuario[4], contrasena_ingresada) or usuario[4] == contrasena_ingresada): 
                estado_usuario = usuario[2]

                if estado_usuario == 'Inactivo':
                    return render_template('login.html', error="Tu cuenta ha sido desactivada.")
                else: 
                    session.permanent = True
                    session['id_usuario'] = usuario[0]
                    session['nombre_usuario'] = usuario[1]
                    
                    id_rol = usuario[3]
                    
                    if id_rol == 1:
                        session['role'] = 'ADMIN'
                    elif id_rol == 2:
                        session['role'] = 'COORDINADOR'
                    elif id_rol == 3:
                        session['role'] = 'MAESTRO'
                    else:
                        return render_template('login.html', error="Tu usuario no tiene un rol válido asignado.")
                    
                    if session['role'] == 'MAESTRO':
                        return redirect(url_for('asignaciones.vista_asignaciones'))
                    
                    return redirect(url_for('panel.inicio'))
            else:
                return render_template('login.html', error="Correo o contraseña incorrectos.")
        else:
            return render_template('login.html', error="Error al conectar con la base de datos.")
                    
    return render_template('login.html', error=error)

# --- RUTA DE LOGOUT ---
@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))