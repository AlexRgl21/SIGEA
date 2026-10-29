import logging

from flask import Blueprint, render_template, request, redirect, url_for, session

import config
from database.conexion import get_db
from services import autenticacion
from services.errores import ErrorNegocio

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

ERROR_CONEXION = "Error de conexión. Inténtalo de nuevo."


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

        session['reset_correo'] = correo
        session.pop('reset_verificado', None)
        return redirect(url_for('auth.restablecer_contrasena', success=autenticacion.MSG_ENVIO))

    return render_template('olvide_contrasena.html', error=error)


def _solicitar_codigo(correo):
    conn = get_db()
    if not conn:
        return False
    try:
        autenticacion.solicitar_codigo(conn, correo)
        return True
    except Exception:
        logger.exception("Error al generar el código de recuperación")
        return False


@auth_bp.route('/reenviar-codigo', methods=['POST'])
def reenviar_codigo():
    correo = session.get('reset_correo')
    if not correo:
        return redirect(url_for('auth.olvide_contrasena'))

    session.pop('reset_verificado', None)
    if not _solicitar_codigo(correo):
        return redirect(url_for('auth.restablecer_contrasena',
                                error="No pudimos reenviar el código. Inténtalo de nuevo."))
    return redirect(url_for('auth.restablecer_contrasena', success=autenticacion.MSG_ENVIO))


@auth_bp.route('/verificar-codigo', methods=['POST'])
def verificar_codigo():
    correo = session.get('reset_correo')
    if not correo:
        return redirect(url_for('auth.olvide_contrasena'))

    codigo = (request.form.get('codigo') or '').strip().upper()
    if len(codigo) != config.CODIGO_LONGITUD:
        return render_template('restablecer_contrasena.html', paso=1,
                               error=f"Escribe los {config.CODIGO_LONGITUD} caracteres del código.")

    conn = get_db()
    if not conn:
        return render_template('restablecer_contrasena.html', paso=1, error=ERROR_CONEXION)
    try:
        id_codigo = autenticacion.verificar_codigo(conn, correo, codigo)
    except Exception:
        logger.exception("Error al verificar el código de recuperación")
        return render_template('restablecer_contrasena.html', paso=1,
                               error="No pudimos verificar el código. Inténtalo de nuevo.")

    if id_codigo is None:
        return render_template('restablecer_contrasena.html', paso=1,
                               error=autenticacion.MSG_CODIGO_INVALIDO)

    session['reset_verificado'] = id_codigo
    return redirect(url_for('auth.restablecer_contrasena',
                            success="Código verificado. Ahora elige tu nueva contraseña."))


@auth_bp.route('/restablecer-contrasena', methods=['GET', 'POST'])
def restablecer_contrasena():
    correo = session.get('reset_correo')
    if not correo:
        return redirect(url_for('auth.olvide_contrasena'))

    conn = get_db()
    if not conn:
        return render_template('restablecer_contrasena.html', paso=1, error=ERROR_CONEXION)
    try:
        id_usuario = autenticacion.usuario_verificado(conn, correo, session.get('reset_verificado'))

        if request.method == 'POST':
            if id_usuario is None:
                session.pop('reset_verificado', None)
                return redirect(url_for('auth.restablecer_contrasena',
                                        error="Primero verifica el código que te enviamos."))
            try:
                autenticacion.cambiar_contrasena(
                    conn, id_usuario,
                    request.form.get('nueva_contrasena') or '',
                    request.form.get('confirmar_contrasena') or '')
            except ErrorNegocio as e:
                return render_template('restablecer_contrasena.html', paso=2, error=e.mensaje)

            session.pop('reset_correo', None)
            session.pop('reset_verificado', None)
            return redirect(url_for('auth.login',
                                    success="Contraseña restablecida con éxito. Ya puedes iniciar sesión."))

        if id_usuario is None:
            session.pop('reset_verificado', None)
        return render_template('restablecer_contrasena.html',
                               paso=2 if id_usuario else 1,
                               error=request.args.get('error'),
                               success=request.args.get('success'))
    except Exception:
        logger.exception("Error en el restablecimiento de contraseña")
        return render_template('restablecer_contrasena.html', paso=1,
                               error="No pudimos completar la operación. Inténtalo de nuevo.")


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = request.args.get('error')
    success = request.args.get('success')

    if request.method == 'POST':
        correo = (request.form.get('correo') or '').strip().lower()[:100]
        contrasena = request.form.get('contrasena') or ''
        ip = request.remote_addr or 'desconocida'

        conn = get_db()
        if not conn:
            return render_template('login.html', error="Error al conectar con la base de datos.")

        try:
            usuario = autenticacion.autenticar(conn, correo, contrasena, ip)
        except ErrorNegocio as e:
            return render_template('login.html', error=e.mensaje), (e.status or 200)
        except Exception:
            logger.exception("Error en el inicio de sesión")
            return render_template('login.html',
                                   error="No pudimos iniciar tu sesión. Inténtalo de nuevo.")

        session.clear()
        session.permanent = True
        session['id_usuario'] = usuario['id_usuario']
        session['nombre_usuario'] = usuario['nombre']
        session['role'] = usuario['role']

        if usuario['role'] == config.ROL_MAESTRO:
            return redirect(url_for('asignaciones.vista_asignaciones'))
        elif usuario['role'] == config.ROL_ALMACEN:
            return redirect(url_for('reservas.vista_reserva'))
        return redirect(url_for('panel.inicio'))

    return render_template('login.html', error=error, success=success)


@auth_bp.route('/logout', methods=['POST'])
def logout():
    motivo = request.form.get('motivo')
    session.clear()
    if motivo == 'inactividad':
        return redirect(url_for('auth.login', error="Tu sesión se cerró por inactividad."))
    return redirect(url_for('auth.login'))


@auth_bp.route('/sesion/extender', methods=['POST'])
def extender_sesion():
    if 'id_usuario' not in session:
        return ('', 401)
    session.modified = True
    return ('', 204)