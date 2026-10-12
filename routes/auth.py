import string
import secrets
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from database.conexion import get_db_connection
from werkzeug.security import check_password_hash, generate_password_hash
import threading
import os
from dotenv import load_dotenv
import hmac 
import hashlib

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
        decorated_function.roles = roles
        return decorated_function
    return decorator


# ---------------------------------------------------------------
# RECUPERACIÓN DE CONTRASEÑA (código con hash, expiración e intentos en la BD)
# ---------------------------------------------------------------
CODIGO_LONGITUD = 6
CODIGO_VIGENCIA_MIN = 10      # minutos de vida del código
MAX_INTENTOS = 5              # intentos fallidos permitidos por código
ESPERA_REENVIO_SEG = 60       # segundos mínimos entre un código y el siguiente
MAX_ENVIOS_POR_HORA = 5       # códigos por usuario en una hora
CAMBIO_VIGENCIA_MIN = 10      # minutos para elegir la contraseña una vez verificado el código
LONGITUD_MINIMA_PASSWORD = 8

MSG_ENVIO = ("Si el correo está registrado, te enviamos un código. "
             "Revisa tu bandeja; si no llega, espera un minuto antes de pedir otro.")
MSG_CODIGO_INVALIDO = ("El código es incorrecto, expiró o superaste el máximo de intentos. "
                       "Solicita uno nuevo si lo necesitas.")


def _ahora():
    return datetime.now()


def _generar_codigo():
    alfabeto = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alfabeto) for _ in range(CODIGO_LONGITUD))


def _hash_codigo(id_usuario, codigo):
    """HMAC-SHA256 con la SECRET_KEY: si alguien lee la tabla no puede sacar el código."""
    clave = (os.getenv('SECRET_KEY') or '').encode()
    return hmac.new(clave, f"{id_usuario}:{codigo}".encode(), hashlib.sha256).hexdigest()


def _emitir_codigo(cursor, conn, id_usuario, correo, nombre):
    """Crea y envía un código nuevo. Respeta la espera entre envíos y el tope por hora.
    Si no puede enviar, no lo dice al usuario (para no revelar si la cuenta existe)."""
    ahora = _ahora()

    cursor.execute("SELECT creado_en FROM CodigosRecuperacion "
                   "WHERE id_usuario = ? ORDER BY creado_en DESC", (id_usuario,))
    ultimo = cursor.fetchone()
    if ultimo and (ahora - ultimo[0]).total_seconds() < ESPERA_REENVIO_SEG:
        return False

    cursor.execute("SELECT COUNT(*) FROM CodigosRecuperacion "
                   "WHERE id_usuario = ? AND creado_en > ?",
                   (id_usuario, ahora - timedelta(hours=1)))
    if cursor.fetchone()[0] >= MAX_ENVIOS_POR_HORA:
        return False

    # Solo un código vigente a la vez: los anteriores quedan invalidados
    cursor.execute("UPDATE CodigosRecuperacion SET usado = 1 "
                   "WHERE id_usuario = ? AND usado = 0", (id_usuario,))

    codigo = _generar_codigo()
    cursor.execute(
        "INSERT INTO CodigosRecuperacion (id_usuario, codigo_hash, creado_en, expira_en) "
        "VALUES (?, ?, ?, ?)",
        (id_usuario, _hash_codigo(id_usuario, codigo), ahora,
         ahora + timedelta(minutes=CODIGO_VIGENCIA_MIN)))
    conn.commit()

    threading.Thread(target=enviar_correo_codigo, args=(correo, codigo, nombre)).start()
    return True


