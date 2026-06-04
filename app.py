from flask import Flask, render_template


# Inicializamos la aplicación de Flask
app = Flask(__name__)


# Definimos la ruta principal (la "portada" de tu página)
@app.route('/')
def inicio():
    # Aquí Flask va a buscar tu archivo principal.html dentro de la carpeta 'templates'
    return render_template('principal.html')


# Le decimos a Python que arranque el servidor si ejecutamos este archivo directamente
if __name__ == '__main__':
    # debug=True hace que el servidor se reinicie automáticamente si guardas cambios en tu código
    app.run(debug=True)