"""Envío de SMS de confirmación de reserva vía Twilio (asíncrono)."""
import re
import threading
import unicodedata

from config import Config


def _normalizar_telefono(telefono):
    """Devuelve el número en formato E.164. Asume España (+34) si no hay prefijo."""
    if not telefono:
        return None
    limpio = re.sub(r"[\s\-\(\)]", "", str(telefono))
    if limpio.startswith("+"):
        return limpio
    if limpio.startswith("00"):
        return "+" + limpio[2:]
    if len(limpio) == 9 and limpio[0] in "6789":
        return Config.SMS_DEFAULT_COUNTRY_CODE + limpio
    return None


def _quitar_acentos(texto):
    if not texto:
        return ""
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn')

def _construir_mensaje_pendiente(nombre, fecha, hora, personas, codigo_confirmacion):
    nombre_limpio = _quitar_acentos(nombre)
    return (
        f"Alchimie: Reserva de {nombre_limpio}. "
        f"{fecha} {hora}, {personas} pax. "
        f"Codigo de confirmacion: {codigo_confirmacion}."
    )


def _construir_mensaje_confirmada(nombre, fecha, hora, personas):
    nombre_limpio = _quitar_acentos(nombre)
    return (
        f"Alchimie: Confirmada reserva de {nombre_limpio}. "
        f"{fecha} {hora}, {personas} pax. "
        f"Te esperamos!"
    )


def _enviar(numero_destino, mensaje):
    sid = Config.TWILIO_ACCOUNT_SID
    token = Config.TWILIO_AUTH_TOKEN
    remitente = Config.TWILIO_FROM_NUMBER

    if not (sid and token and remitente):
        print("[SMS] Configura TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN y TWILIO_FROM_NUMBER en config.py. Envío omitido.")
        return

    try:
        from twilio.rest import Client
    except ImportError:
        print("[SMS] Falta la librería 'twilio'. Instala con: pip install twilio")
        return

    try:
        client = Client(sid, token)
        msg = client.messages.create(body=mensaje, from_=remitente, to=numero_destino)
        print(f"[SMS] Enviado a {numero_destino} (sid={msg.sid})")
    except Exception as e:
        print(f"[SMS] Error enviando a {numero_destino}: {e}")


def enviar_solicitud_confirmacion_async(nombre, fecha, hora, personas, telefono, codigo_confirmacion):
    """Envía un SMS pidiendo confirmación explícita de la reserva."""
    if not Config.SMS_ENABLED:
        print(f"\n[TEST/SMS DESACTIVADO] Código de confirmación para {nombre}: {codigo_confirmacion}\n")
        return

    destino = _normalizar_telefono(telefono)
    if not destino:
        print(f"[SMS] Teléfono no válido para envío: {telefono!r}")
        return

    mensaje = _construir_mensaje_pendiente(nombre, fecha, hora, personas, codigo_confirmacion)
    hilo = threading.Thread(
        target=_enviar,
        args=(destino, mensaje),
        daemon=True,
    )
    hilo.start()


def enviar_confirmacion_final_async(nombre, fecha, hora, personas, telefono):
    """Envía el SMS final cuando la reserva ya está confirmada."""
    if not Config.SMS_ENABLED:
        print(f"\n[TEST/SMS DESACTIVADO] Confirmación de reserva enviada a {nombre} para el {fecha} a las {hora}\n")
        return

    destino = _normalizar_telefono(telefono)
    if not destino:
        print(f"[SMS] Teléfono no válido para envío: {telefono!r}")
        return

    mensaje = _construir_mensaje_confirmada(nombre, fecha, hora, personas)
    hilo = threading.Thread(
        target=_enviar,
        args=(destino, mensaje),
        daemon=True,
    )
    hilo.start()
