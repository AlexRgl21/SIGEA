import logging

from flask import Blueprint, jsonify, session

from database.conexion import get_db
from services import notificaciones as servicio

notificaciones_bp = Blueprint('notificaciones', __name__)
logger = logging.getLogger(__name__)


@notificaciones_bp.route('/notificaciones/leer', methods=['POST'])
def marcar_leidas():
    # La campana llama a esto al abrirse: marca como leídas las notificaciones visibles.
    if 'id_usuario' not in session or 'role' not in session:
        return jsonify(ok=False), 401
    conn = get_db()
    if not conn:
        return jsonify(ok=False), 503
    try:
        cantidad = servicio.marcar_leidas(conn, session['role'], session['id_usuario'])
        return jsonify(ok=True, marcadas=cantidad)
    except Exception:
        logger.exception("No se pudieron marcar las notificaciones como leídas")
        return jsonify(ok=False), 500