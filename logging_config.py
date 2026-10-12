"""Configuración central del registro de errores de SIGEA.
- Consola: mensajes desde nivel INFO (como ahora).
- Archivo logs/sigea.log: solo avisos y errores (WARNING o más), con el traceback
  completo. Rota solo al llegar a 1 MB y conserva 5 archivos.
"""
import logging
import os
from logging.handlers import RotatingFileHandler


def configurar_logging(carpeta='logs'):
    raiz = logging.getLogger()
    if getattr(raiz, '_sigea_configurado', False):
        return                                   # evita duplicar handlers
    raiz.setLevel(logging.INFO)

    formato = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s')

    os.makedirs(carpeta, exist_ok=True)
    archivo = RotatingFileHandler(os.path.join(carpeta, 'sigea.log'),
                                maxBytes=1_000_000, backupCount=5,
                                encoding='utf-8', delay=True)
    archivo.setLevel(logging.WARNING)
    archivo.setFormatter(formato)

    consola = logging.StreamHandler()
    consola.setLevel(logging.INFO)
    consola.setFormatter(formato)

    raiz.addHandler(archivo)
    raiz.addHandler(consola)
    raiz._sigea_configurado = True