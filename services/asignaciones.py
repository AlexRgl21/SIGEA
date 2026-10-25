# Lógica de negocio de asignaciones, grupos y calendario

import logging
import math
import config
from . import conflictos
from .errores import ErrorNegocio

logger = logging.getLogger(__name__)


# Utilidades de validación
def _entero(valor, campo):
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ErrorNegocio(f"El campo '{campo}' no es válido.") from None


def _entero_opcional(valor):
    if valor is None or str(valor).strip() == '':
        return None
    return int(valor)


# Calendario
def construir_eventos(horarios_db):
    eventos = []
    for h in horarios_db:
        dia_num = config.DIA_A_NUMERO_CALENDARIO.get(str(h[1]).strip())
        if dia_num is None:
            continue
        acronimo = str(h[6]).strip() if h[6] else ''
        eventos.append({
            'title': h[0],
            'startTime': str(h[2])[:5],
            'endTime': str(h[3])[:5],
            'daysOfWeek': [dia_num],
            'color': config.COLORES_CARRERA.get(acronimo, config.COLOR_CARRERA_DEFAULT),
            'extendedProps': {'id_espacio': h[4]},
        })
    return eventos


def datos_vista(conn, page=1):
    # Todo lo que necesita la pantalla de asignaciones.
    cursor = conn.cursor()

    cursor.execute("SELECT id_carrera, nombre_carrera, acronimo FROM Carreras")
    carreras = cursor.fetchall()
    cols_carreras = [column[0] for column in cursor.description]
    carreras_list = [dict(zip(cols_carreras, row)) for row in carreras]

    # --- LÓGICA DE PAGINACIÓN PARA LA TABLA DE GRUPOS ---
    per_page = 10
    offset = (page - 1) * per_page

    cursor.execute("SELECT COUNT(*) FROM Grupos WHERE estatus = 'Activo'")
    total_grupos_db = cursor.fetchone()[0] or 0
    total_pages = math.ceil(total_grupos_db / per_page) if total_grupos_db > 0 else 1

    cursor.execute("""
        SELECT g.id_grupo, g.nombre_grupo, g.generacion_inicio, g.generacion_fin, c.acronimo, g.id_carrera
        FROM Grupos g
        INNER JOIN Carreras c ON g.id_carrera = c.id_carrera
        WHERE g.estatus = 'Activo'
        ORDER BY g.generacion_inicio DESC, g.nombre_grupo ASC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """, (offset, per_page))
    grupos_db = cursor.fetchall()
    cols_grupos = [column[0] for column in cursor.description]
    grupos_list = [dict(zip(cols_grupos, row)) for row in grupos_db]
    # ----------------------------------------------------

    cursor.execute("SELECT id_espacio, nombre, id_edificio FROM Espacios "
                   "WHERE estatus = 'Activo' AND tipo = ?", (config.TIPO_ESPACIO_AULA,))
    espacios = cursor.fetchall()
    cols_espacios = [column[0] for column in cursor.description]
    espacios_list = [dict(zip(cols_espacios, row)) for row in espacios]

    cursor.execute("SELECT id_periodo, nombre, fecha_inicio, fecha_fin FROM Periodos WHERE activo = 1 ORDER BY fecha_inicio")
    periodos = cursor.fetchall()
    cols_periodos = [column[0] for column in cursor.description]
    periodos_list = [dict(zip(cols_periodos, row)) for row in periodos]

    cursor.execute("""
        SELECT g.nombre_grupo, h.dia_semana, h.hora_inicio, h.hora_fin, a.id_espacio, e.id_edificio, c.acronimo
        FROM Horarios h
        JOIN Asignaciones a ON h.id_asignacion = a.id_asignacion
        JOIN Grupos g ON a.id_grupo = g.id_grupo
        JOIN Espacios e ON a.id_espacio = e.id_espacio
        JOIN Carreras c ON g.id_carrera = c.id_carrera
        JOIN Periodos p ON a.id_periodo = p.id_periodo
        WHERE p.activo = 1
    """)
    horarios_db = cursor.fetchall()

    cursor.execute("SELECT id_edificio, nombre FROM Edificios")
    edificios = cursor.fetchall()

    return dict(carreras=carreras_list, grupos=grupos_list, espacios=espacios_list, periodos=periodos_list,
                edificios=edificios, eventos_calendario=construir_eventos(horarios_db), 
                page=page, total_pages=total_pages)


# Asignación de horarios (usa el motor de conflictos)
def _horarios_existentes(cursor, id_periodo, id_espacio, id_grupo, dias):
    marcas = ','.join('?' * len(dias))
    cursor.execute(f"""
        SELECT a.id_grupo, a.id_espacio, h.dia_semana, h.hora_inicio, h.hora_fin
        FROM Horarios h WITH (UPDLOCK, HOLDLOCK)
        JOIN Asignaciones a ON h.id_asignacion = a.id_asignacion
        WHERE a.id_periodo = ?
          AND (a.id_espacio = ? OR a.id_grupo = ?)
          AND h.dia_semana IN ({marcas})
    """, (id_periodo, id_espacio, id_grupo, *dias))
    return [dict(id_grupo=f[0], id_espacio=f[1], dia_semana=f[2], hora_inicio=f[3], hora_fin=f[4])
            for f in cursor.fetchall()]


