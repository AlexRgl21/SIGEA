from flask import Blueprint, flash, render_template, request

import config
from database.conexion import get_db
from services import panel as servicio
from .decoradores import role_required

panel_bp = Blueprint('panel', __name__)

# Valores que usa principal.html cuando no hay base de datos
PANEL_VACIO = dict(total_espacios=0, bloqueados=0, ocupados=0, libres=0,
                   reservas_hoy=[], datos_grafica=[], dia_hoy='', tabla_disponibilidad=[],
                   page=1, total_pages=1, q='', estado='todos')


@panel_bp.route('/panel')
@role_required(*config.ROLES_ADMINISTRATIVOS)
def inicio():
    conn = get_db()
    
    # Capturamos la página y los filtros actuales de la URL
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
    q = (request.args.get('q') or '').strip()
    estado = (request.args.get('estado') or 'todos').strip().lower()
        
    if not conn:
        flash("No se pudo conectar con la base de datos. Inténtalo de nuevo en unos minutos.", "danger")
        return render_template('principal.html', **PANEL_VACIO)
        
    # Le pasamos la página y los filtros al servicio para que haga el cálculo real
    datos_panel = servicio.calcular_panel(conn, page=page, q=q, estado=estado)
    return render_template('principal.html', **datos_panel)