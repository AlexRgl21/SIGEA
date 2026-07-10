from flask import Flask, redirect, url_for, session
from routes.auth import auth_bp
from routes.panel import panel_bp
from routes.usuarios import usuarios_bp
from routes.gestion import gestion_bp
from routes.asignaciones import asignaciones_bp
from routes.reservas import reservas_bp
from datetime import timedelta
import datetime
from database.conexion import get_db_connection

# Inicializamos la aplicación de Flask
app = Flask(__name__)
app.secret_key = "una_clave_muy_secreta_para_sigea"

app.permanent_session_lifetime = timedelta(minutes=5) #contador para cerrar sesión

app.register_blueprint(auth_bp)
app.register_blueprint(panel_bp)
app.register_blueprint(usuarios_bp)
app.register_blueprint(gestion_bp)
app.register_blueprint(asignaciones_bp)
app.register_blueprint(reservas_bp)

#
# MOTOR DE NOTIFICACIONES GLOBALES (CAMPANA)# 
@app.context_processor
def inyectar_notificaciones():
    notificaciones = []
    cantidad_notis = 0
    
    if 'id_usuario' in session and 'role' in session:
        rol = session.get('role')
        id_usuario = session.get('id_usuario')
        
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                
                # 1. LÓGICA PARA COORDINADOR Y ADMIN
                if rol in ['ADMIN', 'COORDINADOR']:
                    cursor.execute("""
                        SELECT u.nombre, u.apellidos, e.nombre, r.fecha, r.id_reserva
                        FROM Reservas r
                        JOIN Usuarios u ON r.id_usuario = u.id_usuario
                        JOIN Espacios e ON r.id_espacio = e.id_espacio
                        WHERE UPPER(TRIM(r.estado)) = 'PENDIENTE'
                        ORDER BY r.id_reserva DESC
                    """)
                    for fila in cursor.fetchall():
                        notificaciones.append({
                            'mensaje': f"Nueva solicitud de {fila[0]} {fila[1]} para {fila[2]} el día {fila[3]}.",
                            'url': url_for('reservas.vista_reserva') # Enlace al módulo
                        })
                        
                # 2. LÓGICA PARA EL MAESTRO (Trae las últimas 5 respuestas)
                elif rol == 'MAESTRO':
                    cursor.execute("""
                        SELECT TOP 5 e.nombre, r.estado, r.fecha, r.id_reserva
                        FROM Reservas r
                        JOIN Espacios e ON r.id_espacio = e.id_espacio
                        WHERE r.id_usuario = ? 
                          AND UPPER(TRIM(r.estado)) IN ('APROBADA', 'RECHAZADA')
                        ORDER BY r.id_reserva DESC
                    """, (id_usuario,))
                    
                    for fila in cursor.fetchall():
                        estado_limpio = "Aprobada" if "APROBADA" in str(fila[1]).upper() else "Rechazada"
                        notificaciones.append({
                            'mensaje': f"Tu reserva en {fila[0]} (Folio: REQ-{fila[3]}) fue {estado_limpio} para el día {fila[2]}.",
                            'url': url_for('reservas.vista_reserva') # Enlace al módulo
                        })
                        
                cantidad_notis = len(notificaciones)
            except Exception as e:
                print(f"Error en motor de notificaciones: {e}")
            finally:
                conn.close()
            
    return dict(notis=notificaciones, cant_notis=cantidad_notis)

# Definimos la ruta principal
@app.route('/')
def index():
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    # debug=True hace que el servidor se reinicie automáticamente 
    app.run(debug=True)