import string
import secrets
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database.conexion import get_db_connection
from werkzeug.security import check_password_hash, generate_password_hash
import threading
import os
from dotenv import load_dotenv

load_dotenv()

auth_bp = Blueprint('auth', __name__)

def enviar_correo_codigo(correo_destino, codigo, nombre_usuario):
    correo_emisor = os.getenv('GMAIL_USER')
    password_emisor = os.getenv('GMAIL_PASS')

    msg = EmailMessage()
    msg['Subject'] = 'Código de verificación - Restablecer Contraseña SIGEA'
    msg['From'] = correo_emisor
    msg['To'] = correo_destino

    contenido = f"""Hola {nombre_usuario},
    
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

    except Exception as e:
        print(f"Error al enviar el correo de restablecimiento: {e}")

# --- DECORADOR DE ROLES ---
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            rol_actual = session.get('role')
            if not rol_actual or rol_actual not in roles:
                session.clear() 
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
        if not conn:
            return render_template('olvide_contrasena.html', error="Error de conexión con la base de datos.")
            
        try:
            cursor = conn.cursor()

            cursor.execute("SELECT id_usuario, nombre FROM Usuarios WHERE correo = ? AND estado = 'Activo'", (correo,))
            usuario = cursor.fetchone()

            if not usuario:
                return render_template('olvide_contrasena.html', error = "El correo electrónico no se encuentra registrado o la cuenta esta inactiva.")
            
            alfabeto = string.ascii_uppercase + string.digits
            codigo = ''.join(secrets.choice(alfabeto) for i in range(6))

            session.permanent = False
            session['reset_correo'] = correo
            session['reset_nombre'] = usuario[1]
            session['reset_codigo'] = codigo
            session['reset_expiracion'] = (datetime.now() + timedelta(minutes=10))

            hilo_correo = threading.Thread(
                target=enviar_correo_codigo,
                args=(correo, codigo, usuario[1])
            )
            hilo_correo.start()

            return redirect(url_for('auth.restablecer_contrasena', success="Código enviado. Revisa tu bandeja de entrada."))
        
        except Exception as e:
            return render_template('olvide_contrasena.html', error=f"Error en el servidor: {e}")
        finally:
            conn.close()

    return render_template('olvide_contrasena.html', error=error)


# REENVIAR CODIGO
@auth_bp.route('/reenviar-codigo')
def reenviar_codigo():
    correo = session.get('reset_correo')
    nombre = session.get('reset_nombre', 'Usuario')

    if not correo:
        return redirect(url_for('auth.olvide_contrasena'))
    
    alfabeto = string.ascii_uppercase + string.digits
    nuevo_codigo = ''.join(secrets.choice(alfabeto) for i in range (6))

    session.permanent = False
    session['reset_codigo'] = nuevo_codigo
    session['reset_expiracion'] = (datetime.now() + timedelta(minutes=10))

    hilo_correo = threading.Thread(
        target=enviar_correo_codigo,
        args=(correo, nuevo_codigo, nombre)
    )
    hilo_correo.start()
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
            fecha_expiracion = datetime.fromisoformat(expiracion) if isinstance(expiracion, str) else expiracion
            fecha_expiracion_limpia = fecha_expiracion.replace(tzinfo=None)
            
            if datetime.now() > fecha_expiracion_limpia:
                session.clear()
                return redirect(url_for('auth.olvide_contrasena', error="El código de verificación ha expirado. Solicita uno nuevo."))
            
        if codigo_ingresado != session.get('reset_codigo'):
            return render_template('restablecer_contrasena.html', error="El código de verificación introducido es incorrecto.")
            
        if nueva_contrasena != confirmar_contrasena:
            return render_template('restablecer_contrasena.html', error="Las contraseñas no coinciden. Verifícalas.")
            
        password_hash = generate_password_hash(nueva_contrasena)
        correo_usuario = session.get('reset_correo')
            
        conn = get_db_connection()
        if not conn:
            return render_template('restablecer_contrasena.html', error="Error al actualizar los datos. Inténtalo de nuevo.")
            
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE Usuarios SET contrasena = ? WHERE correo = ?", (password_hash, correo_usuario))
            conn.commit()

            session.pop('reset_correo', None)
            session.pop('reset_codigo', None)
            session.pop('reset_expiracion', None)

            return redirect(url_for('auth.login', success="Contraseña restablecida con éxito. Ya puedes iniciar sesión."))
        except Exception as e:
            conn.rollback()
            return render_template('restablecer_contrasena.html', error=f"Error en base de datos: {e}")
        finally:
            cursor.close()
                            
    return render_template('restablecer_contrasena.html', error=error, success = success)


# RUTA DE LOGIN
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = request.args.get('error')
    success = request.args.get('success')

    if request.method == 'POST':
        correo = request.form['correo']
        contrasena_ingresada = request.form['contrasena']

        conn = get_db_connection()
        if not conn:
            return render_template('login.html', error="Error al conectar con la base de datos.")
        
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id_usuario, nombre, estado, id_rol, contrasena FROM Usuarios WHERE correo = ?", (correo,))
            usuario = cursor.fetchone()

            if not usuario or not (check_password_hash(usuario[4], contrasena_ingresada) or usuario[4] == contrasena_ingresada):
                 return render_template('login.html', error="Correo o contraseña incorrectos.")
                 
            estado_usuario = usuario[2]
            if estado_usuario == 'Inactivo':
                return render_template('login.html', error="Tu cuenta ha sido desactivada.") 
            
            session.permanent = True
            session['id_usuario'] = usuario[0]
            session['nombre_usuario'] = usuario[1]
                    
            id_rol = usuario[3]
            roles = {1: 'ADMIN', 2: 'COORDINADOR', 3: 'MAESTRO'}

            if id_rol not in roles:
                return render_template('login.html', error="Tu usuario no tiene un rol válido asignado.")
                 
            session['role'] = roles[id_rol]
            
            if session['role'] == 'MAESTRO':
                return redirect(url_for('asignaciones.vista_asignaciones'))
            
            return redirect(url_for('panel.inicio'))
            
        except Exception as e:
            return render_template('login.html', error=f"Error interno: {e}")
        finally:
            conn.close()
                    
    return render_template('login.html', error=error, success=success)
                    

# --- RUTA DE LOGOUT ---
@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))