"""Configuración central del registro (logs) de SIGEA.

- Consola: mensajes desde nivel INFO.
- logs/sigea.log: solo avisos y errores (WARNING o más), con el traceback completo.
- logs/auditoria.log: acciones importantes (INFO), p. ej. el cierre de periodos y el
  borrado de sus asignaciones. Así no se mezclan con los errores.

Los archivos rotan al llegar a 1 MB y se conservan 5.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

RAIZ_PROYECTO = os.path.dirname(os.path.abspath(__file__))
NOMBRE_AUDITORIA = 'sigea.auditoria'


def _carpeta_logs(carpeta=None):
    return carpeta or os.getenv('LOG_DIR') or os.path.join(RAIZ_PROYECTO, 'logs')


def _handler_archivo(ruta, nivel, formato):
    handler = RotatingFileHandler(ruta, maxBytes=1_000_000, backupCount=5,
                                  encoding='utf-8', delay=True)
    handler.setLevel(nivel)
    handler.setFormatter(formato)
    return handler


def configurar_logging(carpeta=None):
    raiz = logging.getLogger()
    if getattr(raiz, '_sigea_configurado', False):
        return                                   # evita duplicar handlers
    raiz.setLevel(logging.INFO)

    formato = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s')

    consola = logging.StreamHandler()
    consola.setLevel(logging.INFO)
    consola.setFormatter(formato)
    raiz.addHandler(consola)

    carpeta = _carpeta_logs(carpeta)
    try:
        os.makedirs(carpeta, exist_ok=True)
        if not os.access(carpeta, os.W_OK):
            raise PermissionError(f"sin permiso de escritura en '{carpeta}'")
        raiz.addHandler(_handler_archivo(os.path.join(carpeta, 'sigea.log'), logging.WARNING, formato))
        logging.getLogger(NOMBRE_AUDITORIA).addHandler(
            _handler_archivo(os.path.join(carpeta, 'auditoria.log'), logging.INFO, formato))
    except OSError as error:
        # La app NO debe caerse por no poder escribir logs: se sigue solo con la consola
        raiz.warning("No se pudo preparar la carpeta de logs '%s' (%s). "
                     "Solo habrá registro en consola.", carpeta, error)

    raiz._sigea_configurado = True