def _solicitar_codigo(correo):
    """Busca la cuenta y, si existe y está activa, envía el código.
    Devuelve False solo ante un fallo técnico (no por cuenta inexistente)."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id_usuario, nombre FROM Usuarios "
                       "WHERE correo = ? AND estado = 'Activo'", (correo,))
        usuario = cursor.fetchone()
        if usuario:
            _emitir_codigo(cursor, conn, usuario[0], correo, usuario[1])
        return True
    except Exception:
        conn.rollback()
        current_app.logger.exception("Error al generar el código de recuperación")
        return False
    finally:
        conn.close()


def _verificar_codigo(cursor, conn, correo, codigo):
    """Devuelve (id_usuario, id_codigo) si el código es válido, o None.
    Cada comprobación gasta un intento de forma atómica, así que no se puede
    adivinar el código mandando peticiones en paralelo."""
    cursor.execute("SELECT id_usuario FROM Usuarios "
                   "WHERE correo = ? AND estado = 'Activo'", (correo,))
    usuario = cursor.fetchone()
    if not usuario:
        return None
    id_usuario = usuario[0]

    cursor.execute("SELECT id_codigo, codigo_hash, expira_en FROM CodigosRecuperacion "
                   "WHERE id_usuario = ? AND usado = 0 ORDER BY creado_en DESC",
                   (id_usuario,))
    fila = cursor.fetchone()
    if not fila or fila[2] < _ahora():
        return None
    id_codigo, codigo_hash = fila[0], fila[1]

    cursor.execute("UPDATE CodigosRecuperacion SET intentos = intentos + 1 "
                   "WHERE id_codigo = ? AND usado = 0 AND intentos < ?",
                   (id_codigo, MAX_INTENTOS))
    intento_gastado = cursor.rowcount
    conn.commit()
    if intento_gastado == 0:
        return None

    if not hmac.compare_digest(codigo_hash, _hash_codigo(id_usuario, codigo)):
        # Si era el último intento, el código queda inutilizable
        cursor.execute("UPDATE CodigosRecuperacion SET usado = 1 "
                       "WHERE id_codigo = ? AND intentos >= ?", (id_codigo, MAX_INTENTOS))
        conn.commit()
        return None

    return id_usuario, id_codigo


def _verificacion_vigente(cursor, correo):
    """Devuelve el id_usuario si ESTA sesión ya verificó un código que sigue vigente.
    La marca viaja en la cookie firmada de la sesión, así que otro navegador que escriba
    el mismo correo no puede saltarse la verificación."""
    id_codigo = session.get('reset_verificado')
    if not id_codigo:
        return None
    cursor.execute(
        "SELECT c.id_usuario FROM CodigosRecuperacion c "
        "JOIN Usuarios u ON u.id_usuario = c.id_usuario "
        "WHERE c.id_codigo = ? AND c.usado = 0 AND c.expira_en > ? "
        "AND u.correo = ? AND u.estado = 'Activo'",
        (id_codigo, _ahora(), correo))
    fila = cursor.fetchone()
    return fila[0] if fila else None


@auth_bp.route('/olvide-contrasena', methods=['GET', 'POST'])
def olvide_contrasena():
    error = request.args.get('error')

    if request.method == 'POST':
        correo = (request.form.get('correo') or '').strip().lower()
        if not correo:
            return render_template('olvide_contrasena.html', error="Escribe tu correo electrónico.")

        if not _solicitar_codigo(correo):
            return render_template('olvide_contrasena.html',
                                   error="No pudimos procesar tu solicitud. Inténtalo de nuevo.")

        # En la sesión solo queda el correo escrito; el código nunca sale de la BD
        session['reset_correo'] = correo
        session.pop('reset_verificado', None)
        return redirect(url_for('auth.restablecer_contrasena', success=MSG_ENVIO))

    return render_template('olvide_contrasena.html', error=error)


# REENVIAR CÓDIGO
@auth_bp.route('/reenviar-codigo', methods=['POST'])
def reenviar_codigo():
    correo = session.get('reset_correo')
    if not correo:
        return redirect(url_for('auth.olvide_contrasena'))

    session.pop('reset_verificado', None)   # un código nuevo invalida la verificación anterior
    if not _solicitar_codigo(correo):
        return redirect(url_for('auth.restablecer_contrasena',
                                error="No pudimos reenviar el código. Inténtalo de nuevo."))
    return redirect(url_for('auth.restablecer_contrasena', success=MSG_ENVIO))


# PASO 1: VERIFICAR EL CÓDIGO
@auth_bp.route('/verificar-codigo', methods=['POST'])
def verificar_codigo():
    correo = session.get('reset_correo')
    if not correo:
        return redirect(url_for('auth.olvide_contrasena'))

    codigo_ingresado = (request.form.get('codigo') or '').strip().upper()
    if len(codigo_ingresado) != CODIGO_LONGITUD:
        # Un código incompleto no gasta intentos
        return render_template('restablecer_contrasena.html', paso=1,
                               error=f"Escribe los {CODIGO_LONGITUD} caracteres del código.")

    conn = get_db_connection()
    if not conn:
        return render_template('restablecer_contrasena.html', paso=1,
                               error="Error de conexión. Inténtalo de nuevo.")
    try:
        cursor = conn.cursor()
        resultado = _verificar_codigo(cursor, conn, correo, codigo_ingresado)
        if resultado is None:
            return render_template('restablecer_contrasena.html', paso=1, error=MSG_CODIGO_INVALIDO)

        _, id_codigo = resultado
        # Ventana nueva para elegir la contraseña
        cursor.execute("UPDATE CodigosRecuperacion SET expira_en = ? WHERE id_codigo = ?",
                       (_ahora() + timedelta(minutes=CAMBIO_VIGENCIA_MIN), id_codigo))
        conn.commit()

        session['reset_verificado'] = id_codigo
        return redirect(url_for('auth.restablecer_contrasena',
                                success="Código verificado. Ahora elige tu nueva contraseña."))
    except Exception:
        conn.rollback()
        current_app.logger.exception("Error al verificar el código de recuperación")
        return render_template('restablecer_contrasena.html', paso=1,
                               error="No pudimos verificar el código. Inténtalo de nuevo.")
    finally:
        conn.close()


# PASO 2: ELEGIR LA NUEVA CONTRASEÑA (solo si el código ya fue verificado)
@auth_bp.route('/restablecer-contrasena', methods=['GET', 'POST'])
def restablecer_contrasena():
    correo = session.get('reset_correo')
    if not correo:
        return redirect(url_for('auth.olvide_contrasena'))

    conn = get_db_connection()
    if not conn:
        return render_template('restablecer_contrasena.html', paso=1,
                               error="Error de conexión. Inténtalo de nuevo.")
    try:
        cursor = conn.cursor()
        id_usuario = _verificacion_vigente(cursor, correo)

        if request.method == 'POST':
            if id_usuario is None:
                session.pop('reset_verificado', None)
                return redirect(url_for('auth.restablecer_contrasena',
                                        error="Primero verifica el código que te enviamos."))

            nueva_contrasena = request.form.get('nueva_contrasena') or ''
            confirmar_contrasena = request.form.get('confirmar_contrasena') or ''

            if nueva_contrasena != confirmar_contrasena:
                return render_template('restablecer_contrasena.html', paso=2,
                                       error="Las contraseñas no coinciden. Verifícalas.")
            if len(nueva_contrasena) < LONGITUD_MINIMA_PASSWORD:
                return render_template('restablecer_contrasena.html', paso=2,
                                       error=f"La contraseña debe tener al menos {LONGITUD_MINIMA_PASSWORD} caracteres.")

            cursor.execute("UPDATE Usuarios SET contrasena = ? WHERE id_usuario = ?",
                           (generate_password_hash(nueva_contrasena), id_usuario))
            cursor.execute("UPDATE CodigosRecuperacion SET usado = 1 WHERE id_usuario = ?",
                           (id_usuario,))
            conn.commit()

            session.pop('reset_correo', None)
            session.pop('reset_verificado', None)
            return redirect(url_for('auth.login',
                                    success="Contraseña restablecida con éxito. Ya puedes iniciar sesión."))

        # GET: muestra el paso que corresponde
        if id_usuario is None:
            session.pop('reset_verificado', None)
        return render_template('restablecer_contrasena.html',
                               paso=2 if id_usuario else 1,
                               error=request.args.get('error'),
                               success=request.args.get('success'))
    except Exception:
        conn.rollback()
        current_app.logger.exception("Error en el restablecimiento de contraseña")
        return render_template('restablecer_contrasena.html', paso=1,
                               error="No pudimos completar la operación. Inténtalo de nuevo.")
    finally:
        conn.close()

# LOGIN (con límite de intentos fallidos) Y LOGOUT
LOGIN_MAX_INTENTOS = 5        # fallos por correo dentro de la ventana
LOGIN_MAX_INTENTOS_IP = 20    # fallos por IP dentro de la ventana
LOGIN_VENTANA_MIN = 15        # ventana de conteo y duración del bloqueo

# Hash de relleno: se compara cuando el correo no existe, para que el sistema
# tarde lo mismo en responder exista o no la cuenta.
_HASH_FALSO = generate_password_hash('relleno-que-no-es-una-contrasena')


def _minutos_de_bloqueo(cursor, correo, ip):
    """Devuelve los minutos de bloqueo que faltan (mínimo 1) si el correo o la IP
    superaron su límite, o 0 si puede intentar. El bloqueo dura LOGIN_VENTANA_MIN
    minutos contados desde el último fallo."""
    ahora = _ahora()
    desde = ahora - timedelta(minutes=LOGIN_VENTANA_MIN)
    espera = 0

    consultas = (
        ("SELECT creado_en FROM LoginFallidos WHERE correo = ? AND creado_en > ? "
         "ORDER BY creado_en DESC", correo, LOGIN_MAX_INTENTOS),
        ("SELECT creado_en FROM LoginFallidos WHERE ip = ? AND creado_en > ? "
         "ORDER BY creado_en DESC", ip, LOGIN_MAX_INTENTOS_IP),
    )
    for sql, valor, tope in consultas:
        cursor.execute(sql, (valor, desde))
        fechas = [fila[0] for fila in cursor.fetchall()]     # de la más reciente a la más antigua
        if len(fechas) >= tope:
            libre_en = fechas[0] + timedelta(minutes=LOGIN_VENTANA_MIN)
            segundos = (libre_en - ahora).total_seconds()
            espera = max(espera, max(1, int((segundos + 59) // 60)))
    return espera


def _registrar_fallo(cursor, conn, correo, ip):
    ahora = _ahora()
    cursor.execute("INSERT INTO LoginFallidos (correo, ip, creado_en) VALUES (?, ?, ?)",
                   (correo, ip, ahora))
    # Limpieza: los fallos de más de un día ya no sirven
    cursor.execute("DELETE FROM LoginFallidos WHERE creado_en < ?", (ahora - timedelta(days=1),))
    conn.commit()


def _limpiar_fallos(cursor, conn, correo):
    cursor.execute("DELETE FROM LoginFallidos WHERE correo = ?", (correo,))
    conn.commit()


# RUTA DE LOGIN
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = request.args.get('error')
    success = request.args.get('success')

    if request.method == 'POST':
        correo = (request.form.get('correo') or '').strip().lower()[:100]
        contrasena_ingresada = request.form.get('contrasena') or ''
        ip = request.remote_addr or 'desconocida'

        conn = get_db_connection()
        if not conn:
            return render_template('login.html', error="Error al conectar con la base de datos.")

        try:
            cursor = conn.cursor()

            # 1. Los intentos hechos durante el bloqueo no se cuentan
            espera = _minutos_de_bloqueo(cursor, correo, ip)
            if espera:
                return render_template(
                    'login.html',
                    error=f"Demasiados intentos fallidos. Inténtalo de nuevo en {espera} minuto(s)."), 429

            # 2. Validar credenciales
            cursor.execute("SELECT id_usuario, nombre, estado, id_rol, contrasena "
                           "FROM Usuarios WHERE correo = ?", (correo,))
            usuario = cursor.fetchone()

            if usuario:
                contrasena_correcta = check_password_hash(usuario[4], contrasena_ingresada)
            else:
                check_password_hash(_HASH_FALSO, contrasena_ingresada)
                contrasena_correcta = False

            if not contrasena_correcta:
                _registrar_fallo(cursor, conn, correo, ip)
                return render_template('login.html', error="Correo o contraseña incorrectos.")

            # 3. Contraseña correcta: se reinicia el conteo de fallos de ese correo
            _limpiar_fallos(cursor, conn, correo)

            if usuario[2] == 'Inactivo':
                return render_template('login.html', error="Tu cuenta ha sido desactivada.")

            id_rol = usuario[3]
            roles = {1: 'ADMIN', 2: 'COORDINADOR', 3: 'MAESTRO'}
            if id_rol not in roles:
                return render_template('login.html', error="Tu usuario no tiene un rol válido asignado.")

            session.permanent = True
            session['id_usuario'] = usuario[0]
            session['nombre_usuario'] = usuario[1]
            session['role'] = roles[id_rol]

            if session['role'] == 'MAESTRO':
                return redirect(url_for('asignaciones.vista_asignaciones'))

            return redirect(url_for('panel.inicio'))

        except Exception:
            conn.rollback()
            current_app.logger.exception("Error en el inicio de sesión")
            return render_template('login.html',
                                error="No pudimos iniciar tu sesión. Inténtalo de nuevo.")
        finally:
            conn.close()

    return render_template('login.html', error=error, success=success)


# --- RUTA DE LOGOUT (solo POST, protegida con CSRF) ---
@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('auth.login'))