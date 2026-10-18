from functools import wraps

from flask import redirect, session, url_for


def role_required(*roles):
    # Permite el acceso solo a los roles indicados; si no, limpia la sesión y manda al login.
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            rol_actual = session.get('role')
            if not rol_actual or rol_actual not in roles:
                session.clear()
                return redirect(url_for('auth.login', error="Acceso denegado o sesión expirada."))
            return f(*args, **kwargs)
        decorated_function.roles = roles
        return decorated_function
    return decorator