# Errores esperados de negocio
class ErrorNegocio(Exception):
    def __init__(self, mensaje, status=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status = status      # código HTTP opcional (por ejemplo 429)