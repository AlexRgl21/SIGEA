from flask import Blueprint, render_template

usuarios_bp = Blueprint('usuarios', __name__)

@usuarios_bp.route('/usuarios')
def lista_usuarios():
    return render_template('usuarios.html')