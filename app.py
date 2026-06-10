from flask import Flask, redirect, url_for
from routes.auth import auth_bp
from routes.panel import panel_bp
from routes.usuarios import usuarios_bp


# Inicializamos la aplicación de Flask
app = Flask(__name__)

app.register_blueprint(auth_bp)
app.register_blueprint(panel_bp)
app.register_blueprint(usuarios_bp)

# Definimos la ruta principal (la "portada" de tu página)
@app.route('/')
def index():
    return redirect(url_for('auth.login'))
# Le decimos a Python que arranque el servidor si ejecutamos este archivo directamente
if __name__ == '__main__':
    # debug=True hace que el servidor se reinicie automáticamente si guardas cambios en tu código
    app.run(debug=True)