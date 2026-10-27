import logging
import math

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
    
    # Leer la página y los filtros actuales de la URL
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
    q = (request.args.get('q') or '').strip()
    rol = (request.args.get('rol') or '').strip()
    estado = (request.args.get('estado') or '').strip()

    if not conn:
        return render_template('usuarios.html', usuarios=[], error="Sin conexión a la base de datos",
                               page=1, total_pages=1, q=q, rol=rol, estado=estado)

    # Si no hay filtros activos, delegamos directamente al servicio original
    if not q and not rol and not estado:
        datos = servicio.listar(conn, page=page)
        datos.update(q='', rol='', estado='')
        return render_template('usuarios.html', **datos)

    # Si hay filtros activos, consultamos todos los usuarios y filtramos antes de paginar
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id_usuario, nombre, apellidos, correo, id_rol, estado
        FROM Usuarios
        ORDER BY id_usuario DESC
    """)
    todos = []
    for f in cursor.fetchall():
        rol_nombre = config.NOMBRES_ROL.get(f[4], 'Docente')
        nombre_completo = f"{f[1]} {f[2]}".strip()
        todos.append({
            'id_usuario': f[0],
            'nombre': f[1],
            'apellidos': f[2],
            'nombre_completo': nombre_completo,
            'correo': f[3],
            'id_rol': f[4],
            'rol_nombre': rol_nombre,
            'estado': f[5],
        })

    q_low = q.lower()
    rol_low = rol.lower()
    estado_low = estado.lower()

    filtrados = [
        u for u in todos
        if (not q_low or q_low in u['nombre_completo'].lower() or q_low in u['correo'].lower())
        and (not rol_low or u['rol_nombre'].lower() == rol_low)
        and (not estado_low or str(u['estado']).lower() == estado_low)
    ]

    per_page = 10
    total_pages = math.ceil(len(filtrados) / per_page) if filtrados else 1
    if page > total_pages:
        page = total_pages
    offset = (page - 1) * per_page

    return render_template('usuarios.html',
                           usuarios=filtrados[offset:offset + per_page],
                           page=page, total_pages=total_pages,
                           q=q, rol=rol, estado=estado)


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