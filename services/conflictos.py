# Motor de detección de conflictos (empalmes) de SIGEA.

from dataclasses import dataclass
from datetime import datetime, time

TIPO_ESPACIO = 'ESPACIO'
TIPO_GRUPO = 'GRUPO'


def a_hora(valor):

    if isinstance(valor, datetime):
        return valor.time().replace(microsecond=0)
    if isinstance(valor, time):
        return valor.replace(microsecond=0)
    if isinstance(valor, str):
        texto = valor.strip()
        try:
            return time.fromisoformat(texto).replace(microsecond=0)
        except ValueError:
            raise ValueError(f"Hora inválida: {valor!r}") from None
    raise ValueError(f"Hora inválida: {valor!r}")


def validar_rango(inicio, fin):
    # Devuelve (inicio, fin) como time, o lanza ValueError si el rango no tiene sentido.
    inicio, fin = a_hora(inicio), a_hora(fin)
    if fin <= inicio:
        raise ValueError("La hora de fin debe ser posterior a la hora de inicio.")
    return inicio, fin


def hay_traslape(inicio_a, fin_a, inicio_b, fin_b):
    # True si los dos rangos se traslapan. Tocarse en el borde NO es traslape.
    inicio_a, fin_a = a_hora(inicio_a), a_hora(fin_a)
    inicio_b, fin_b = a_hora(inicio_b), a_hora(fin_b)
    return inicio_a < fin_b and fin_a > inicio_b


def buscar_traslapes(inicio, fin, existentes):
    return [e for e in existentes
            if hay_traslape(inicio, fin, e['hora_inicio'], e['hora_fin'])]


@dataclass(frozen=True)
class Choque:
    tipo: str            # TIPO_ESPACIO o TIPO_GRUPO
    dia: str
    hora_inicio: time    # del horario que ya existe
    hora_fin: time

    def mensaje(self):
        rango = f"{self.hora_inicio.strftime('%H:%M')} a {self.hora_fin.strftime('%H:%M')}"
        if self.tipo == TIPO_GRUPO:
            return (f"Choque detectado el {self.dia}: El grupo ya tiene clase de {rango} "
                    f"en otro espacio.")
        return f"Choque detectado el {self.dia}: El salón ya está ocupado de {rango}."


def detectar_choques(dias, inicio, fin, id_espacio, existentes, id_grupo=None,
                     validar_grupo=True):
    """Busca choques de una asignación nueva contra los horarios ya guardados.

    dias        -- días que se quieren asignar, en el orden en que se reportarán
    inicio, fin -- rango horario de la clase nueva
    id_espacio  -- espacio donde se quiere poner la clase
    existentes  -- horarios ya guardados del MISMO periodo; cada uno es un dict con
                   'dia_semana', 'hora_inicio', 'hora_fin', 'id_espacio', 'id_grupo'
    id_grupo    -- grupo de la clase nueva (para detectar que el grupo esté en dos lugares)

    Devuelve una lista de Choque (vacía si no hay problema), como máximo uno por día
    y tipo, siguiendo el orden de `dias`.
    """
    inicio, fin = validar_rango(inicio, fin)
    choques = []
    for dia in dias:
        del_dia = [e for e in existentes if str(e['dia_semana']).strip() == dia]

        mismo_espacio = [e for e in del_dia if e['id_espacio'] == id_espacio]
        for e in buscar_traslapes(inicio, fin, mismo_espacio)[:1]:
            choques.append(Choque(TIPO_ESPACIO, dia, a_hora(e['hora_inicio']), a_hora(e['hora_fin'])))

        if validar_grupo and id_grupo is not None:
            mismo_grupo = [e for e in del_dia
                           if e['id_grupo'] == id_grupo and e['id_espacio'] != id_espacio]
            for e in buscar_traslapes(inicio, fin, mismo_grupo)[:1]:
                choques.append(Choque(TIPO_GRUPO, dia, a_hora(e['hora_inicio']), a_hora(e['hora_fin'])))
    return choques


def primer_choque(*args, **kwargs):
    choques = detectar_choques(*args, **kwargs)
    return choques[0] if choques else None