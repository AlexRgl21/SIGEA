from flask import Blueprint, render_template

asignaciones_bp = Blueprint('asignaciones', __name__)

@asignaciones_bp.route('/asignaciones')
def vista_asignaciones():
    return render_template('asignaciones.html')