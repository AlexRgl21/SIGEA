from flask import Blueprint, render_template

reservas_bp = Blueprint('reservas', __name__)

@reservas_bp.route('/reservas')
def vista_reserva():
    return render_template('reservas.html')