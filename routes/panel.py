from flask import Blueprint, render_template, session, redirect, url_for

panel_bp = Blueprint('panel', __name__)

@panel_bp.route('/panel')
def inicio():

    #candado para mandarte al login despues del tiempo establecido
    if 'id_usuario' not in session:
        return redirect(url_for('auth.login'))
    
    return render_template('principal.html')