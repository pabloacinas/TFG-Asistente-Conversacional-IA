from google.genai.types import GenerateContentConfig

from config import Config


def convertir_mensajes_a_prompt(mensajes):
    partes = []

    for mensaje in mensajes:
        role = mensaje.get("role")
        content = mensaje.get("content", "")

        if role == "system":
            partes.append(f"SISTEMA:\n{content}")
        elif role == "user":
            partes.append(f"USUARIO:\n{content}")
        elif role == "assistant":
            partes.append(f"ASISTENTE:\n{content}")

    return "\n\n".join(partes)


def _build_generation_config(temperature=None, max_tokens=None):
    temp = Config.TEMPERATURE if temperature is None else temperature
    tokens = Config.MAX_TOKENS if max_tokens is None else max_tokens

    return GenerateContentConfig(
        temperature=temp,
        max_output_tokens=tokens,
    )


def generar_respuesta_stream(cliente, mensajes, model=None, temperature=None, max_tokens=None):
    prompt = convertir_mensajes_a_prompt(mensajes)
    modelo = model or Config.GEMINI_MODEL
    config = _build_generation_config(temperature=temperature, max_tokens=max_tokens)

    response = cliente.models.generate_content_stream(
        model=modelo,
        contents=prompt,
        config=config,
    )

    for chunk in response:
        if chunk.text:
            yield chunk.text


def generar_respuesta(cliente, mensajes, model=None, temperature=None, max_tokens=None):
    prompt = convertir_mensajes_a_prompt(mensajes)
    modelo = model or Config.GEMINI_MODEL
    config = _build_generation_config(temperature=temperature, max_tokens=max_tokens)

    response = cliente.models.generate_content(
        model=modelo,
        contents=prompt,
        config=config,
    )

    return response.text or ""
