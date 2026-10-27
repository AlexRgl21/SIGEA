import logging
import math

from flask import Blueprint, render_template, request, redirect, url_for, flash

import config
from database.conexion import get_db
from services import periodos as servicio_periodos
from services.errores import ErrorNegocio
from .decoradores import role_required

gestion_bp = Blueprint('gestion', __name__)
logger = logging.getLogger(__name__)


def _color_edificio(codigo):
    return config.COLORES_EDIFICIOS.get(str(codigo).strip(), config.COLOR_EDIFICIO_DEFAULT)


def _ejecutar(conn, sql, parametros, ok, error_log, error_msg):
    try:
        conn.cursor().execute(sql, parametros)
        conn.commit()
        flash(ok, "success")
    except Exception:
        conn.rollback()
        logger.exception(error_log)
        flash(error_msg, "danger")


# VISTA PRINCIPAL: AULAS Y EDIFICIOS
@gestion_bp.route('/gestion')
@role_required(config.ROL_ADMIN)
def vista_gestion():
    conn = get_db()
    
    # 1. Parámetros de paginación y filtro para las aulas (12 tarjetas por página)
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
    q = (request.args.get('q') or '').strip()
    per_page = 12

    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return render_template('gestion.html', edificios=[], aulas=[], periodos=[], page=1, total_pages=1, q='')

    cursor = conn.cursor()
    
    # Edificios completos (sin paginación porque se muestran en su propia pestaña)
    cursor.execute("SELECT id_edificio, nombre, codigo, estatus FROM Edificios")
    edificios_db = cursor.fetchall()

    # Contar y obtener aulas (filtradas por búsqueda si existe `q`)
    if q:
        like_param = f"%{q}%"
        cursor.execute("""
            SELECT COUNT(*)
            FROM Espacios e
            INNER JOIN Edificios ed ON e.id_edificio = ed.id_edificio
            WHERE e.nombre LIKE ? OR e.tipo LIKE ? OR e.estatus LIKE ? OR ed.codigo LIKE ? OR ed.nombre LIKE ?
        """, (like_param, like_param, like_param, like_param, like_param))
        total_aulas_db = cursor.fetchone()[0] or 0
        total_pages = math.ceil(total_aulas_db / per_page) if total_aulas_db > 0 else 1
        if page > total_pages:
            page = total_pages
        offset = (page - 1) * per_page

        cursor.execute("""
            SELECT e.id_espacio, e.nombre, e.capacidad, e.tipo, e.estatus, ed.codigo
            FROM Espacios e
            INNER JOIN Edificios ed ON e.id_edificio = ed.id_edificio
            WHERE e.nombre LIKE ? OR e.tipo LIKE ? OR e.estatus LIKE ? OR ed.codigo LIKE ? OR ed.nombre LIKE ?
            ORDER BY e.id_espacio ASC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """, (like_param, like_param, like_param, like_param, like_param, offset, per_page))
    else:
        cursor.execute("SELECT COUNT(*) FROM Espacios")
        total_aulas_db = cursor.fetchone()[0] or 0
        total_pages = math.ceil(total_aulas_db / per_page) if total_aulas_db > 0 else 1
        if page > total_pages:
            page = total_pages
        offset = (page - 1) * per_page

        cursor.execute("""
            SELECT e.id_espacio, e.nombre, e.capacidad, e.tipo, e.estatus, ed.codigo
            FROM Espacios e
            INNER JOIN Edificios ed ON e.id_edificio = ed.id_edificio
            ORDER BY e.id_espacio ASC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """, (offset, per_page))

    aulas_db = cursor.fetchall()

    edificios = [tuple(ed) + (_color_edificio(ed[2]),) for ed in edificios_db]
    aulas = [tuple(au) + (_color_edificio(au[5]),) for au in aulas_db]
    
    servicio_periodos.cerrar_vencidos_seguro(conn)      # que la lista nunca muestre un periodo vencido como activo
    periodos = servicio_periodos.listar(conn)

    return render_template('gestion.html', edificios=edificios, aulas=aulas, periodos=periodos,
                           page=page, total_pages=total_pages, q=q)


@gestion_bp.route('/gestion/agregar_espacio', methods=['POST'])
@role_required(config.ROL_ADMIN)
def agregar_espacio():
    conn = get_db()
    if not conn:
        flash("Error de conexión en la base de datos.", "danger")
        return redirect(url_for('gestion.vista_gestion'))
    _ejecutar(conn,
              "INSERT INTO Espacios (nombre, capacidad, tipo, id_edificio) VALUES (?, ?, ?, ?)",
              (request.form.get('nombre'), request.form.get('capacidad'),
               request.form.get('tipo'), request.form.get('id_edificio')),
              "Espacio agregado exitosamente al catálogo.",
              "Error al agregar el espacio",
              "Error al agregar el espacio. Inténtalo de nuevo o avisa al administrador.")
    return redirect(url_for('gestion.vista_gestion', page=1, _anchor='vista-aulas'))


