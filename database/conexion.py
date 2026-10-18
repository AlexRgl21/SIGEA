# Acceso a SQL Server: UNA conexión por petición.
import logging
import os

import pyodbc
from dotenv import load_dotenv
from flask import g

load_dotenv()
logger = logging.getLogger(__name__)

DRIVER = '{ODBC Driver 17 for SQL Server}'
LOGIN_TIMEOUT_SEG = 5


def _cadena_conexion():
    return (
        f'DRIVER={DRIVER};'
        f'SERVER={os.getenv("DB_SERVER")};'
        f'DATABASE={os.getenv("DB_NAME")};'
        f'Trusted_Connection=yes;'
        f'Encrypt=yes;'
        f'TrustServerCertificate=yes;'
        f'MARS_Connection=yes'
    )


def crear_conexion():
    try:
        conn = pyodbc.connect(_cadena_conexion(), timeout=LOGIN_TIMEOUT_SEG)
        logger.debug("Conexión abierta a SIGEA")
        return conn
    except pyodbc.Error:
        logger.exception("Error al conectar con la base de datos")
        return None


def get_db():
    if 'db' not in g:
        g.db = crear_conexion()
    return g.db


def cerrar_db(error=None):
    conn = g.pop('db', None)
    if conn is None:
        return
    try:
        if error is not None:
            conn.rollback()
    except pyodbc.Error:
        logger.warning("No se pudo hacer rollback al cerrar la petición", exc_info=True)
    try:
        conn.close()
        logger.debug("Conexión cerrada")
    except pyodbc.Error:
        logger.warning("No se pudo cerrar la conexión", exc_info=True)


def init_app(app):
    app.teardown_appcontext(cerrar_db)