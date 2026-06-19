from flask import Blueprint, render_template

gestion_bp = Blueprint('gestion', __name__)

@gestion_bp.route('/gestion')
def vista_gestion():
    return render_template('gestion.html')