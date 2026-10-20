import logging
import math

from flask import Blueprint, render_template, request, redirect, url_for, flash

import config
from database.conexion import get_db
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
    
    # 1. Parámetros de paginación para las aulas (12 tarjetas por página)
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
    per_page = 12
    offset = (page - 1) * per_page

    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return render_template('gestion.html', edificios=[], aulas=[], page=1, total_pages=1)

    cursor = conn.cursor()
    
    # Edificios completos (sin paginación porque se muestran en su propia pestaña)
    cursor.execute("SELECT id_edificio, nombre, codigo, estatus FROM Edificios")
    edificios_db = cursor.fetchall()

    # Contar total de aulas para la paginación
    cursor.execute("SELECT COUNT(*) FROM Espacios")
    total_aulas_db = cursor.fetchone()[0] or 0
    total_pages = math.ceil(total_aulas_db / per_page) if total_aulas_db > 0 else 1

    # Aulas paginadas con OFFSET / FETCH NEXT
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
    
    return render_template('gestion.html', edificios=edificios, aulas=aulas, page=page, total_pages=total_pages)


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
    return redirect(url_for('gestion.vista_gestion', page=1))


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
    return redirect(url_for('gestion.vista_gestion'))


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
    return redirect(url_for('gestion.vista_gestion'))


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
    return redirect(url_for('gestion.vista_gestion'))