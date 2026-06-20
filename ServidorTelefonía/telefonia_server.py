"""Servidor de telefonía para Alchi (Twilio Voice + Media Streams).

Permite recibir una llamada telefónica real (a través de un número de Twilio) y
conversar con el asistente Alchi por voz, reutilizando el mismo cerebro que la
centralita web: `procesar_turno`, `GestorReservas` y el STT/TTS de Google Cloud.

Arquitectura:
    Móvil → Twilio (número) → POST /voice (TwiML) → WebSocket /media
    → STT (mu-law 8 kHz) → procesar_turno → TTS (mu-law 8 kHz) → Twilio → Móvil

Este servidor es independiente de `server.py` (el panel web sigue intacto). Se
expone a internet con ngrok para la demo:

    uvicorn telefonia_server:app --port 5050
    ngrok http 5050
    # y se configura el webhook de Voz del número de Twilio a https://<ngrok>/voice
"""
import asyncio
import base64
import json
import os
import queue
import sys
import threading
import time
import traceback

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NUCLEO_PATH = os.path.join(PROJECT_ROOT, "NucleoAlchi")
if NUCLEO_PATH not in sys.path:
    sys.path.insert(0, NUCLEO_PATH)

from config import Config
from llm_provider import obtener_cliente
from reservas import GestorReservas
from voice.sentence_splitter import dividir_en_frases
from voice.stt import transcribir_streaming_telefonia
from voice.tts import sintetizar_telefonia
try:
    from .telefonia_audio import TwilioInboundStream, trocear_frames
except Exception:
    from telefonia_audio import TwilioInboundStream, trocear_frames


# =========================
# Carga de contexto (carta + horario) una sola vez al arrancar
# =========================

def _cargar_md(ruta_cache):
    if os.path.exists(ruta_cache):
        with open(ruta_cache, "r", encoding="utf-8") as f:
            return f.read()
    return ""


_BASE = PROJECT_ROOT
CLIENTE = obtener_cliente()
CARTA_MD = _cargar_md(os.path.join(_BASE, Config.ARCHIVO_CARTA_MD))
HORARIO_MD = _cargar_md(os.path.join(_BASE, Config.ARCHIVO_HORARIO_MD))


def _log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] [TELEFONIA] {msg}", flush=True)


# =========================
# Hilo de conversación por llamada
# =========================

class LlamadaTelefonica(threading.Thread):
    """Gestiona una llamada: escucha (STT) → piensa (LLM) → habla (TTS).

    Reutiliza el flujo de `procesar_turno`. El audio entrante llega por
    `inbound` (mu-law) y la voz sintetizada se deja en `outbound` (frames
    mu-law de 20 ms) para que el bucle async la envíe a Twilio.
    """

    def __init__(self, telefono, inbound, outbound):
        super().__init__(name="LlamadaTelefonica", daemon=True)
        self.telefono = telefono
        self.inbound = inbound
        self.outbound = outbound
        self.activo = True

        from main import procesar_turno  # import perezoso para evitar ciclos
        self._procesar_turno = procesar_turno
        self.gestor = GestorReservas(llm_client=CLIENTE)
        self.historial = []

    def _hablar(self, texto):
        """Sintetiza una frase a mu-law y la encola en frames para Twilio."""
        if not texto or not texto.strip():
            return
        try:
            mulaw = sintetizar_telefonia(texto)
        except Exception as e:
            _log(f"Error TTS: {e}")
            return
        for frame in trocear_frames(mulaw):
            if not self.activo:
                return
            self.outbound.put(frame)

    def run(self):
        _log(f"Llamada iniciada ({self.telefono}).")
        try:
            # Saludo inicial
            self._hablar(Config.VOZ_SALUDO_INICIAL)

            while self.activo:
                # Descartar el audio captado mientras el bot hablaba (sin barge-in).
                self.inbound.clear()

                # Escuchar un turno del usuario hasta resultado final.
                texto_usuario = ""
                for texto, is_final in transcribir_streaming_telefonia(self.inbound):
                    if not self.activo:
                        return
                    if is_final and texto.strip():
                        texto_usuario = texto.strip()
                        break

                if not self.activo:
                    return
                if not texto_usuario:
                    continue

                _log(f"Usuario: {texto_usuario!r}")

                # Pensar + hablar, frase a frase para reducir latencia.
                stream = self._procesar_turno(
                    texto_usuario,
                    CLIENTE,
                    CARTA_MD,
                    HORARIO_MD,
                    self.gestor,
                    self.historial,
                )
                for frase in dividir_en_frases(stream):
                    if not self.activo:
                        return
                    _log(f"Alchi: {frase!r}")
                    self._hablar(frase)

        except Exception:
            _log("Error en el hilo de llamada:\n" + traceback.format_exc())
        finally:
            self.activo = False
            _log("Hilo de llamada finalizado.")

    def colgar(self):
        self.activo = False
        self.inbound.close()


