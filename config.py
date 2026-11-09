
import os
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

APP_TIMEZONE = os.getenv(
    'APP_TIMEZONE',
    'America/Mexico_City'
)


def ahora_local():
    return datetime.now(
        ZoneInfo(APP_TIMEZONE)
    ).replace(tzinfo=None)


def fecha_actual():
    return ahora_local().date()


SESION_MINUTOS = 5
SESION_AVISO_SEG = 60
SESION_PING_SEG = 30

# Roles
ROL_ADMIN = 'ADMIN'
ROL_COORDINADOR = 'COORDINADOR'
ROL_MAESTRO = 'MAESTRO'
ROL_ALMACEN = 'ALMACEN'
ROL_SOPORTE = 'SOPORTE'

ROLES_POR_ID = {
    1: ROL_ADMIN,
    2: ROL_COORDINADOR,
    3: ROL_MAESTRO,
    4: ROL_ALMACEN,
    5: ROL_SOPORTE
}

NOMBRES_ROL = {
    1: 'Administrador',
    2: 'Coordinador de Carrera',
    3: 'Docente',
    4: 'Almacén',
    5: 'Soporte'
}

ID_ROL_MAESTRO = 3
ID_ROL_SOPORTE = 5

ROLES_ADMINISTRATIVOS = (
    ROL_ADMIN,
    ROL_COORDINADOR
)

TODOS_LOS_ROLES = (
    ROL_ADMIN,
    ROL_COORDINADOR,
    ROL_MAESTRO,
    ROL_ALMACEN
)

TICKET_CATEGORIAS = (
    'Error del sistema',
    'Asignación de horarios',
    'Reservas',
    'Acceso o contraseña',
    'Otro'
)

TICKET_PRIORIDADES = (
    'Baja',
    'Media',
    'Alta'
)

TICKET_ESTADOS = (
    'Abierto',
    'En proceso',
    'Resuelto'
)

TICKET_MAX_SIN_RESOLVER = 5
TICKET_MAX_RESUELTOS_VISTA = 50

# Colores
COLORES_CARRERA = {
    'ITIID': '#67A15F',
    'IRC': '#C8C7C5',
    'LTF': '#436DA8',
    'IMI': '#D67A38',
    'ISA': '#CF4444',
    'IAEV': '#9854C4',
    'ISW': '#67A15F',
    'ING': '#F7F088',
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

# Calendario y espacios
DIAS_SEMANA = [
    'Lunes',
    'Martes',
    'Miércoles',
    'Jueves',
    'Viernes',
    'Sábado',
    'Domingo'
]

DIA_A_NUMERO_CALENDARIO = {
    'Lunes': 1,
    'Martes': 2,
    'Miércoles': 3,
    'Jueves': 4,
    'Viernes': 5,
    'Sábado': 6
}

TIPO_ESPACIO_AULA = 'Aula Clásica'

TIPOS_ESPACIO_RESERVABLES = (
    'laboratorio',
    'sala de conferencia'
)

VALIDAR_CHOQUE_DE_GRUPO = True

# Periodos
PERIODOS_REVISION_SEG = 60

NOTIS_LIMITE = 15

CODIGO_LONGITUD = 6
CODIGO_VIGENCIA_MIN = 10
MAX_INTENTOS = 5
ESPERA_REENVIO_SEG = 60
MAX_ENVIOS_POR_HORA = 5
CAMBIO_VIGENCIA_MIN = 10
LONGITUD_MINIMA_PASSWORD = 8

LOGIN_MAX_INTENTOS = 5
LOGIN_MAX_INTENTOS_IP = 20
LOGIN_VENTANA_MIN = 15

DOMINIO_CORREO = os.getenv(
    'DOMINIO_CORREO',
    'upsrj.edu.mx'
)

SMTP_HOST = os.getenv(
    'SMTP_HOST',
    'smtp.gmail.com'
)

SMTP_PUERTO = int(
    os.getenv('SMTP_PUERTO', '587')
)

SMTP_TIMEOUT_SEG = 15


def aplicar_config(app):
    app.secret_key = os.getenv('SECRET_KEY')

    if not app.secret_key:
        raise RuntimeError(
            "Falta SECRET_KEY en el .env"
        )

    app.permanent_session_lifetime = timedelta(
        minutes=SESION_MINUTOS
    )

    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    app.config['SESSION_COOKIE_SECURE'] = (
        os.getenv('COOKIE_SECURE', '0') == '1'
    )

    app.config['WTF_CSRF_TIME_LIMIT'] = None
