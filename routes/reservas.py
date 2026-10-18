import logging

from flask import Blueprint, render_template, request, session, redirect, url_for, flash

import config
from database.conexion import get_db
from services import reservas as servicio
from services.errores import ErrorNegocio
from .decoradores import role_required

reservas_bp = Blueprint('reservas', __name__)
logger = logging.getLogger(__name__)

DESTINO = 'reservas.vista_reserva'


def _volver():
    return redirect(url_for(DESTINO))


@reservas_bp.route('/reservas')
@role_required(*config.TODOS_LOS_ROLES)
def vista_reserva():
    conn = get_db()
    if not conn:
        flash("Error de conexión a la base de datos", "danger")
        return render_template('reservas.html', pendientes=[], aprobadas=[], espacios=[])
    pendientes, aprobadas, espacios = servicio.datos_vista(
        conn, session.get('role'), session.get('id_usuario'))
    return render_template('reservas.html', pendientes=pendientes, aprobadas=aprobadas, espacios=espacios)


@reservas_bp.route('/reservas/nueva', methods=['POST'])
@role_required(*config.TODOS_LOS_ROLES)
def crear_reserva():
    conn = get_db()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return _volver()
    try:
        f = request.form
        servicio.crear_reserva(conn, session.get('id_usuario'), f.get('id_espacio'), f.get('fecha'),
                               f.get('hora_inicio'), f.get('hora_fin'), f.get('motivo'))
        flash("Solicitud de reserva enviada correctamente a revisión.", "success")
    except ErrorNegocio as e:
        flash(e.mensaje, "danger")
    except Exception:
        logger.exception("Error al guardar la reserva")
        flash("Error al guardar la reserva. Inténtalo de nuevo o avisa al administrador.", "danger")
    return _volver()


@reservas_bp.route('/reservas/aceptar/<int:id>', methods=['POST'])
@role_required(*config.ROLES_ADMINISTRATIVOS)
def aceptar_reserva(id):
    conn = get_db()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return _volver()
    try:
        servicio.aprobar_reserva(conn, id)
        flash("La reserva fue aprobada con éxito.", "success")
    except ErrorNegocio as e:
        flash(e.mensaje, "danger")
    except Exception:
        logger.exception("Error al aceptar la reserva")
        flash("Error al aceptar la reserva. Inténtalo de nuevo o avisa al administrador.", "danger")
    return _volver()


@reservas_bp.route('/reservas/rechazar/<int:id>', methods=['POST'])
@role_required(*config.ROLES_ADMINISTRATIVOS)
def rechazar_reserva(id):
    conn = get_db()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return _volver()
    try:
        servicio.rechazar_reserva(conn, id)
        flash("La reserva fue rechazada y eliminada del panel.", "success")
    except ErrorNegocio as e:
        flash(e.mensaje, "danger")
    except Exception:
        logger.exception("Error al rechazar la reserva")
        flash("Error al rechazar la reserva. Inténtalo de nuevo o avisa al administrador.", "danger")
    return _volver()