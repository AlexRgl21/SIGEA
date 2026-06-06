from flask import Blueprint, render_template

panel_bp = Blueprint('panel', __name__)

@panel_bp.route('/panel')
def inicio():
    return render_template('principal.html')