import pyodbc
import os 
from dotenv import load_dotenv

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
        print("Conexión exitosa a SIGEA")
        return conn
   
    except pyodbc.Error as e:
        print(f"Error al conectar con la base de datos: {e}")
        return None
