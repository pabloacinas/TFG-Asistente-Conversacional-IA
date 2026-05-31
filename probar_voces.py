"""Reproduce una frase con varias voces de Google TTS para comparar."""
import time

from google.cloud import texttospeech as tts

from config import Config
from voice.audio_io import ReproductorPCM

FRASE = "Hola, soy Alchi de L'Alchimie. ¿En qué puedo ayudarle hoy?"

VOCES = [
    "es-ES-Chirp3-HD-Aoede",#
    "es-ES-Chirp3-HD-Kore",
    "es-ES-Chirp3-HD-Leda",#
    "es-ES-Chirp3-HD-Zephyr",
    "es-ES-Chirp3-HD-Charon",@
    "es-ES-Chirp3-HD-Puck",
    "es-ES-Chirp3-HD-Fenrir",
    "es-ES-Chirp3-HD-Orus",@
    "es-ES-Studio-F",#
    "es-ES-Studio-C",
    "es-ES-Neural2-C",
    "es-ES-Neural2-F",
]


def probar(nombre_voz, reproductor, cliente):
    print(f"\n>>> {nombre_voz}")
    audio_cfg = tts.AudioConfig(
        audio_encoding=tts.AudioEncoding.LINEAR16,
        sample_rate_hertz=Config.TTS_SAMPLE_RATE,
    )
    voz = tts.VoiceSelectionParams(language_code="es-ES", name=nombre_voz)
    try:
        resp = cliente.synthesize_speech(
            input=tts.SynthesisInput(text=FRASE),
            voice=voz,
            audio_config=audio_cfg,
        )
        audio = resp.audio_content
        if audio[:4] == b"RIFF":
            audio = audio[44:]
        reproductor.reproducir(audio)
        reproductor.esperar_vacio(timeout=20)
        time.sleep(0.4)
    except Exception as e:
        print(f"   ERROR: {e}")


def main():
    cliente = tts.TextToSpeechClient()
    reproductor = ReproductorPCM()
    try:
        for v in VOCES:
            probar(v, reproductor, cliente)
    finally:
        reproductor.cerrar()


if __name__ == "__main__":
    main()