def validar_solicitud_asignacion(id_grupo, id_espacio, id_periodo, hora_inicio, hora_fin, dias):
    id_grupo = _entero(id_grupo, 'grupo')
    id_espacio = _entero(id_espacio, 'espacio')
    id_periodo = _entero(id_periodo, 'periodo')

    dias_limpios = []
    for d in dias or []:
        d = str(d).strip()
        if d not in config.DIAS_SEMANA:
            raise ErrorNegocio("Hay un día seleccionado que no es válido.")
        if d not in dias_limpios:
            dias_limpios.append(d)
    if not dias_limpios:
        raise ErrorNegocio("Selecciona al menos un día para la clase.")

    try:
        inicio, fin = conflictos.validar_rango(hora_inicio, hora_fin)
    except ValueError as e:
        raise ErrorNegocio(str(e)) from None
    return id_grupo, id_espacio, id_periodo, inicio, fin, dias_limpios


def crear_asignacion(conn, id_grupo, id_espacio, id_periodo, hora_inicio, hora_fin, dias):
    # Valida, revisa conflictos y guarda. Devuelve el id de la asignación nueva.
    id_grupo, id_espacio, id_periodo, inicio, fin, dias = validar_solicitud_asignacion(
        id_grupo, id_espacio, id_periodo, hora_inicio, hora_fin, dias)

    cursor = conn.cursor()
    try:
        existentes = _horarios_existentes(cursor, id_periodo, id_espacio, id_grupo, dias)
        choque = conflictos.primer_choque(
            dias, inicio, fin, id_espacio, existentes,
            id_grupo=id_grupo, validar_grupo=config.VALIDAR_CHOQUE_DE_GRUPO)
        if choque:
            conn.rollback()                       # libera los bloqueos
            raise ErrorNegocio(choque.mensaje())

        cursor.execute("""
            INSERT INTO Asignaciones (id_grupo, id_espacio, id_periodo)
            OUTPUT INSERTED.id_asignacion
            VALUES (?, ?, ?)
        """, (id_grupo, id_espacio, id_periodo))
        id_asignacion = cursor.fetchone()[0]

        for dia in dias:
            cursor.execute("""
                INSERT INTO Horarios (id_asignacion, dia_semana, hora_inicio, hora_fin)
                VALUES (?, ?, CAST(? AS TIME), CAST(? AS TIME))
            """, (id_asignacion, dia, inicio.strftime('%H:%M:%S'), fin.strftime('%H:%M:%S')))
        conn.commit()
        return id_asignacion
    except ErrorNegocio:
        raise
    except Exception:
        conn.rollback()
        raise


# Grupos
def _datos_grupo(nombre_grupo, generacion_inicio, generacion_fin, id_carrera):
    nombre = (nombre_grupo or '').strip()
    if not nombre:
        raise ErrorNegocio("El nombre del grupo es obligatorio.")
    try:
        return (nombre, int(generacion_inicio), _entero_opcional(generacion_fin), int(id_carrera))
    except (TypeError, ValueError):
        raise ErrorNegocio("La generación y la carrera deben ser números válidos.") from None


def agregar_grupo(conn, nombre_grupo, generacion_inicio, generacion_fin, id_carrera):
    # Crea el grupo, o reactiva uno eliminado con el mismo nombre.
    nombre, g_ini, g_fin, id_carrera = _datos_grupo(nombre_grupo, generacion_inicio,
                                                    generacion_fin, id_carrera)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id_grupo, estatus FROM Grupos WHERE nombre_grupo = ?", (nombre,))
        existente = cursor.fetchone()
        if existente:
            if existente[1] != 'Inactivo':
                raise ErrorNegocio(f"El grupo '{nombre}' ya existe y está activo. "
                                   "Por favor, elige otro nombre.")
            cursor.execute("""
                UPDATE Grupos
                SET estatus = 'Activo', generacion_inicio = ?, generacion_fin = ?, id_carrera = ?
                WHERE id_grupo = ?
            """, (g_ini, g_fin, id_carrera, existente[0]))
            conn.commit()
            return (f"El grupo '{nombre}' había sido eliminado previamente y fue reactivado "
                    "con los nuevos datos.")

        cursor.execute("""
            INSERT INTO Grupos (nombre_grupo, generacion_inicio, generacion_fin, id_carrera)
            VALUES (?, ?, ?, ?)
        """, (nombre, g_ini, g_fin, id_carrera))
        conn.commit()
        return "Grupo registrado exitosamente."
    except ErrorNegocio:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise


def desactivar_grupo(conn, id_grupo):
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Grupos SET estatus = 'Inactivo' WHERE id_grupo = ?", (id_grupo,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def actualizar_grupo(conn, id_grupo, nombre_grupo, generacion_inicio, generacion_fin, id_carrera):
    nombre, g_ini, g_fin, id_carrera = _datos_grupo(nombre_grupo, generacion_inicio,
                                                    generacion_fin, id_carrera)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id_grupo FROM Grupos WHERE nombre_grupo = ? AND id_grupo != ?",
                       (nombre, id_grupo))
        if cursor.fetchone():
            raise ErrorNegocio(f"El grupo '{nombre}' ya existe. Por favor, elige otro nombre.")
        cursor.execute("""
            UPDATE Grupos
            SET nombre_grupo = ?, generacion_inicio = ?, generacion_fin = ?, id_carrera = ?
            WHERE id_grupo = ?
        """, (nombre, g_ini, g_fin, id_carrera, id_grupo))
        conn.commit()
    except ErrorNegocio:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise