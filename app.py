from flask import Flask, redirect, url_for
from routes.auth import auth_bp
from routes.panel import panel_bp
from routes.usuarios import usuarios_bp
from routes.gestion import gestion_bp

# Inicializamos la aplicación de Flask
app = Flask(__name__)

app.register_blueprint(auth_bp)
app.register_blueprint(panel_bp)
app.register_blueprint(usuarios_bp)
app.register_blueprint(gestion_bp)

# Definimos la ruta principal
@app.route('/')
def index():
    return redirect(url_for('auth.login'))
if __name__ == '__main__':
    # debug=True hace que el servidor se reinicie automáticamente 
    app.run(debug=True)