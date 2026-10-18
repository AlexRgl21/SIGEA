import logging

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

import config
from database.conexion import get_db
from services import usuarios as servicio
from services.errores import ErrorNegocio
from .decoradores import role_required

usuarios_bp = Blueprint('usuarios', __name__)
logger = logging.getLogger(__name__)

DESTINO = 'usuarios.lista_usuarios'


def _sin_conexion():
    flash("Error de conexión a la base de datos.", "danger")
    return redirect(url_for(DESTINO))


@usuarios_bp.route('/usuarios')
@role_required(*config.ROLES_ADMINISTRATIVOS)
def lista_usuarios():
    conn = get_db()
    if not conn:
        return render_template('usuarios.html', usuarios=[], error="Sin conexión a la base de datos")
    return render_template('usuarios.html', usuarios=servicio.listar(conn))


@usuarios_bp.route('/usuarios/agregar', methods=['POST'])
@role_required(*config.ROLES_ADMINISTRATIVOS)
def agregar_usuario():
    conn = get_db()
    if not conn:
        return _sin_conexion()
    try:
        servicio.crear(conn, session.get('role'),
                       request.form['nombre'], request.form['apellidos'],
                       request.form['correo'], request.form.get('id_rol'))
        flash("Usuario registrado correctamente. El correo se está enviando.", "success")
    except ErrorNegocio as e:
        flash(e.mensaje, "danger")
    except Exception:
        logger.exception("Error al registrar")
        flash("Error al registrar. Inténtalo de nuevo o avisa al administrador.", "danger")
    return redirect(url_for(DESTINO))


@usuarios_bp.route('/usuarios/configurar/<int:id>', methods=['POST'])
@role_required(*config.ROLES_ADMINISTRATIVOS)
def configurar_usuario(id):
    conn = get_db()
    if not conn:
        return _sin_conexion()
    try:
        servicio.configurar(conn, session.get('role'), id,
                            request.form.get('id_rol'), request.form.get('estado'))
        flash("Permisos y estado del usuario actualizados correctamente.", "success")
    except ErrorNegocio as e:
        flash(e.mensaje, "danger")
    except Exception:
        logger.exception("Error al configurar el usuario")
        flash("Error al configurar el usuario. Inténtalo de nuevo o avisa al administrador.", "danger")
    return redirect(url_for(DESTINO))


@usuarios_bp.route('/usuarios/editar/<int:id>', methods=['POST'])
@role_required(*config.ROLES_ADMINISTRATIVOS)
def editar_usuario(id):
    conn = get_db()
    if not conn:
        return _sin_conexion()
    try:
        servicio.editar(conn, session.get('role'), id,
                        request.form.get('nombre'), request.form.get('apellidos'),
                        request.form.get('correo'))
        flash("Datos del usuario modificados con éxito.", "success")
    except ErrorNegocio as e:
        flash(e.mensaje, "danger")
    except Exception:
        logger.exception("Error al editar el usuario")
        flash("Error al editar el usuario. Inténtalo de nuevo o avisa al administrador.", "danger")
    return redirect(url_for(DESTINO))