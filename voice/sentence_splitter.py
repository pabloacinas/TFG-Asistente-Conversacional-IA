"""Trocea un stream de tokens del LLM en frases completas."""
import re

from config import Config

_FIN_FRASE = re.compile(r"[\.\!\?\;…]+[\)\"'»]?\s+|\n+")


def dividir_en_frases(stream_tokens):
    """Generador: consume tokens y emite frases en cuanto detecta puntuación final
    o cuando el buffer crece más de VOZ_FRASE_MIN_CHARS sin puntuación."""
    buffer = ""
    for token in stream_tokens:
        if not token:
            continue
        buffer += token

        while True:
            match = _FIN_FRASE.search(buffer)
            if match:
                fin = match.end()
                frase = buffer[:fin].strip()
                buffer = buffer[fin:]
                if frase:
                    yield frase
                continue

            if len(buffer) >= Config.VOZ_FRASE_MIN_CHARS * 3:
                # Flush por longitud para evitar latencias largas si el LLM no puntúa
                corte = buffer.rfind(" ", 0, Config.VOZ_FRASE_MIN_CHARS * 3)
                if corte > Config.VOZ_FRASE_MIN_CHARS:
                    frase = buffer[:corte].strip()
                    buffer = buffer[corte:]
                    if frase:
                        yield frase
                        continue
            break

    resto = buffer.strip()
    if resto:
        yield resto