@gestion_bp.route('/gestion/editar_edificio', methods=['POST'])
@role_required(config.ROL_ADMIN)
def editar_edificio():
    id_edificio = request.form['id_edificio']
    nombre = request.form['nombre']
    codigo = request.form['codigo']
    estatus = request.form['estatus']

    conn = get_db()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for('gestion.vista_gestion'))
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE Edificios SET nombre = ?, codigo = ?, estatus = ? WHERE id_edificio = ?",
                       (nombre, codigo, estatus, id_edificio))
        # El estatus del edificio se propaga a todos sus espacios
        cursor.execute("UPDATE Espacios SET estatus = ? WHERE id_edificio = ?", (estatus, id_edificio))
        conn.commit()
        flash("Edificio y sus espacios actualizados correctamente.", "success")
    except Exception:
        conn.rollback()
        logger.exception("Error al actualizar el edificio")
        flash("Error al actualizar el edificio. Inténtalo de nuevo o avisa al administrador.", "danger")
    return redirect(url_for('gestion.vista_gestion', _anchor='vista-edificios'))


@gestion_bp.route('/gestion/editar_espacio', methods=['POST'])
@role_required(config.ROL_ADMIN)
def editar_espacio():
    conn = get_db()
    if not conn:
        flash("Error de conexión en la base de datos.", "danger")
        return redirect(url_for('gestion.vista_gestion'))
    f = request.form
    _ejecutar(conn,
            "UPDATE Espacios SET nombre = ?, capacidad = ?, tipo = ?, estatus = ?, id_edificio = ? "
            "WHERE id_espacio = ?",
            (f['nombre'], f['capacidad'], f['tipo'], f['estatus'], f['id_edificio'], f['id_espacio']),
            "Información del espacio modificada con éxito.",
            "Error al actualizar el espacio",
            "Error al actualizar el espacio. Inténtalo de nuevo o avisa al administrador.")
    return redirect(url_for('gestion.vista_gestion', _anchor='vista-aulas'))


@gestion_bp.route('/gestion/eliminar_espacio/<int:id>', methods=['POST'])
@role_required(config.ROL_ADMIN)
def eliminar_espacio(id):
    conn = get_db()
    if not conn:
        flash("Error de conexión en la base de datos.", "danger")
        return redirect(url_for('gestion.vista_gestion'))
    _ejecutar(conn, "DELETE FROM Espacios WHERE id_espacio = ?", (id,),
            "El espacio fue eliminado del sistema.",
            "Error al eliminar el espacio",
            "Error al eliminar el espacio. Inténtalo de nuevo o avisa al administrador.")
    return redirect(url_for('gestion.vista_gestion', _anchor='vista-aulas'))


# PERIODOS (CUATRIMESTRES)
def _volver_a_periodos():
    return redirect(url_for('gestion.vista_gestion', _anchor='vista-periodos'))


@gestion_bp.route('/gestion/periodos/crear', methods=['POST'])
@role_required(config.ROL_ADMIN)
def crear_periodo():
    conn = get_db()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return _volver_a_periodos()
    f = request.form
    try:
        servicio_periodos.crear_periodo(conn, f.get('nombre'), f.get('fecha_inicio'), f.get('fecha_fin'))
        flash("Periodo creado. Se inactivará solo al pasar su fecha de fin.", "success")
    except ErrorNegocio as e:
        flash(e.mensaje, "danger")
    except Exception:
        logger.exception("Error al crear el periodo")
        flash("Error al crear el periodo. Inténtalo de nuevo o avisa al administrador.", "danger")
    return _volver_a_periodos()


@gestion_bp.route('/gestion/periodos/editar', methods=['POST'])
@role_required(config.ROL_ADMIN)
def editar_periodo():
    conn = get_db()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return _volver_a_periodos()
    f = request.form
    try:
        servicio_periodos.actualizar_periodo(conn, f.get('id_periodo', type=int), f.get('nombre'),
                                             f.get('fecha_inicio'), f.get('fecha_fin'))
        flash("Periodo actualizado correctamente.", "success")
    except ErrorNegocio as e:
        flash(e.mensaje, "danger")
    except Exception:
        logger.exception("Error al actualizar el periodo")
        flash("Error al actualizar el periodo. Inténtalo de nuevo o avisa al administrador.", "danger")
    return _volver_a_periodos()


@gestion_bp.route('/gestion/periodos/finalizar/<int:id_periodo>', methods=['POST'])
@role_required(config.ROL_ADMIN)
def finalizar_periodo(id_periodo):
    conn = get_db()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return _volver_a_periodos()
    try:
        nombre, borradas = servicio_periodos.finalizar_periodo(conn, id_periodo)
        flash(f"Periodo '{nombre}' finalizado. Se borraron {borradas} asignaciones.", "success")
    except ErrorNegocio as e:
        flash(e.mensaje, "warning")
    except Exception:
        logger.exception("Error al finalizar el periodo")
        flash("Error al finalizar el periodo. Inténtalo de nuevo o avisa al administrador.", "danger")
    return _volver_a_periodos()