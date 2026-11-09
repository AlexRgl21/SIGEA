
import logging
import secrets
import string

import psycopg
from werkzeug.security import generate_password_hash

import config
from . import correo
from .errores import ErrorNegocio

logger = logging.getLogger(__name__)


def correo_institucional(direccion, dominio=None):
    dominio = dominio or config.DOMINIO_CORREO

    partes = (
        direccion or ''
    ).strip().lower().split('@')

    return (
        len(partes) == 2
        and partes[0] != ''
        and partes[1] == dominio
    )


def generar_password_temporal(longitud=8):
    alfabeto = string.ascii_letters + string.digits

    return ''.join(
        secrets.choice(alfabeto)
        for _ in range(longitud)
    )


def listar(conn, page=1):
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id_usuario,
            nombre,
            apellidos,
            nombre || ' ' || apellidos AS nombre_completo,
            correo,
            estado,
            id_rol
        FROM Usuarios
        WHERE id_rol <> %s
        ORDER BY id_usuario ASC
    """, (config.ID_ROL_SOPORTE,))

    columnas = [
        c.name for c in cursor.description
    ]

    usuarios = [
        dict(zip(columnas, fila))
        for fila in cursor.fetchall()
    ]

    for u in usuarios:
        u['rol_nombre'] = config.NOMBRES_ROL.get(
            u['id_rol']
        )

    return dict(
        usuarios=usuarios,
        page=1,
        total_pages=1
    )


def puede_gestionar(conn, rol_actor, id_objetivo):
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id_rol
        FROM Usuarios
        WHERE id_usuario = %s
    """, (id_objetivo,))

    fila = cursor.fetchone()

    if not fila or fila[0] == config.ID_ROL_SOPORTE:
        return False

    if rol_actor == config.ROL_ADMIN:
        return True

    return fila[0] == config.ID_ROL_MAESTRO


def _rol_permitido(rol_actor, id_rol):
    if rol_actor != config.ROL_ADMIN:
        return config.ID_ROL_MAESTRO

    try:
        id_rol = int(id_rol)
    except (TypeError, ValueError):
        raise ErrorNegocio(
            "El rol seleccionado no es válido."
        ) from None

    if (
        id_rol not in config.ROLES_POR_ID
        or id_rol == config.ID_ROL_SOPORTE
    ):
        raise ErrorNegocio(
            "El rol seleccionado no es válido."
        )

    return id_rol


def configurar(
    conn,
    rol_actor,
    id_objetivo,
    id_rol,
    estado
):
    if estado not in ('Activo', 'Inactivo'):
        raise ErrorNegocio(
            "Los datos del formulario no son válidos. "
            "Recarga la página e inténtalo de nuevo."
        )

    if (
        rol_actor != config.ROL_ADMIN
        and str(id_rol) in ('1', '2')
    ):
        raise ErrorNegocio(
            "Alerta de seguridad: No tienes permisos "
            "para asignar este rol."
        )

    id_rol = _rol_permitido(
        rol_actor,
        id_rol
    )

    if not puede_gestionar(
        conn,
        rol_actor,
        id_objetivo
    ):
        raise ErrorNegocio(
            "No tienes permisos para modificar a este usuario."
        )

    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE Usuarios
            SET id_rol = %s,
                estado = %s
            WHERE id_usuario = %s
        """, (
            id_rol,
            estado,
            id_objetivo
        ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise


def crear(
    conn,
    rol_actor,
    nombre,
    apellidos,
    correo_usuario,
    id_rol
):
    correo_usuario = (
        correo_usuario or ''
    ).strip().lower()

    if not correo_institucional(correo_usuario):
        raise ErrorNegocio(
            f"Correo inválido. Solo se permiten "
            f"correos @{config.DOMINIO_CORREO}."
        )

    id_rol = _rol_permitido(
        rol_actor,
        id_rol
    )

    password_temporal = generar_password_temporal()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO Usuarios (
                nombre,
                apellidos,
                correo,
                contrasena,
                id_rol,
                estado
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                'Activo'
            )
        """, (
            nombre,
            apellidos,
            correo_usuario,
            generate_password_hash(password_temporal),
            id_rol
        ))

        conn.commit()

    except psycopg.IntegrityError:
        conn.rollback()
        raise ErrorNegocio(
            "No se pudo registrar: el correo ya está "
            "registrado o algún dato no es válido."
        ) from None

    except Exception:
        conn.rollback()
        raise

    correo.correo_bienvenida(
        correo_usuario,
        nombre,
        password_temporal
    )


def editar(
    conn,
    rol_actor,
    id_objetivo,
    nombre,
    apellidos,
    correo_usuario
):
    correo_usuario = (
        correo_usuario or ''
    ).strip().lower()

    if not correo_institucional(correo_usuario):
        raise ErrorNegocio(
            f"Correo inválido. Solo se permiten "
            f"correos @{config.DOMINIO_CORREO}."
        )

    if not puede_gestionar(
        conn,
        rol_actor,
        id_objetivo
    ):
        raise ErrorNegocio(
            "No tienes permisos para modificar a este usuario."
        )

    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE Usuarios
            SET nombre = %s,
                apellidos = %s,
                correo = %s
            WHERE id_usuario = %s
        """, (
            nombre,
            apellidos,
            correo_usuario,
            id_objetivo
        ))

        conn.commit()

    except psycopg.IntegrityError:
        conn.rollback()
        raise ErrorNegocio(
            "Ese correo ya está registrado en otro usuario."
        ) from None

    except Exception:
        conn.rollback()
        raise