# =========================
# FastAPI: webhook TwiML + WebSocket de audio
# =========================

app = FastAPI()


def _twiml_stream(host):
    """Devuelve el TwiML que ordena a Twilio abrir el stream de audio bidireccional."""
    wss_url = f"wss://{host}/media"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Connect><Stream url=\"{wss_url}\" /></Connect>"
        "</Response>"
    )


@app.api_route("/voice", methods=["GET", "POST"])
async def voice(request: Request):
    """Webhook que Twilio invoca cuando entra una llamada."""
    host = Config.TELEFONIA_PUBLIC_HOST or request.url.hostname
    _log(f"Llamada entrante; respondiendo TwiML con stream a wss://{host}/media")
    return PlainTextResponse(_twiml_stream(host), media_type="application/xml")


@app.websocket("/media")
async def media(ws: WebSocket):
    """Canal de audio en tiempo real con Twilio (Media Streams)."""
    await ws.accept()
    loop = asyncio.get_event_loop()

    inbound = TwilioInboundStream()
    outbound = queue.Queue()
    stream_sid = None
    llamada = None

    async def enviar_audio():
        """Lee frames mu-law de `outbound` y los envía a Twilio con pacing de 20 ms."""
        while True:
            try:
                frame = await loop.run_in_executor(None, outbound.get, True, 0.2)
            except Exception:
                # Timeout de la cola: comprobamos si la llamada sigue viva.
                if llamada is not None and not llamada.activo:
                    return
                continue
            if stream_sid is None:
                continue
            payload = base64.b64encode(frame).decode("ascii")
            await ws.send_text(json.dumps({
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": payload},
            }))
            await asyncio.sleep(0.02)

    sender_task = asyncio.create_task(enviar_audio())

    try:
        while True:
            mensaje = await ws.receive_text()
            datos = json.loads(mensaje)
            evento = datos.get("event")

            if evento == "start":
                start = datos.get("start", {})
                stream_sid = start.get("streamSid") or datos.get("streamSid")
                params = start.get("customParameters", {}) or {}
                telefono = params.get("From") or params.get("telefono") or "desconocido"
                _log(f"Stream iniciado (streamSid={stream_sid}).")
                llamada = LlamadaTelefonica(telefono, inbound, outbound)
                llamada.start()

            elif evento == "media":
                payload = datos.get("media", {}).get("payload")
                if payload:
                    inbound.put(base64.b64decode(payload))

            elif evento == "stop":
                _log("Stream detenido por Twilio.")
                break

    except WebSocketDisconnect:
        _log("WebSocket desconectado.")
    except Exception:
        _log("Error en el WebSocket:\n" + traceback.format_exc())
    finally:
        if llamada is not None:
            llamada.colgar()
        else:
            inbound.close()
        sender_task.cancel()
        try:
            await ws.close()
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=Config.TELEFONIA_PORT)
