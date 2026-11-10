import logging
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)

import config
from database.conexion import get_db
from services import reservas
from services.errores import ErrorNegocio
from .decoradores import role_required

logger = logging.getLogger(__name__)

reservas_bp = Blueprint('reservas', __name__)


@reservas_bp.route('/reservas')
@role_required(
    config.ROL_ADMIN,
    config.ROL_COORDINADOR,
    config.ROL_MAESTRO,
    config.ROL_ALMACEN
)
def vista_reserva():
    conn = get_db()
    if not conn:
        flash("Error de conexión con la base de datos.", "danger")
        return redirect(url_for('panel.dashboard'))

    pendientes, aprobadas, espacios = reservas.datos_vista(
        conn,
        session.get('role'),
        session.get('id_usuario')
    )

    return render_template(
        'reservas.html',
        pendientes=pendientes,
        aprobadas=aprobadas,
        espacios=espacios
    )


# Solución AUD-003 y corrección del endpoint a 'crear_reserva' para que coincida con el HTML
@reservas_bp.route('/reservas/nueva', methods=['POST'])
@role_required(
    config.ROL_ADMIN,
    config.ROL_MAESTRO
)
def crear_reserva():
    conn = get_db()
    if not conn:
        flash("Error de conexión con la base de datos.", "danger")
        return redirect(url_for('reservas.vista_reserva'))

    try:
        reservas.crear_reserva(
            conn,
            session.get('id_usuario'),
            request.form.get('id_espacio'),
            request.form.get('fecha'),
            request.form.get('hora_inicio'),
            request.form.get('hora_fin'),
            request.form.get('motivo')
        )
        flash("Solicitud de reserva enviada correctamente.", "success")
    except ErrorNegocio as e:
        flash(str(e), "warning")
    except Exception:
        logger.exception("Error al crear la reserva")
        flash("Ocurrió un error al procesar la solicitud.", "danger")

    return redirect(url_for('reservas.vista_reserva'))


@reservas_bp.route('/reservas/aprobar/<int:id_reserva>', methods=['POST'])
@role_required(
    config.ROL_ADMIN,
    config.ROL_COORDINADOR,
    config.ROL_ALMACEN
)
def aprobar_reserva(id_reserva):
    conn = get_db()
    if not conn:
        flash("Error de conexión con la base de datos.", "danger")
        return redirect(url_for('reservas.vista_reserva'))

    try:
        reservas.aprobar_reserva(conn, id_reserva)
        flash("Reserva aprobada exitosamente.", "success")
    except ErrorNegocio as e:
        flash(str(e), "warning")
    except Exception:
        logger.exception("Error al aprobar la reserva %s", id_reserva)
        flash("Ocurrió un error al aprobar la reserva.", "danger")

    return redirect(url_for('reservas.vista_reserva'))


@reservas_bp.route('/reservas/rechazar/<int:id_reserva>', methods=['POST'])
@role_required(
    config.ROL_ADMIN,
    config.ROL_COORDINADOR,
    config.ROL_ALMACEN
)
def rechazar_reserva(id_reserva):
    conn = get_db()
    if not conn:
        flash("Error de conexión con la base de datos.", "danger")
        return redirect(url_for('reservas.vista_reserva'))

    try:
        reservas.rechazar_reserva(conn, id_reserva)
        flash("Reserva rechazada.", "info")
    except ErrorNegocio as e:
        flash(str(e), "warning")
    except Exception:
        logger.exception("Error al rechazar la reserva %s", id_reserva)
        flash("Ocurrió un error al rechazar la reserva.", "danger")

    return redirect(url_for('reservas.vista_reserva'))