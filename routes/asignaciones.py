import logging

from flask import Blueprint, render_template, request, redirect, url_for, flash

import config
from database.conexion import get_db
from services import asignaciones as servicio
from services import periodos as servicio_periodos
from services.errores import ErrorNegocio
from .decoradores import role_required

asignaciones_bp = Blueprint('asignaciones', __name__)
logger = logging.getLogger(__name__)

DESTINO = 'asignaciones.vista_asignaciones'


def _volver():
    return redirect(url_for(DESTINO))


@asignaciones_bp.route('/asignaciones')
@role_required(*config.TODOS_LOS_ROLES)           # todos pueden ver el calendario
def vista_asignaciones():
    conn = get_db()
    
    # 1. Paginación: Leer la página actual de la URL
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
        
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return render_template('asignaciones.html', carreras=[], grupos=[], espacios=[],
                               periodos=[], edificios=[], eventos_calendario=[], page=1, total_pages=1)
    
    servicio_periodos.cerrar_vencidos_seguro(conn)                           
    # Le pasamos la página al servicio de datos_vista
    datos = servicio.datos_vista(conn, page)
    return render_template('asignaciones.html', **datos)


@asignaciones_bp.route('/asignaciones/nueva_asignacion', methods=['POST'])
@role_required(*config.ROLES_ADMINISTRATIVOS)
def nueva_asignacion():
    conn = get_db()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return _volver()
    try:
        servicio.crear_asignacion(
            conn,
            request.form.get('id_grupo'), request.form.get('id_espacio'),
            request.form.get('id_periodo'),
            request.form.get('hora_inicio'), request.form.get('hora_fin'),
            request.form.getlist('dias'))
        flash("Horario asignado con éxito. No se detectaron empalmes.", "success")
    except ErrorNegocio as e:
        flash(e.mensaje, "danger")
    except Exception:
        logger.exception("Error crítico en asignación")
        flash("Ocurrió un error interno al intentar guardar el horario.", "danger")
    return _volver()


@asignaciones_bp.route('/asignaciones/agregar_grupo', methods=['POST'])
@role_required(*config.ROLES_ADMINISTRATIVOS)
def agregar_grupo():
    conn = get_db()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return _volver()
    try:
        f = request.form
        mensaje = servicio.agregar_grupo(conn, f.get('nombre_grupo'), f.get('generacion_inicio'),
                                         f.get('generacion_fin'), f.get('id_carrera'))
        flash(mensaje, "success")
    except ErrorNegocio as e:
        flash(e.mensaje, "danger")
    except Exception:
        logger.exception("Error al guardar el grupo")
        flash("Error al guardar el grupo. Inténtalo de nuevo o avisa al administrador.", "danger")
    return _volver()


@asignaciones_bp.route('/asignaciones/eliminar_grupo/<int:id_grupo>', methods=['POST'])
@role_required(*config.ROLES_ADMINISTRATIVOS)
def eliminar_grupo(id_grupo):
    conn = get_db()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return _volver()
    try:
        servicio.desactivar_grupo(conn, id_grupo)
        flash("El grupo ha sido eliminado.", "success")
    except Exception:
        logger.exception("Error al eliminar el grupo")
        flash("No se pudo eliminar el grupo. Inténtalo de nuevo.", "danger")
    return _volver()


@asignaciones_bp.route('/asignaciones/editar_grupo/<int:id_grupo>', methods=['POST'])
@role_required(*config.ROLES_ADMINISTRATIVOS)
def editar_grupo(id_grupo):
    conn = get_db()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return _volver()
    try:
        f = request.form
        servicio.actualizar_grupo(conn, id_grupo, f.get('nombre_grupo'), f.get('generacion_inicio'),
                                  f.get('generacion_fin'), f.get('id_carrera'))
        flash("El grupo fue actualizado correctamente.", "success")
    except ErrorNegocio as e:
        flash(e.mensaje, "warning")
    except Exception:
        logger.exception("Error al actualizar el grupo")
        flash("Error al intentar actualizar los datos del grupo.", "danger")
    return _volver()