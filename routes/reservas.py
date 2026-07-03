from flask import Blueprint, render_template, session, redirect, url_for

reservas_bp = Blueprint('reservas', __name__)

@reservas_bp.route('/reservas')
def vista_reserva():

    #candado para mandarte al login despues del tiempo establecido
    if 'id_usuario' not in session:
        return redirect(url_for('auth.login'))
    
    return render_template('reservas.html')