"""Captura de micrófono y reproducción de PCM mediante sounddevice."""
import queue
import threading

import numpy as np
import sounddevice as sd

from config import Config


class MicrofonoStream:
    """Captura mono int16 a STT_SAMPLE_RATE; expone una cola de chunks bytes."""

    def __init__(self, sample_rate=None, blocksize=1600):
        self.sample_rate = sample_rate or Config.STT_SAMPLE_RATE
        self.blocksize = blocksize  # ~100 ms a 16 kHz
        self._cola = queue.Queue()
        self._stream = None
        self._cerrado = False

    def _callback(self, indata, frames, time_info, status):
        if status:
            # Underrun/overrun: ignorar pero no romper
            pass
        self._cola.put(bytes(indata))

    def __enter__(self):
        self._stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=self.blocksize,
            dtype="int16",
            channels=1,
            callback=self._callback,
        )
        self._stream.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.cerrar()

    def chunks(self):
        """Generador bloqueante de chunks PCM hasta que se cierre el stream."""
        while not self._cerrado:
            try:
                chunk = self._cola.get(timeout=0.5)
            except queue.Empty:
                continue
            if chunk is None:
                return
            yield chunk

    def cerrar(self):
        if self._cerrado:
            return
        self._cerrado = True
        self._cola.put(None)
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None


class ReproductorPCM:
    """Reproductor en hilo: consume bytes LINEAR16 mono a TTS_SAMPLE_RATE."""

    def __init__(self, sample_rate=None):
        self.sample_rate = sample_rate or Config.TTS_SAMPLE_RATE
        self._cola = queue.Queue()
        self._cancel = threading.Event()
        self._hilo = threading.Thread(target=self._worker, daemon=True)
        self._hilo.start()

    def _worker(self):
        stream = sd.RawOutputStream(
            samplerate=self.sample_rate,
            dtype="int16",
            channels=1,
        )
        stream.start()
        try:
            while True:
                item = self._cola.get()
                if item is None:
                    break
                if self._cancel.is_set():
                    continue
                try:
                    stream.write(item)
                except Exception:
                    pass
        finally:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

    def reproducir(self, pcm_bytes):
        if not pcm_bytes:
            return
        self._cola.put(pcm_bytes)

    def cancelar(self):
        """Marca cancelación y vacía la cola pendiente (barge-in)."""
        self._cancel.set()
        try:
            while True:
                self._cola.get_nowait()
        except queue.Empty:
            pass

    def reanudar(self):
        self._cancel.clear()

    def esperar_vacio(self, timeout=None):
        """Bloquea hasta que la cola esté vacía."""
        self._cola.join() if False else None  # no-op: usamos polling simple
        import time
        t0 = time.time()
        while not self._cola.empty():
            if timeout is not None and (time.time() - t0) > timeout:
                return False
            time.sleep(0.05)
        return True

    def cerrar(self):
        self._cola.put(None)


def calcular_rms(pcm_bytes):
    """RMS aproximado para detectar voz durante reproducción (barge-in heurístico)."""
    if not pcm_bytes:
        return 0.0
    arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
    if arr.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(arr * arr)))
