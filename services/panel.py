# Cálculo de los indicadores del panel principal
import math
from datetime import datetime

import config


def nombre_dia(fecha):
    return config.DIAS_SEMANA[fecha.weekday()]


def _hhmm(valor):
    return str(valor)[:5]


def armar_tabla_disponibilidad(espacios, clases_ahora, clases_proximas):
    tabla = []
    for id_espacio, nombre_espacio, nombre_edificio in espacios:
        info = {'grupo': '-', 'horario': '-', 'estatus': 'Libre', 'badge_class': 'badge-disponible'}
        if id_espacio in clases_ahora:
            info.update(clases_ahora[id_espacio], estatus='Ocupado', badge_class='badge-ocupado')
        elif id_espacio in clases_proximas:
            info.update(clases_proximas[id_espacio], estatus='Próximo', badge_class='badge-proximo')
        tabla.append({'edificio': nombre_edificio, 'espacio': nombre_espacio, **info})
    return tabla


def calcular_panel(conn, page=1, q='', estado='todos', ahora=None):
    ahora = ahora or datetime.now()
    hora_actual = ahora.strftime('%H:%M:%S')
    hoy = ahora.date()
    dia_hoy = nombre_dia(hoy)
    cursor = conn.cursor()

    # Parámetros de paginación (10 registros por página)
    per_page = 10

    cursor.execute("""
        SELECT COUNT(*),
               SUM(CASE WHEN estatus = 'Mantenimiento' THEN 1 ELSE 0 END)
        FROM Espacios
    """)
    fila = cursor.fetchone()
    total_espacios = fila[0] or 0
    bloqueados = fila[1] or 0

    cursor.execute("""
        SELECT COUNT(DISTINCT a.id_espacio)
        FROM Asignaciones a
        JOIN Horarios h ON a.id_asignacion = h.id_asignacion
        WHERE h.dia_semana = ?
          AND h.hora_inicio <= CAST(? AS TIME)
          AND h.hora_fin > CAST(? AS TIME)
    """, (dia_hoy, hora_actual, hora_actual))
    ocupados_por_clase = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COUNT(DISTINCT id_espacio)
        FROM Reservas
        WHERE fecha = ? AND estado = 'Aprobada'
          AND hora_inicio <= CAST(? AS TIME)
          AND hora_fin > CAST(? AS TIME)
    """, (hoy, hora_actual, hora_actual))
    ocupados_por_reserva = cursor.fetchone()[0] or 0

    ocupados = ocupados_por_clase + ocupados_por_reserva
    libres = max(0, total_espacios - bloqueados - ocupados)

    cursor.execute("""
        SELECT ed.nombre AS edificio, e.nombre AS espacio, r.hora_inicio, r.hora_fin
        FROM Reservas r
        JOIN Espacios e ON r.id_espacio = e.id_espacio
        JOIN Edificios ed ON e.id_edificio = ed.id_edificio
        WHERE r.fecha = ? AND r.estado = 'Aprobada'
        ORDER BY r.hora_inicio ASC
    """, (hoy,))
    reservas_hoy = cursor.fetchall()

    cursor.execute("""
        SELECT ed.nombre AS nombre_edificio,
               COUNT(DISTINCT es.id_espacio) AS total_espacios,
               COUNT(DISTINCT CASE WHEN h.dia_semana = ? THEN a.id_espacio END) AS espacios_ocupados_hoy
        FROM Edificios ed
        LEFT JOIN Espacios es ON ed.id_edificio = es.id_edificio AND es.estatus = 'Activo'
        LEFT JOIN Asignaciones a ON es.id_espacio = a.id_espacio
        LEFT JOIN Horarios h ON a.id_asignacion = h.id_asignacion
        GROUP BY ed.nombre
        HAVING COUNT(DISTINCT CASE WHEN h.dia_semana = ? THEN a.id_espacio END) > 0
    """, (dia_hoy, dia_hoy))
    datos_grafica = [{'edificio': f[0],
                      'porcentaje': int((f[2] / f[1] * 100) if f[1] > 0 else 0)}
                     for f in cursor.fetchall()]

    # --- TABLA DE DISPONIBILIDAD CON FILTROS Y PAGINACIÓN ---
    cursor.execute("""
        SELECT e.id_espacio, e.nombre AS espacio, ed.nombre AS edificio
        FROM Espacios e
        JOIN Edificios ed ON e.id_edificio = ed.id_edificio
        WHERE e.estatus = 'Activo' AND e.nombre LIKE 'Salón%'
        ORDER BY ed.nombre, CAST(SUBSTRING(e.nombre, 7, LEN(e.nombre)) AS INT)
    """)
    todos_espacios = [tuple(f) for f in cursor.fetchall()]

    cursor.execute("""
        SELECT a.id_espacio, g.nombre_grupo, h.hora_inicio, h.hora_fin
        FROM Asignaciones a
        JOIN Horarios h ON a.id_asignacion = h.id_asignacion
        JOIN Grupos g ON a.id_grupo = g.id_grupo
        WHERE h.dia_semana = ?
          AND h.hora_inicio <= CAST(? AS TIME)
          AND h.hora_fin > CAST(? AS TIME)
    """, (dia_hoy, hora_actual, hora_actual))
    clases_ahora = {f[0]: {'grupo': f[1], 'horario': f"{_hhmm(f[2])} - {_hhmm(f[3])}"}
                    for f in cursor.fetchall()}

    cursor.execute("""
        SELECT a.id_espacio, g.nombre_grupo, h.hora_inicio, h.hora_fin
        FROM Asignaciones a
        JOIN Horarios h ON a.id_asignacion = h.id_asignacion
        JOIN Grupos g ON a.id_grupo = g.id_grupo
        WHERE h.dia_semana = ? AND h.hora_inicio > CAST(? AS TIME)
        ORDER BY h.hora_inicio ASC
    """, (dia_hoy, hora_actual))
    clases_proximas = {}
    for f in cursor.fetchall():
        clases_proximas.setdefault(
            f[0], {'grupo': f[1], 'horario': f"{_hhmm(f[2])} - {_hhmm(f[3])}"})

    tabla_completa = armar_tabla_disponibilidad(todos_espacios, clases_ahora, clases_proximas)

    # Aplicamos filtros de estatus y búsqueda antes de paginar
    q_low = (q or '').strip().lower()
    estado_low = (estado or 'todos').strip().lower()

    tabla_filtrada = []
    for item in tabla_completa:
        coincide_q = (not q_low
                      or q_low in item['grupo'].lower()
                      or q_low in item['espacio'].lower()
                      or q_low in item['edificio'].lower())
        coincide_estado = (estado_low == 'todos'
                           or estado_low in item['estatus'].lower())
        if coincide_q and coincide_estado:
            tabla_filtrada.append(item)

    total_filas = len(tabla_filtrada)
    total_pages = math.ceil(total_filas / per_page) if total_filas > 0 else 1
    if page > total_pages:
        page = total_pages
    offset = (page - 1) * per_page
    tabla_paginada = tabla_filtrada[offset:offset + per_page]

    return dict(
        total_espacios=total_espacios, bloqueados=bloqueados, reservas_hoy=reservas_hoy,
        datos_grafica=datos_grafica, dia_hoy=dia_hoy, ocupados=ocupados, libres=libres,
        tabla_disponibilidad=tabla_paginada,
        page=page, total_pages=total_pages, q=q, estado=estado
    )