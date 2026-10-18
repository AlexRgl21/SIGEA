# Login, bloqueo por intentos fallidos y recuperación de contraseña

import hashlib
import hmac
import logging
import os
import secrets
import string
from datetime import datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

import config
from . import correo
from .errores import ErrorNegocio

logger = logging.getLogger(__name__)

MSG_ENVIO = ("Si el correo está registrado, te enviamos un código. "
             "Revisa tu bandeja; si no llega, espera un minuto antes de pedir otro.")
MSG_CODIGO_INVALIDO = ("El código es incorrecto, expiró o superaste el máximo de intentos. "
                       "Solicita uno nuevo si lo necesitas.")

# Hash de relleno: se compara cuando el correo no existe, para que el sistema
# tarde lo mismo en responder exista o no la cuenta.
_HASH_FALSO = generate_password_hash('relleno-que-no-es-una-contrasena')


def _ahora():
    return datetime.now()


# RECUPERACIÓN DE CONTRASEÑA
def generar_codigo():
    alfabeto = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alfabeto) for _ in range(config.CODIGO_LONGITUD))


def hash_codigo(id_usuario, codigo):
    clave = (os.getenv('SECRET_KEY') or '').encode()
    return hmac.new(clave, f"{id_usuario}:{codigo}".encode(), hashlib.sha256).hexdigest()


def _emitir_codigo(cursor, conn, id_usuario, correo_destino, nombre):
    ahora = _ahora()

    cursor.execute("SELECT TOP 1 creado_en FROM CodigosRecuperacion "
                   "WHERE id_usuario = ? ORDER BY creado_en DESC", (id_usuario,))
    ultimo = cursor.fetchone()
    if ultimo and (ahora - ultimo[0]).total_seconds() < config.ESPERA_REENVIO_SEG:
        return False

    cursor.execute("SELECT COUNT(*) FROM CodigosRecuperacion WHERE id_usuario = ? AND creado_en > ?",
                   (id_usuario, ahora - timedelta(hours=1)))
    if cursor.fetchone()[0] >= config.MAX_ENVIOS_POR_HORA:
        return False

    # Solo un código vigente a la vez: los anteriores quedan invalidados
    cursor.execute("UPDATE CodigosRecuperacion SET usado = 1 WHERE id_usuario = ? AND usado = 0",
                   (id_usuario,))
    codigo = generar_codigo()
    cursor.execute(
        "INSERT INTO CodigosRecuperacion (id_usuario, codigo_hash, creado_en, expira_en) "
        "VALUES (?, ?, ?, ?)",
        (id_usuario, hash_codigo(id_usuario, codigo), ahora,
         ahora + timedelta(minutes=config.CODIGO_VIGENCIA_MIN)))
    conn.commit()

    correo.correo_codigo_recuperacion(correo_destino, codigo, nombre)
    return True


def solicitar_codigo(conn, correo_usuario):
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id_usuario, nombre FROM Usuarios WHERE correo = ? AND estado = 'Activo'",
                       (correo_usuario,))
        usuario = cursor.fetchone()
        if usuario:
            _emitir_codigo(cursor, conn, usuario[0], correo_usuario, usuario[1])
    except Exception:
        conn.rollback()
        raise


def verificar_codigo(conn, correo_usuario, codigo):
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id_usuario FROM Usuarios WHERE correo = ? AND estado = 'Activo'",
                       (correo_usuario,))
        usuario = cursor.fetchone()
        if not usuario:
            return None
        id_usuario = usuario[0]

        cursor.execute("SELECT TOP 1 id_codigo, codigo_hash, expira_en FROM CodigosRecuperacion "
                       "WHERE id_usuario = ? AND usado = 0 ORDER BY creado_en DESC", (id_usuario,))
        fila = cursor.fetchone()
        if not fila or fila[2] < _ahora():
            return None
        id_codigo, codigo_hash = fila[0], fila[1]

        cursor.execute("UPDATE CodigosRecuperacion SET intentos = intentos + 1 "
                       "WHERE id_codigo = ? AND usado = 0 AND intentos < ?",
                       (id_codigo, config.MAX_INTENTOS))
        intento_gastado = cursor.rowcount
        conn.commit()
        if intento_gastado == 0:
            return None

        if not hmac.compare_digest(codigo_hash, hash_codigo(id_usuario, codigo)):
            # Si era el último intento, el código queda inutilizable
            cursor.execute("UPDATE CodigosRecuperacion SET usado = 1 "
                           "WHERE id_codigo = ? AND intentos >= ?", (id_codigo, config.MAX_INTENTOS))
            conn.commit()
            return None

        cursor.execute("UPDATE CodigosRecuperacion SET expira_en = ? WHERE id_codigo = ?",
                       (_ahora() + timedelta(minutes=config.CAMBIO_VIGENCIA_MIN), id_codigo))
        conn.commit()
        return id_codigo
    except Exception:
        conn.rollback()
        raise


