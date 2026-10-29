from flask import Blueprint, flash, render_template, request

import config
from database.conexion import get_db
from services import panel as servicio
from .decoradores import role_required

panel_bp = Blueprint('panel', __name__)

PANEL_VACIO = dict(total_espacios=0, bloqueados=0, ocupados=0, libres=0,
                   reservas_hoy=[], datos_grafica=[], dia_hoy='', tabla_disponibilidad=[],
                   page=1, total_pages=1)


@panel_bp.route('/panel')
@role_required(*config.ROLES_ADMINISTRATIVOS)
def inicio():
    conn = get_db()
    
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
        
    if not conn:
        flash("No se pudo conectar con la base de datos. Inténtalo de nuevo en unos minutos.", "danger")
        return render_template('principal.html', **PANEL_VACIO)
        
    datos_panel = servicio.calcular_panel(conn, page)
    return render_template('principal.html', **datos_panel)