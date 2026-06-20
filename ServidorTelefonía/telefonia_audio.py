"""Adaptador de audio entre Twilio Media Streams y el pipeline de voz de Alchi.

Twilio envía y espera audio mu-law (PCMU) mono a 8 kHz, troceado en frames de
20 ms (160 bytes) y codificado en base64 dentro de mensajes JSON por WebSocket.

Este módulo ofrece:
- `TwilioInboundStream`: una cola de bytes mu-law que expone `.chunks()`, la
  misma interfaz que `MicrofonoStream`, para poder reutilizar `transcribir_streaming`.
- helpers para trocear audio mu-law en frames listos para enviar a Twilio.
"""
import queue

from config import Config


# Sentinela para indicar que la llamada ha terminado y `.chunks()` debe parar.
_FIN = object()


class TwilioInboundStream:
    """Cola thread-safe de audio mu-law entrante con interfaz tipo MicrofonoStream.

    El handler WebSocket (asyncio) llama a `put()` con cada frame recibido de
    Twilio; el hilo de la llamada consume el audio mediante `chunks()`, que es
    un generador bloqueante igual que el del micrófono local.
    """

    def __init__(self):
        self._cola = queue.Queue()
        self._cerrado = False

    def put(self, datos_mulaw):
        """Encola un frame de audio mu-law recibido de Twilio."""
        if not self._cerrado and datos_mulaw:
            self._cola.put(datos_mulaw)

    def clear(self):
        """Descarta el audio acumulado (p. ej. el captado mientras el bot hablaba)."""
        try:
            while True:
                self._cola.get_nowait()
        except queue.Empty:
            pass

    def close(self):
        """Marca el stream como cerrado y desbloquea cualquier `chunks()` activo."""
        self._cerrado = True
        self._cola.put(_FIN)

    def chunks(self):
        """Generador bloqueante de bytes mu-law hasta cierre o inactividad larga."""
        while True:
            try:
                item = self._cola.get(timeout=30.0)
            except queue.Empty:
                return
            if item is _FIN or self._cerrado:
                return
            yield item


def trocear_frames(datos_mulaw, tam_frame=None):
    """Divide bytes mu-law en frames de tamaño fijo (20 ms por defecto).

    El último frame se rellena con silencio mu-law (0xFF) para completar 20 ms.
    """
    tam = tam_frame or Config.TELEFONIA_FRAME_BYTES
    for inicio in range(0, len(datos_mulaw), tam):
        frame = datos_mulaw[inicio:inicio + tam]
        if len(frame) < tam:
            frame = frame + b"\xff" * (tam - len(frame))
        yield frame
