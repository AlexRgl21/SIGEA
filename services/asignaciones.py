import logging
import config

from . import conflictos
from .errores import ErrorNegocio

logger = logging.getLogger(__name__)


def _entero(valor, campo):
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ErrorNegocio(
            f"El campo '{campo}' no es válido."
        ) from None


def _entero_opcional(valor):
    if valor is None or str(valor).strip() == '':
        return None
    return int(valor)


# Calendario
def construir_eventos(horarios_db):
    eventos = []

    for h in horarios_db:
        dia_num = config.DIA_A_NUMERO_CALENDARIO.get(
            str(h[1]).strip()
        )

        if dia_num is None:
            continue

        acronimo = str(h[6]).strip() if h[6] else ''

        eventos.append({
            'title': h[0],
            'startTime': str(h[2])[:5],
            'endTime': str(h[3])[:5],
            'daysOfWeek': [dia_num],
            'color': config.COLORES_CARRERA.get(
                acronimo,
                config.COLOR_CARRERA_DEFAULT
            ),
            'extendedProps': {
                'id_espacio': h[4]
            },
        })

    return eventos


def datos_vista(conn, page=1):
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id_carrera,
            nombre_carrera,
            acronimo
        FROM Carreras
    """)

    carreras = cursor.fetchall()
    cols_carreras = [
        column.name for column in cursor.description
    ]

    carreras_list = [
        dict(zip(cols_carreras, row))
        for row in carreras
    ]

    cursor.execute("""
        SELECT
            g.id_grupo,
            g.nombre_grupo,
            g.generacion_inicio,
            g.generacion_fin,
            c.acronimo,
            g.id_carrera
        FROM Grupos g
        INNER JOIN Carreras c
            ON g.id_carrera = c.id_carrera
        WHERE g.estatus = 'Activo'
        ORDER BY
            g.generacion_inicio DESC,
            g.nombre_grupo ASC
    """)

    grupos_db = cursor.fetchall()
    cols_grupos = [
        column.name for column in cursor.description
    ]

    grupos_list = [
        dict(zip(cols_grupos, row))
        for row in grupos_db
    ]

    cursor.execute("""
        SELECT
            id_espacio,
            nombre,
            id_edificio
        FROM Espacios
        WHERE estatus = 'Activo'
          AND tipo = %s
    """, (config.TIPO_ESPACIO_AULA,))

    espacios = cursor.fetchall()
    cols_espacios = [
        column.name for column in cursor.description
    ]

    espacios_list = [
        dict(zip(cols_espacios, row))
        for row in espacios
    ]

    cursor.execute("""
        SELECT
            id_periodo,
            nombre,
            fecha_inicio,
            fecha_fin
        FROM Periodos
        WHERE activo = TRUE
        ORDER BY fecha_inicio
    """)

    periodos = cursor.fetchall()
    cols_periodos = [
        column.name for column in cursor.description
    ]

    periodos_list = [
        dict(zip(cols_periodos, row))
        for row in periodos
    ]

    cursor.execute("""
        SELECT
            g.nombre_grupo,
            h.dia_semana,
            h.hora_inicio,
            h.hora_fin,
            a.id_espacio,
            e.id_edificio,
            c.acronimo
        FROM Horarios h
        JOIN Asignaciones a
            ON h.id_asignacion = a.id_asignacion
        JOIN Grupos g
            ON a.id_grupo = g.id_grupo
        JOIN Espacios e
            ON a.id_espacio = e.id_espacio
        JOIN Carreras c
            ON g.id_carrera = c.id_carrera
        JOIN Periodos p
            ON a.id_periodo = p.id_periodo
        WHERE p.activo = TRUE
    """)

    horarios_db = cursor.fetchall()

    cursor.execute("""
        SELECT id_edificio, nombre
        FROM Edificios
    """)

    edificios = cursor.fetchall()

    return dict(
        carreras=carreras_list,
        grupos=grupos_list,
        espacios=espacios_list,
        periodos=periodos_list,
        edificios=edificios,
        eventos_calendario=construir_eventos(horarios_db),
        page=1,
        total_pages=1
    )


def _horarios_existentes(
    cursor,
    id_periodo,
    id_espacio,
    id_grupo,
    dias
):
    marcas = ','.join(['%s'] * len(dias))

    cursor.execute(f"""
        SELECT
            a.id_grupo,
            a.id_espacio,
            h.dia_semana,
            h.hora_inicio,
            h.hora_fin
        FROM Horarios h
        JOIN Asignaciones a
            ON h.id_asignacion = a.id_asignacion
        WHERE a.id_periodo = %s
          AND (
              a.id_espacio = %s
              OR a.id_grupo = %s
          )
          AND h.dia_semana IN ({marcas})
    """, (
        id_periodo,
        id_espacio,
        id_grupo,
        *dias
    ))

    return [
        dict(
            id_grupo=f[0],
            id_espacio=f[1],
            dia_semana=f[2],
            hora_inicio=f[3],
            hora_fin=f[4]
        )
        for f in cursor.fetchall()
    ]


def _verificar_reservas_aprobadas(cursor, id_espacio, periodo_inicio, periodo_fin, inicio, fin, dias):
    """(AUD-007) Verifica si un nuevo horario de clases choca con una reserva que ya había sido aprobada."""
    marcas = ','.join(['%s'] * len(dias))
    
    cursor.execute(f"""
        SELECT r.fecha, r.hora_inicio, r.hora_fin
        FROM Reservas r
        WHERE r.id_espacio = %s
          AND r.estado = 'Aprobada'
          AND r.fecha >= %s
          AND r.fecha <= %s
          -- En PostgreSQL, extract(isodow) retorna 1=Lunes, 7=Domingo
          AND (
            CASE extract(isodow from r.fecha)
                WHEN 1 THEN 'Lunes'
                WHEN 2 THEN 'Martes'
                WHEN 3 THEN 'Miércoles'
                WHEN 4 THEN 'Jueves'
                WHEN 5 THEN 'Viernes'
                WHEN 6 THEN 'Sábado'
                WHEN 7 THEN 'Domingo'
            END
          ) IN ({marcas})
    """, (id_espacio, periodo_inicio, periodo_fin, *dias))

    reservas_existentes = [
        dict(hora_inicio=f[1], hora_fin=f[2], fecha=f[0])
        for f in cursor.fetchall()
    ]

    for reserva in reservas_existentes:
        if conflictos.hay_traslape(inicio, fin, reserva['hora_inicio'], reserva['hora_fin']):
            raise ErrorNegocio(
                f"Choque cruzado detectado: El espacio ya tiene una reserva aprobada el {reserva['fecha']} "
                f"de {reserva['hora_inicio']} a {reserva['hora_fin']}."
            )


def validar_solicitud_asignacion(
    id_grupo,
    id_espacio,
    id_periodo,
    hora_inicio,
    hora_fin,
    dias
):
    id_grupo = _entero(id_grupo, 'grupo')
    id_espacio = _entero(id_espacio, 'espacio')
    id_periodo = _entero(id_periodo, 'periodo')

    dias_limpios = []

    for d in dias or []:
        d = str(d).strip()

        if d not in config.DIAS_SEMANA:
            raise ErrorNegocio(
                "Hay un día seleccionado que no es válido."
            )

        if d not in dias_limpios:
            dias_limpios.append(d)

    if not dias_limpios:
        raise ErrorNegocio(
            "Selecciona al menos un día para la clase."
        )

    try:
        inicio, fin = conflictos.validar_rango(
            hora_inicio,
            hora_fin
        )
    except ValueError as e:
        raise ErrorNegocio(str(e)) from None

    return (
        id_grupo,
        id_espacio,
        id_periodo,
        inicio,
        fin,
        dias_limpios
    )


def crear_asignacion(
    conn,
    id_grupo,
    id_espacio,
    id_periodo,
    hora_inicio,
    hora_fin,
    dias
):
    (
        id_grupo,
        id_espacio,
        id_periodo,
        inicio,
        fin,
        dias
    ) = validar_solicitud_asignacion(
        id_grupo,
        id_espacio,
        id_periodo,
        hora_inicio,
        hora_fin,
        dias
    )

    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT fecha_inicio, fecha_fin
            FROM Periodos
            WHERE id_periodo = %s
              AND activo = TRUE
              AND fecha_fin >= CURRENT_DATE
            FOR UPDATE
        """, (id_periodo,))

        fila_periodo = cursor.fetchone()

        if not fila_periodo:
            raise ErrorNegocio(
                "El periodo no está activo o ya terminó."
            )
        
        p_inicio, p_fin = fila_periodo[0], fila_periodo[1]

        cursor.execute("""
            SELECT 1
            FROM Grupos
            WHERE id_grupo = %s
              AND estatus = 'Activo'
            FOR UPDATE
        """, (id_grupo,))

        if not cursor.fetchone():
            raise ErrorNegocio(
                "El grupo no está activo."
            )

        cursor.execute("""
            SELECT 1
            FROM Espacios
            WHERE id_espacio = %s
              AND estatus = 'Activo'
              AND tipo = %s
            FOR UPDATE
        """, (
            id_espacio,
            config.TIPO_ESPACIO_AULA
        ))

        if not cursor.fetchone():
            raise ErrorNegocio(
                "El espacio no está activo o no es un aula."
            )

        # 1. Verificamos choques entre las clases normales
        existentes = _horarios_existentes(
            cursor,
            id_periodo,
            id_espacio,
            id_grupo,
            dias
        )

        choque = conflictos.primer_choque(
            dias,
            inicio,
            fin,
            id_espacio,
            existentes,
            id_grupo=id_grupo,
            validar_grupo=config.VALIDAR_CHOQUE_DE_GRUPO
        )

        if choque:
            raise ErrorNegocio(
                choque.mensaje()
            )
        
        # 2. Verificamos choques cruzados contra reservas ya aprobadas (AUD-007)
        _verificar_reservas_aprobadas(
            cursor, id_espacio, p_inicio, p_fin, inicio, fin, dias
        )

        cursor.execute("""
            INSERT INTO Asignaciones (
                id_grupo,
                id_espacio,
                id_periodo
            )
            VALUES (%s, %s, %s)
            RETURNING id_asignacion
        """, (
            id_grupo,
            id_espacio,
            id_periodo
        ))

        id_asignacion = cursor.fetchone()[0]

        for dia in dias:
            cursor.execute("""
                INSERT INTO Horarios (
                    id_asignacion,
                    dia_semana,
                    hora_inicio,
                    hora_fin
                )
                VALUES (
                    %s,
                    %s,
                    CAST(%s AS TIME),
                    CAST(%s AS TIME)
                )
            """, (
                id_asignacion,
                dia,
                inicio.strftime('%H:%M:%S'),
                fin.strftime('%H:%M:%S')
            ))

        conn.commit()
        return id_asignacion

    except Exception:
        conn.rollback()
        raise


