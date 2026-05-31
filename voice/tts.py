"""Text-to-Speech con Cloud TTS. Streaming Chirp3-HD con fallback a Neural2."""
from google.cloud import texttospeech as tts

from config import Config

_cliente = None
_voz_actual = None


def _get_cliente():
    global _cliente
    if _cliente is None:
        _cliente = tts.TextToSpeechClient()
    return _cliente


def _voz_streaming():
    return tts.VoiceSelectionParams(
        language_code=Config.TTS_LANGUAGE,
        name=Config.TTS_VOICE,
    )


def _audio_config_streaming():
    # streaming_synthesize solo admite PCM (raw int16 sin cabecera) a 24kHz
    return tts.StreamingAudioConfig(
        audio_encoding=tts.AudioEncoding.PCM,
        sample_rate_hertz=Config.TTS_SAMPLE_RATE,
    )


def sintetizar_streaming(frases_iter, reproductor, cancel_event=None):
    """Toma un iterable de frases y va alimentando el reproductor PCM.

    Usa streaming_synthesize de Chirp3-HD; si la voz Chirp3 no está disponible
    cae a synthesize_speech estándar.
    """
    cliente = _get_cliente()

    try:
        _streaming_chirp(cliente, frases_iter, reproductor, cancel_event)
    except Exception as e:
        msg = str(e).lower()
        if "chirp" in msg or "not supported" in msg or "invalid" in msg or "permission" in msg:
            print(f"[VOZ] TTS streaming falló ({e}); usando fallback Neural2.")
            _no_streaming_fallback(cliente, frases_iter, reproductor, cancel_event)
        else:
            raise


def _streaming_chirp(cliente, frases_iter, reproductor, cancel_event):
    config = tts.StreamingSynthesizeConfig(
        voice=_voz_streaming(),
        streaming_audio_config=_audio_config_streaming(),
    )
    config_req = tts.StreamingSynthesizeRequest(streaming_config=config)

    def requests():
        yield config_req
        for frase in frases_iter:
            if cancel_event is not None and cancel_event.is_set():
                return
            if not frase.strip():
                continue
            yield tts.StreamingSynthesizeRequest(
                input=tts.StreamingSynthesisInput(text=frase)
            )

    for response in cliente.streaming_synthesize(requests=requests()):
        if cancel_event is not None and cancel_event.is_set():
            return
        if response.audio_content:
            reproductor.reproducir(response.audio_content)


def _no_streaming_fallback(cliente, frases_iter, reproductor, cancel_event):
    voz = tts.VoiceSelectionParams(
        language_code=Config.TTS_LANGUAGE,
        name=Config.TTS_VOICE_FALLBACK,
    )
    audio_cfg = tts.AudioConfig(
        audio_encoding=tts.AudioEncoding.LINEAR16,
        sample_rate_hertz=Config.TTS_SAMPLE_RATE,
    )
    for frase in frases_iter:
        if cancel_event is not None and cancel_event.is_set():
            return
        if not frase.strip():
            continue
        resp = cliente.synthesize_speech(
            input=tts.SynthesisInput(text=frase),
            voice=voz,
            audio_config=audio_cfg,
        )
        # Recortar cabecera WAV (44 bytes) si LINEAR16 viene con cabecera
        audio = resp.audio_content
        if audio[:4] == b"RIFF":
            audio = audio[44:]
        reproductor.reproducir(audio)


def hablar_texto(texto, reproductor):
    """Helper síncrono para frases sueltas (saludos, errores)."""
    sintetizar_streaming(iter([texto]), reproductor)
