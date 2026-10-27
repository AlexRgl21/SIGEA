# Todo el envío de correo de SIGEA

import logging
import os
import smtplib
import threading
from email.message import EmailMessage

import config

logger = logging.getLogger(__name__)


def construir_mensaje(emisor, destinatarios, asunto, contenido):
    # Arma el mensaje. Con varios destinatarios van en copia oculta (Bcc), para que nadie vea los correos de los demás.
    msg = EmailMessage()
    msg['Subject'] = asunto
    msg['From'] = emisor
    if len(destinatarios) == 1:
        msg['To'] = destinatarios[0]
    else:
        msg['To'] = emisor
        msg['Bcc'] = ', '.join(destinatarios)
    msg.set_content(contenido)
    return msg


def _abrir_smtp():
    if config.SMTP_PUERTO == 465:
        return smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PUERTO, timeout=config.SMTP_TIMEOUT_SEG)
    servidor = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PUERTO, timeout=config.SMTP_TIMEOUT_SEG)
    servidor.starttls()
    return servidor


def enviar_ahora(destinatarios, asunto, contenido):
    # Envío síncrono. Nunca lanza excepciones: registra el error y devuelve False.
    emisor = os.getenv('GMAIL_USER')
    clave = os.getenv('GMAIL_PASS')
    if not emisor or not clave:
        logger.error("Faltan GMAIL_USER o GMAIL_PASS: no se envió el correo '%s'", asunto)
        return False
    try:
        msg = construir_mensaje(emisor, destinatarios, asunto, contenido)
        with _abrir_smtp() as servidor:          # el with cierra la conexión aunque falle
            servidor.login(emisor, clave)
            servidor.send_message(msg)
        logger.info("Correo '%s' enviado (%d destinatario(s))", asunto, len(destinatarios))
        return True
    except Exception:
        logger.exception("Error al enviar el correo '%s'", asunto)
        return False


def enviar_correo(destinatarios, asunto, contenido):
    # Envía en segundo plano. Acepta un correo (str) o una lista.
    if isinstance(destinatarios, str):
        destinatarios = [destinatarios]
    destinatarios = [d for d in destinatarios if d]
    if not destinatarios:
        return None
    hilo = threading.Thread(target=enviar_ahora, args=(destinatarios, asunto, contenido), daemon=True)
    hilo.start()
    return hilo


# Plantillas
def correo_codigo_recuperacion(correo, codigo, nombre):
    enviar_correo(correo, 'Código de verificación - Restablecer Contraseña SIGEA', f"""Hola {nombre},

Has solicitado restablecer tu contraseña en el Sistema Integral de Gestión de Espacios Académicos (SIGEA).

Tu código de verificación es: {codigo}

Este código es válido durante los próximos {config.CODIGO_VIGENCIA_MIN} minutos. Si no solicitaste este cambio, puedes ignorar este correo de forma segura.

Saludos,
El equipo de SIGEA.
""")


def correo_bienvenida(correo, nombre, password_temporal):
    enviar_correo(correo, 'Bienvenido a SIGEA - Tus credenciales de acceso', f"""Hola {nombre},
Has sido registrado exitosamente en el Sistema Integral de Gestión de Espacios Académicos (SIGEA).

Tus credenciales de acceso son:
Usuario / Correo: {correo}
Contraseña Temporal: {password_temporal}

Te recomendamos iniciar sesión lo antes posible.

Saludos,
El equipo de SIGEA.
""")


def notificar_nueva_reserva(correos_almacen, fecha):
    enviar_correo(correos_almacen, "SIGEA - Nueva Solicitud de Reserva Especial",
                f"Se ha registrado una nueva solicitud para el día {fecha}. "
                "Ingresa a SIGEA para revisarla.")


def notificar_reserva_aprobada(correo, nombre, espacio, fecha, hora_inicio, hora_fin):
    enviar_correo(correo, "SIGEA - Tu reserva ha sido Aprobada",
                f"Hola {nombre},\n\nTu solicitud para el espacio '{espacio}' el día {fecha} "
                f"de {hora_inicio} a {hora_fin} ha sido APROBADA.\n\nSaludos.")


def notificar_reserva_rechazada(correo, nombre, espacio, fecha):
    enviar_correo(correo, "SIGEA - Tu reserva ha sido Rechazada",
                f"Hola {nombre},\n\nLamentablemente tu solicitud para el espacio '{espacio}' "
                f"el día {fecha} ha sido RECHAZADA.\n\nContacta a almacén para más detalles.")