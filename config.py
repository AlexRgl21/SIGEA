# Configuración central de SIGEA

import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

# SESIÓN
SESION_MINUTOS = 5          # inactividad máxima antes de cerrar la sesión
SESION_AVISO_SEG = 60       # el aviso aparece cuando faltan estos segundos
SESION_PING_SEG = 30        # mientras haya actividad, se renueva la cookie como máximo cada tanto

# ROLES
ROL_ADMIN = 'ADMIN'
ROL_COORDINADOR = 'COORDINADOR'
ROL_MAESTRO = 'MAESTRO'

ROLES_POR_ID = {1: ROL_ADMIN, 2: ROL_COORDINADOR, 3: ROL_MAESTRO}   # id_rol (BD) -> rol de sesión
NOMBRES_ROL = {1: 'Administrador', 2: 'Coordinador de Carrera', 3: 'Docente'}  # texto que ve el usuario
ID_ROL_MAESTRO = 3
ROLES_ADMINISTRATIVOS = (ROL_ADMIN, ROL_COORDINADOR)
TODOS_LOS_ROLES = (ROL_ADMIN, ROL_COORDINADOR, ROL_MAESTRO)

# COLORES
COLORES_CARRERA = {
    'ITIID': '#67A15F',   # verde olivo
    'IRC': '#C8C7C5',     # gris
    'LTF': '#436DA8',     # azul
    'IMI': '#D67A38',     # naranja
    'ISA': '#CF4444',     # rojo
    'IAEV': '#9854C4',    # morado
    'ISW': '#67A15F',
    'ING': '#F7F088',     # amarillo
    'PREPA': '#FF7700',
}
COLOR_CARRERA_DEFAULT = '#004a98'

COLORES_EDIFICIOS = {
    'Edi - 1': '#324F85',
    'Edi - 2': '#D12424',
    'Edi - 3': '#3A7824',
    'Metra': '#F2E052',
    'Learning': '#6F0EB5',
}
COLOR_EDIFICIO_DEFAULT = '#004a98'

# CALENDARIO Y ESPACIOS

# Deben coincidir EXACTO con los valores que guarda el formulario de asignaciones.
DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
# Número de día para FullCalendar (domingo = 0)
DIA_A_NUMERO_CALENDARIO = {'Lunes': 1, 'Martes': 2, 'Miércoles': 3, 'Jueves': 4,
                           'Viernes': 5, 'Sábado': 6}

TIPO_ESPACIO_AULA = 'Aula Clásica'
TIPOS_ESPACIO_RESERVABLES = ('laboratorio', 'sala de conferencia')

# Validar también que un mismo grupo no esté en dos espacios a la misma hora
VALIDAR_CHOQUE_DE_GRUPO = True

# PERIODOS (CUATRIMESTRES)
PERIODOS_REVISION_SEG = 60

# NOTIFICACIONES (CAMPANA)
NOTIS_LIMITE = 15           # máximo de avisos que se muestran en la campana

# SEGURIDAD: RECUPERACIÓN DE CONTRASEÑA Y LOGIN
CODIGO_LONGITUD = 6
CODIGO_VIGENCIA_MIN = 10        # minutos de vida del código
MAX_INTENTOS = 5                # intentos fallidos permitidos por código
ESPERA_REENVIO_SEG = 60         # segundos mínimos entre un código y el siguiente
MAX_ENVIOS_POR_HORA = 5         # códigos por usuario en una hora
CAMBIO_VIGENCIA_MIN = 10        # minutos para elegir la contraseña una vez verificado el código
LONGITUD_MINIMA_PASSWORD = 8

LOGIN_MAX_INTENTOS = 5          # fallos por correo dentro de la ventana
LOGIN_MAX_INTENTOS_IP = 20      # fallos por IP dentro de la ventana
LOGIN_VENTANA_MIN = 15          # ventana de conteo y duración del bloqueo

# CORREO
DOMINIO_CORREO = os.getenv('DOMINIO_CORREO', 'upsrj.edu.mx')
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PUERTO = int(os.getenv('SMTP_PUERTO', '587'))     # 465 = SSL directo; otro = STARTTLS
SMTP_TIMEOUT_SEG = 15


def aplicar_config(app):
    app.secret_key = os.getenv('SECRET_KEY')
    if not app.secret_key:
        raise RuntimeError("Falta SECRET_KEY en el .env")

    app.permanent_session_lifetime = timedelta(minutes=SESION_MINUTOS)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    app.config['SESSION_COOKIE_SECURE'] = os.getenv('COOKIE_SECURE', '0') == '1'
    app.config['WTF_CSRF_TIME_LIMIT'] = None