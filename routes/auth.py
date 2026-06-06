from flask import Blueprint, render_template, request, redirect, url_for
from database.conexion import get_db_connection

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        contrasena = request.form['contrasena']

        conn = get_db_connection()
        if conn :
            cursor = conn.cursor()

            cursor.execute("SELECT id_usuario, nombre FROM Usuarios WHERE correo = ? AND contrasena = ?",(correo,contrasena))
            usuario = cursor.fetchone()
            conn.close()

            if usuario:
                return redirect(url_for('panel.inicio'))
            else:
                return render_template('login.html', error="Correo o contraseña incorrectos")
        else:
            return render_template('login.html', error="Error al conectar con la base de datos")
        
    return render_template('login.html')