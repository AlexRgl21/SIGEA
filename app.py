from flask import Flask, redirect, url_for
from routes.auth import auth_bp
from routes.panel import panel_bp
from routes.usuarios import usuarios_bp
from routes.gestion import gestion_bp
from routes.asignaciones import asignaciones_bp
from routes.reservas import reservas_bp
from datetime import timedelta
# Inicializamos la aplicación de Flask

app = Flask(__name__)
app.secret_key = "una_clave_muy_secreta_para_sigea"

app.permanent_session_lifetime = timedelta(minutes=5) #contador para cerrar sesión

app.register_blueprint(auth_bp)
app.register_blueprint(panel_bp)
app.register_blueprint(usuarios_bp)
app.register_blueprint(gestion_bp)
app. register_blueprint(asignaciones_bp)
app.register_blueprint(reservas_bp)

# Definimos la ruta principal
@app.route('/')
def index():
    return redirect(url_for('auth.login'))
if __name__ == '__main__':
    # debug=True hace que el servidor se reinicie automáticamente 
    app.run(debug=True)