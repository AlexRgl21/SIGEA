
import logging
import os

import requests

import config

logger = logging.getLogger(__name__)
RESEND_URL = 'https://api.resend.com/emails'


def _destinatarios_validos(destinatarios):
    if isinstance(destinatarios, str):
        destinatarios = [destinatarios]

    return list(dict.fromkeys(
        str(destino).strip()
        for destino in (destinatarios or [])
        if destino and str(destino).strip()
    ))


def enviar_ahora(destinatarios, asunto, contenido):
    destinatarios = _destinatarios_validos(destinatarios)

    if not destinatarios:
        return False

    api_key = os.getenv('RESEND_API_KEY', '').strip()
    remitente = os.getenv('RESEND_FROM', '').strip()
    responder_a = os.getenv('RESEND_REPLY_TO', '').strip()

    if not api_key or not remitente:
        logger.error('Faltan RESEND_API_KEY o RESEND_FROM; correo no enviado')
        return False

    encabezados = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    exitos = 0

    with requests.Session() as sesion:
        for destino in destinatarios:
            mensaje = {
                'from': remitente,
                'to': [destino],
                'subject': asunto,
                'text': contenido,
            }

            if responder_a:
                mensaje['reply_to'] = responder_a

            try:
                respuesta = sesion.post(
                    RESEND_URL,
                    headers=encabezados,
                    json=mensaje,
                    timeout=(5, 15),
                )

                if not respuesta.ok:
                    logger.error(
                        'Resend rechazó el correo: HTTP %s',
                        respuesta.status_code,
                    )
                    continue

                datos = respuesta.json()
                identificador = datos.get('id')

                if not identificador:
                    logger.error('Resend no devolvió un identificador de correo')
                    continue

                exitos += 1
                logger.info('Correo aceptado por Resend: %s', identificador)

            except (requests.RequestException, ValueError):
                logger.exception('Error al solicitar el envío por Resend')

    return exitos == len(destinatarios)


def enviar_correo(destinatarios, asunto, contenido):
    return enviar_ahora(destinatarios, asunto, contenido)


# Plantillas de mensajes
def correo_codigo_recuperacion(correo, codigo, nombre):
    return enviar_correo(
        correo,
        'Código de verificación - Restablecer Contraseña SIGEA',
        f'''Hola {nombre},

Has solicitado restablecer tu contraseña en el Sistema Integral de Gestión de Espacios Académicos (SIGEA).

Tu código de verificación es: {codigo}

Este código es válido durante los próximos {config.CODIGO_VIGENCIA_MIN} minutos. Si no solicitaste este cambio, puedes ignorar este correo de forma segura.

Saludos,
El equipo de SIGEA.''',
    )


def correo_bienvenida(correo, nombre, password_temporal):
    return enviar_correo(
        correo,
        'Bienvenido a SIGEA - Tus credenciales de acceso',
        f'''Hola {nombre},

Has sido registrado exitosamente en el Sistema Integral de Gestión de Espacios Académicos (SIGEA).

Tus credenciales de acceso son:
Usuario / Correo: {correo}
Contraseña Temporal: {password_temporal}

Te recomendamos iniciar sesión lo antes posible.

Saludos,
El equipo de SIGEA.''',
    )


def notificar_nueva_reserva(correos_admins, fecha):
    return enviar_correo(
        correos_admins,
        'SIGEA - Nueva Solicitud de Reserva Especial',
        f'Se ha registrado una nueva solicitud para el día {fecha}. '
        'Ingresa a SIGEA para revisarla.',
    )


def notificar_nuevo_ticket(
    correos_soporte, id_ticket, asunto, categoria, solicitante, descripcion
):
    resumen = descripcion if len(descripcion) <= 300 else descripcion[:300].rstrip() + '...'

    return enviar_correo(
        correos_soporte,
        f'SIGEA - Nuevo ticket de soporte TCK-{id_ticket:04d}',
        f'Se ha registrado un nuevo ticket de soporte técnico.\n\n'
        f'Folio: TCK-{id_ticket:04d}\n'
        f'Solicitante: {solicitante}\n'
        f'Categoría: {categoria}\n'
        f'Asunto: {asunto}\n\n'
        f'Descripción:\n{resumen}\n\n'
        'Ingresa a SIGEA (Soporte Técnico) para atenderlo.\n\n'
        'Saludos,\nEl equipo de SIGEA.',
    )


def notificar_reserva_aprobada(correo, nombre, espacio, fecha, hora_inicio, hora_fin):
    return enviar_correo(
        correo,
        'SIGEA - Tu reserva ha sido Aprobada',
        f"Hola {nombre},\n\nTu solicitud para el espacio '{espacio}' el día {fecha} "
        f'de {hora_inicio} a {hora_fin} ha sido APROBADA.\n\nSaludos.',
    )


def notificar_reserva_rechazada(correo, nombre, espacio, fecha):
    return enviar_correo(
        correo,
        'SIGEA - Tu reserva ha sido Rechazada',
        f"Hola {nombre},\n\nLamentablemente tu solicitud para el espacio '{espacio}' "
        f'el día {fecha} ha sido RECHAZADA.\n\nContacta a coordinación para más detalles.',
    )