# Catálogo de grupos
def _datos_grupo(
    nombre_grupo,
    generacion_inicio,
    generacion_fin,
    id_carrera
):
    nombre = (nombre_grupo or '').strip()

    if not nombre:
        raise ErrorNegocio(
            "El nombre del grupo es obligatorio."
        )

    try:
        return (
            nombre,
            int(generacion_inicio),
            _entero_opcional(generacion_fin),
            int(id_carrera)
        )
    except (TypeError, ValueError):
        raise ErrorNegocio(
            "La generación y la carrera deben ser números válidos."
        ) from None


def agregar_grupo(
    conn,
    nombre_grupo,
    generacion_inicio,
    generacion_fin,
    id_carrera
):
    nombre, g_ini, g_fin, id_carrera = _datos_grupo(
        nombre_grupo,
        generacion_inicio,
        generacion_fin,
        id_carrera
    )

    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id_grupo, estatus
            FROM Grupos
            WHERE nombre_grupo = %s
        """, (nombre,))

        existente = cursor.fetchone()

        if existente:
            if existente[1] != 'Inactivo':
                raise ErrorNegocio(
                    f"El grupo '{nombre}' ya existe y está activo. "
                    "Por favor, elige otro nombre."
                )

            cursor.execute("""
                UPDATE Grupos
                SET estatus = 'Activo',
                    generacion_inicio = %s,
                    generacion_fin = %s,
                    id_carrera = %s
                WHERE id_grupo = %s
            """, (
                g_ini,
                g_fin,
                id_carrera,
                existente[0]
            ))

            conn.commit()

            return (
                f"El grupo '{nombre}' había sido eliminado "
                "previamente y fue reactivado con los nuevos datos."
            )

        cursor.execute("""
            INSERT INTO Grupos (
                nombre_grupo,
                generacion_inicio,
                generacion_fin,
                id_carrera
            )
            VALUES (%s, %s, %s, %s)
        """, (
            nombre,
            g_ini,
            g_fin,
            id_carrera
        ))

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
        cursor.execute("""
            UPDATE Grupos
            SET estatus = 'Inactivo'
            WHERE id_grupo = %s
        """, (id_grupo,))

        # Solución AUD-014: Validar si realmente se afectó algún registro (evitar falsos positivos)
        if cursor.rowcount == 0:
            raise ErrorNegocio(
                "No se pudo desactivar: El grupo no existe."
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise


def actualizar_grupo(
    conn,
    id_grupo,
    nombre_grupo,
    generacion_inicio,
    generacion_fin,
    id_carrera
):
    nombre, g_ini, g_fin, id_carrera = _datos_grupo(
        nombre_grupo,
        generacion_inicio,
        generacion_fin,
        id_carrera
    )

    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id_grupo
            FROM Grupos
            WHERE nombre_grupo = %s
              AND id_grupo != %s
        """, (
            nombre,
            id_grupo
        ))

        if cursor.fetchone():
            raise ErrorNegocio(
                f"El grupo '{nombre}' ya existe. "
                "Por favor, elige otro nombre."
            )

        cursor.execute("""
            UPDATE Grupos
            SET nombre_grupo = %s,
                generacion_inicio = %s,
                generacion_fin = %s,
                id_carrera = %s
            WHERE id_grupo = %s
        """, (
            nombre,
            g_ini,
            g_fin,
            id_carrera,
            id_grupo
        ))

        conn.commit()

    except ErrorNegocio:
        conn.rollback()
        raise

    except Exception:
        conn.rollback()
        raise