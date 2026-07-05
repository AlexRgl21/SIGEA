from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session
from database.conexion import get_db_connection

auth_bp = Blueprint('auth', __name__)

# --- DECORADOR DE ROLES ---
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            rol_actual = session.get('role')
            # Si no hay rol o el rol no tiene permiso para esta ruta:
            if not rol_actual or rol_actual not in roles:
                session.clear() # Limpiamos cualquier dato atorado
                # Redirigimos al login enviando un mensaje de error por la URL para evitar bucles
                return redirect(url_for('auth.login', error="Acceso denegado o sesión expirada."))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- RUTA DE LOGIN ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Capturamos el error si fuimos rebotados por el decorador
    error = request.args.get('error')

    if request.method == 'POST':
        correo = request.form['correo']
        contrasena = request.form['contrasena']

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            # Solo pedimos el id_rol (1, 2 o 3) 
            cursor.execute("SELECT id_usuario, nombre, estado, id_rol FROM Usuarios WHERE correo = ? AND contrasena = ?", (correo, contrasena))
            usuario = cursor.fetchone()
            conn.close()

            if usuario: 
                estado_usuario = usuario[2]

                if estado_usuario == 'Inactivo':
                    return render_template('login.html', error="Tu cuenta ha sido desactivada.")
                else: 
                    session.permanent = True
                    session['id_usuario'] = usuario[0]
                    session['nombre_usuario'] = usuario[1]
                    
                    # ASIGNAMOS EL ROL EXACTO 
                    id_rol = usuario[3]
                    
                    if id_rol == 1:
                        session['role'] = 'ADMIN'
                    elif id_rol == 2:
                        session['role'] = 'COORDINADOR'
                    elif id_rol == 3:
                        session['role'] = 'MAESTRO'
                    else:
                        return render_template('login.html', error="Tu usuario no tiene un rol válido asignado.")
                    
                    # Redirigimos según el rol que se acaba de setear
                    if session['role'] == 'MAESTRO':
                        return redirect(url_for('asignaciones.vista_asignaciones'))
                    
                    return redirect(url_for('panel.inicio'))
            else:
                return render_template('login.html', error="Correo o contraseña incorrectos.")
        else:
            return render_template('login.html', error="Error al conectar con la base de datos.")
                    
    return render_template('login.html', error=error)

# --- RUTA DE LOGOUT ---
@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))