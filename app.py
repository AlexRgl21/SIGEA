import logging
from urllib.parse import urlparse

import pyodbc
from dotenv import load_dotenv
from flask import Flask, redirect, url_for, session, flash, render_template, request, g
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.exceptions import HTTPException

load_dotenv()

import config
from database import conexion
from database.conexion import get_db
from logging_config import configurar_logging
from routes.auth import auth_bp
from routes.panel import panel_bp
from routes.usuarios import usuarios_bp
from routes.gestion import gestion_bp
from routes.asignaciones import asignaciones_bp
from routes.reservas import reservas_bp
from routes.notificaciones import notificaciones_bp
from services import notificaciones

logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    configurar_logging()
    config.aplicar_config(app)
    CSRFProtect(app)
    conexion.init_app(app)          # cierra la conexión de la petición al terminar

    for bp in (auth_bp, panel_bp, usuarios_bp, gestion_bp,
            asignaciones_bp, reservas_bp, notificaciones_bp):
        app.register_blueprint(bp)

    # CAMPANA DE NOTIFICACIONES + DATOS GLOBALES PARA LAS PLANTILLAS
    @app.context_processor
    def inyectar_globales():
        contexto = {
            'notis': [], 'cant_notis': 0,
            'sesion_total_seg': config.SESION_MINUTOS * 60,
            'sesion_aviso_seg': config.SESION_AVISO_SEG,
            'sesion_ping_seg': config.SESION_PING_SEG,
        }
        if 'id_usuario' in session and 'role' in session:
            if not hasattr(g, 'notis_cache'):          # una sola consulta por petición
                g.notis_cache = _cargar_notificaciones()
            contexto['notis'] = g.notis_cache['lista']
            contexto['cant_notis'] = g.notis_cache['sin_leer']
        return contexto

    def _cargar_notificaciones():
        vacio = {'lista': [], 'sin_leer': 0}
        conn = get_db()                                # misma conexión que usa la ruta
        if not conn:
            return vacio
        try:
            return notificaciones.obtener(conn, session['role'], session['id_usuario'],
                                        url_for('reservas.vista_reserva'))
        except Exception:
            logger.exception("Error en motor de notificaciones")
            return vacio

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    # MANEJO DE ERRORES
    @app.errorhandler(CSRFError)
    def csrf_error(e):
        flash("Tu sesión o el formulario no es válido. Intenta de nuevo.", "danger")
        return redirect(url_for('auth.login'))

    @app.errorhandler(404)
    def pagina_no_encontrada(e):
        return render_template('error.html', titulo="Página no encontrada",
                            mensaje="La dirección que buscas no existe."), 404

    @app.errorhandler(pyodbc.IntegrityError)
    def error_de_integridad(e):
        """Dato repetido o referencia inválida (por ejemplo, un correo que ya existe)."""
        logger.warning("Violación de integridad en %s %s: %s", request.method, request.path, e)
        flash("No se pudo guardar: ya existe un registro con esos datos (por ejemplo, un correo repetido).",
            "danger")
        destino = request.referrer
        if not destino or urlparse(destino).netloc != request.host:   # solo volvemos a páginas propias
            destino = url_for('auth.login')
        return redirect(destino)

    @app.errorhandler(Exception)
    def error_no_controlado(e):
        if isinstance(e, HTTPException):
            return e                       # 405, 400, etc. conservan su comportamiento normal
        logger.exception("Error no controlado en %s %s", request.method, request.path)
        return render_template('error.html', titulo="Algo salió mal",
                            mensaje="Ocurrió un error inesperado y ya quedó registrado. "
                                    "Inténtalo de nuevo en unos minutos."), 500

    return app


app = create_app()

if __name__ == '__main__':
    # debug solo en desarrollo: FLASK_DEBUG=1 en el .env
    import os
    app.run(debug=os.getenv('FLASK_DEBUG', '0') == '1')