def usuario_verificado(conn, correo_usuario, id_codigo):

    if not id_codigo:
        return None
    cursor = conn.cursor()
    cursor.execute(
        "SELECT c.id_usuario FROM CodigosRecuperacion c "
        "JOIN Usuarios u ON u.id_usuario = c.id_usuario "
        "WHERE c.id_codigo = ? AND c.usado = 0 AND c.expira_en > ? "
        "AND u.correo = ? AND u.estado = 'Activo'",
        (id_codigo, _ahora(), correo_usuario))
    fila = cursor.fetchone()
    return fila[0] if fila else None


def cambiar_contrasena(conn, id_usuario, nueva, confirmar):
    if nueva != confirmar:
        raise ErrorNegocio("Las contraseñas no coinciden. Verifícalas.")
    if len(nueva) < config.LONGITUD_MINIMA_PASSWORD:
        raise ErrorNegocio(f"La contraseña debe tener al menos {config.LONGITUD_MINIMA_PASSWORD} caracteres.")
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Usuarios SET contrasena = ? WHERE id_usuario = ?",
                       (generate_password_hash(nueva), id_usuario))
        cursor.execute("UPDATE CodigosRecuperacion SET usado = 1 WHERE id_usuario = ?", (id_usuario,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# LOGIN CON LÍMITE DE INTENTOS
def minutos_de_bloqueo(cursor, correo_usuario, ip, ahora=None):

    ahora = ahora or _ahora()
    desde = ahora - timedelta(minutes=config.LOGIN_VENTANA_MIN)
    espera = 0
    consultas = (
        ("SELECT creado_en FROM LoginFallidos WHERE correo = ? AND creado_en > ? "
         "ORDER BY creado_en DESC", correo_usuario, config.LOGIN_MAX_INTENTOS),
        ("SELECT creado_en FROM LoginFallidos WHERE ip = ? AND creado_en > ? "
         "ORDER BY creado_en DESC", ip, config.LOGIN_MAX_INTENTOS_IP),
    )
    for sql, valor, tope in consultas:
        cursor.execute(sql, (valor, desde))
        fechas = [f[0] for f in cursor.fetchall()]       # de la más reciente a la más antigua
        if len(fechas) >= tope:
            libre_en = fechas[0] + timedelta(minutes=config.LOGIN_VENTANA_MIN)
            segundos = (libre_en - ahora).total_seconds()
            espera = max(espera, max(1, int((segundos + 59) // 60)))
    return espera


def _registrar_fallo(cursor, conn, correo_usuario, ip):
    ahora = _ahora()
    cursor.execute("INSERT INTO LoginFallidos (correo, ip, creado_en) VALUES (?, ?, ?)",
                   (correo_usuario, ip, ahora))
    cursor.execute("DELETE FROM LoginFallidos WHERE creado_en < ?", (ahora - timedelta(days=1),))
    conn.commit()


def _limpiar_fallos(cursor, conn, correo_usuario):
    cursor.execute("DELETE FROM LoginFallidos WHERE correo = ?", (correo_usuario,))
    conn.commit()


def autenticar(conn, correo_usuario, contrasena, ip):
    cursor = conn.cursor()
    try:
        # 1. Los intentos hechos durante el bloqueo no se cuentan
        espera = minutos_de_bloqueo(cursor, correo_usuario, ip)
        if espera:
            raise ErrorNegocio(f"Demasiados intentos fallidos. Inténtalo de nuevo en {espera} minuto(s).",
                               status=429)

        # 2. Validar credenciales
        cursor.execute("SELECT id_usuario, nombre, estado, id_rol, contrasena "
                       "FROM Usuarios WHERE correo = ?", (correo_usuario,))
        usuario = cursor.fetchone()
        if usuario:
            correcta = check_password_hash(usuario[4], contrasena)
        else:
            check_password_hash(_HASH_FALSO, contrasena)
            correcta = False

        if not correcta:
            _registrar_fallo(cursor, conn, correo_usuario, ip)
            raise ErrorNegocio("Correo o contraseña incorrectos.")

        # 3. Contraseña correcta: se reinicia el conteo de fallos de ese correo
        _limpiar_fallos(cursor, conn, correo_usuario)

        if usuario[2] == 'Inactivo':
            raise ErrorNegocio("Tu cuenta ha sido desactivada.")
        rol = config.ROLES_POR_ID.get(usuario[3])
        if rol is None:
            raise ErrorNegocio("Tu usuario no tiene un rol válido asignado.")
        return {'id_usuario': usuario[0], 'nombre': usuario[1], 'role': rol}
    except ErrorNegocio:
        raise
    except Exception:
        conn.rollback()
        raise