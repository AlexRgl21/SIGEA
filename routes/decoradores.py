from functools import wraps
from flask import redirect, session, url_for
import config
from database.conexion import get_db

def role_required(*roles):
    # Permite el acceso solo si el usuario existe, está activo y su rol coincide en tiempo real contra la BD.
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            id_usuario = session.get('id_usuario')
            if not id_usuario:
                session.clear()
                return redirect(url_for('auth.login', error="Sesión no iniciada o expirada."))

            conn = get_db()
            if not conn:
                session.clear()
                return redirect(url_for('auth.login', error="Error de conexión con la base de datos."))

            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT estado, id_rol 
                        FROM Usuarios 
                        WHERE id_usuario = %s
                    """, (id_usuario,))
                    usuario = cursor.fetchone()

                # Si el usuario fue borrado o desactivado en la BD
                if not usuario or usuario[0] != 'Activo':
                    session.clear()
                    return redirect(url_for('auth.login', error="Tu cuenta ha sido desactivada o ya no existe."))

                # Mapeamos el id_rol al nombre del rol usando la misma configuración del sistema
                rol_actual = config.ROLES_POR_ID.get(usuario[1])
                
                if not rol_actual or rol_actual not in roles:
                    session.clear()
                    return redirect(url_for('auth.login', error="Acceso denegado: tus permisos fueron modificados."))

                # Actualizamos el rol en la sesión por si cambió en caliente
                session['role'] = rol_actual

            except Exception:
                session.clear()
                return redirect(url_for('auth.login', error="Error al validar la sesión."))
            
            return f(*args, **kwargs)
        
        decorated_function.roles = roles
        return decorated_function
    return decorator