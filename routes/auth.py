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

            cursor.execute("SELECT id_usuario, nombre, estado FROM Usuarios WHERE correo = ? AND contrasena = ?",(correo,contrasena))
            usuario = cursor.fetchone()
            conn.close()

            if usuario: 
                estado_usuario =usuario[2]

                if estado_usuario == 'Inactivo':
                    return render_template('login.html', error = "Tu cuenta ha sido desactivada. Por favor, contacta a la Coordinación Académica.")
                else: 
                    return redirect(url_for('panel.inicio'))
            else:
                return render_template('login.html', error = "Correo o contraseña incorrectos")
        else:
            return render_template('login.html', error="Error al conectar con la base de datos")
                    
        
    return render_template('login.html')

#regresar el login
@auth_bp.route('/logout')
def logout():
    return redirect(url_for('auth.login'))