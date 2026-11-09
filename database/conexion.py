
import logging
import os

import psycopg
from dotenv import load_dotenv
from flask import g

load_dotenv()

logger = logging.getLogger(__name__)


# Configuración de conexión
def crear_conexion():
    url = os.getenv("DATABASE_URL", "").strip()

    opciones = {
        "connect_timeout": int(
            os.getenv("DB_CONNECT_TIMEOUT", "8")
        ),
        "sslmode": os.getenv(
            "DB_SSLMODE", "disable"
        ),
        "application_name": "SIGEA",
        "prepare_threshold": None,
    }

    if url:
        opciones["conninfo"] = url
    else:
        opciones.update({
            "host": os.getenv(
                "DB_HOST", "127.0.0.1"
            ),
            "port": int(
                os.getenv("DB_PORT", "5432")
            ),
            "dbname": os.getenv(
                "DB_NAME", "sigea"
            ),
            "user": os.getenv(
                "DB_USER", "postgres"
            ),
            "password": os.getenv(
                "DB_PASSWORD", ""
            ),
        })

    try:
        conn = psycopg.connect(**opciones)

        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('TimeZone', %s, false)",
                (
                    os.getenv(
                        "APP_TIMEZONE",
                        "America/Mexico_City"
                    ),
                )
            )

        conn.commit()
        return conn

    except psycopg.Error:
        logger.exception(
            "No se pudo conectar a PostgreSQL"
        )
        return None


# Conexión utilizada por las rutas Flask
def get_db():
    if "db" not in g:
        g.db = crear_conexion()

    return g.db


# Cierre de conexión
def cerrar_db(error=None):
    conn = g.pop("db", None)

    if conn is None:
        return

    try:
        conn.rollback()

    except psycopg.Error:
        logger.warning(
            "No se pudo revertir la transacción",
            exc_info=True
        )

    finally:
        conn.close()


# Registro en Flask
def init_app(app):
    app.teardown_appcontext(cerrar_db)
