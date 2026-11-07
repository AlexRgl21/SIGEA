import logging
from urllib.parse import urlparse

from flask import Blueprint, render_template, request, session, redirect, url_for, flash

import config
from database.conexion import get_db
from services import tickets as servicio
from services.errores import ErrorNegocio
from .decoradores import role_required

tickets_bp = Blueprint('tickets', __name__)
logger = logging.getLogger(__name__)

DESTINO = 'tickets.vista_tickets'
ROLES_SOLICITANTES = config.TODOS_LOS_ROLES          # todos menos Soporte
ROLES_TODOS_CON_SOPORTE = config.TODOS_LOS_ROLES + (config.ROL_SOPORTE,)


def _volver():
    return redirect(url_for(DESTINO))


def _volver_al_origen():
    # Tras reportar desde el botón flotante, regresa a la página donde estaba (solo páginas propias).
    origen = request.referrer
    if origen and urlparse(origen).netloc == request.host:
        return redirect(origen)
    return _volver()


@tickets_bp.route('/soporte')
@role_required(*ROLES_TODOS_CON_SOPORTE)
def vista_tickets():
    conn = get_db()
    es_soporte = session.get('role') == config.ROL_SOPORTE
    vacio = dict(es_soporte=es_soporte, abiertos=[], en_proceso=[], resueltos=[], mis_tickets=[],
                 prioridades=config.TICKET_PRIORIDADES, estados=config.TICKET_ESTADOS)
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return render_template('tickets.html', **vacio)
    try:
        if es_soporte:
            vacio['abiertos'], vacio['en_proceso'], vacio['resueltos'] = servicio.tablero(conn)
        else:
            vacio['mis_tickets'] = servicio.listar_mios(conn, session.get('id_usuario'))
    except Exception:
        logger.exception("Error al cargar los tickets")
        flash("No se pudieron cargar los tickets. Inténtalo de nuevo.", "danger")
    return render_template('tickets.html', **vacio)


@tickets_bp.route('/soporte/nuevo', methods=['POST'])
@role_required(*ROLES_SOLICITANTES)
def crear_ticket():
    conn = get_db()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return _volver_al_origen()
    try:
        f = request.form
        servicio.crear(conn, session.get('id_usuario'), f.get('asunto'), f.get('categoria'),
                       f.get('descripcion'))
        flash("Tu ticket fue enviado a Soporte Técnico.", "success")
    except ErrorNegocio as e:
        flash(e.mensaje, "danger")
    except Exception:
        logger.exception("Error al crear el ticket")
        flash("Error al enviar el ticket. Inténtalo de nuevo.", "danger")
    return _volver_al_origen()


@tickets_bp.route('/soporte/gestionar/<int:id>', methods=['POST'])
@role_required(config.ROL_SOPORTE)
def gestionar_ticket(id):
    conn = get_db()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return _volver()
    try:
        servicio.gestionar(conn, id, session.get('id_usuario'),
                           request.form.get('estado'), request.form.get('prioridad'),
                           request.form.get('respuesta'))
        flash("Ticket actualizado correctamente.", "success")
    except ErrorNegocio as e:
        flash(e.mensaje, "danger")
    except Exception:
        logger.exception("Error al gestionar el ticket")
        flash("Error al actualizar el ticket. Inténtalo de nuevo.", "danger")
    return _volver()