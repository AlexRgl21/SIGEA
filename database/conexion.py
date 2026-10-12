import logging
import pyodbc
import os 
from dotenv import load_dotenv
logger = logging.getLogger(__name__)

load_dotenv()

def get_db_connection():
    try:
        server = os.getenv('DB_SERVER')
        database = os.getenv('DB_NAME')


        driver = '{ODBC Driver 17 for SQL Server}'

        conexion_str =(
            f'DRIVER={driver};'
            f'SERVER={server};'
            f'DATABASE={database};'
            f'Trusted_Connection=yes;'
            f'Encrypt=yes;'
            f'TrustServerCertificate=yes'
        )

        conn = pyodbc.connect(conexion_str)
        logger.debug("Conexión exitosa a SIGEA")
        return conn
   
    except pyodbc.Error:
        logger.exception("Error al conectar con la base de datos")
        return None


