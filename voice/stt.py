"""Speech-to-Text streaming con Cloud Speech v2."""
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import (
    AutoDetectDecodingConfig,
    ExplicitDecodingConfig,
    RecognitionConfig,
    RecognitionFeatures,
    StreamingRecognitionConfig,
    StreamingRecognitionFeatures,
    StreamingRecognizeRequest,
)

from config import Config

_cliente = None


def _get_cliente():
    global _cliente
    if _cliente is None:
        _cliente = SpeechClient()
    return _cliente


def _reconocedor_path():
    # Recognizer "_" usa configuración inline en lugar de un recognizer creado.
    return f"projects/{Config.GCP_PROJECT_ID}/locations/global/recognizers/_"


def _build_streaming_config():
    decoding = ExplicitDecodingConfig(
        encoding=ExplicitDecodingConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=Config.STT_SAMPLE_RATE,
        audio_channel_count=1,
    )
    config = RecognitionConfig(
        explicit_decoding_config=decoding,
        language_codes=[Config.STT_LANGUAGE],
        model=Config.STT_MODEL,
        features=RecognitionFeatures(enable_automatic_punctuation=True),
    )
    streaming_features = StreamingRecognitionFeatures(
        interim_results=True,
        enable_voice_activity_events=True,
    )
    return StreamingRecognitionConfig(
        config=config,
        streaming_features=streaming_features,
    )


def transcribir_streaming(mic_stream):
    """Generador que produce (texto, is_final) consumiendo audio de un MicrofonoStream.

    Itera hasta que recibe un resultado final con texto no vacío y termina.
    """
    cliente = _get_cliente()
    streaming_config = _build_streaming_config()
    config_request = StreamingRecognizeRequest(
        recognizer=_reconocedor_path(),
        streaming_config=streaming_config,
    )

    def request_iter():
        yield config_request
        for chunk in mic_stream.chunks():
            yield StreamingRecognizeRequest(audio=chunk)

    responses = cliente.streaming_recognize(requests=request_iter())

    for response in responses:
        for result in response.results:
            if not result.alternatives:
                continue
            texto = result.alternatives[0].transcript
            yield texto, result.is_final
            if result.is_final and texto.strip():
                return
