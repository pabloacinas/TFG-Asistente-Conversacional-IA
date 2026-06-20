"""
Asistente de IA Local - Alchi (IA + RAG + RESERVAS + HORARIO)
"""

import argparse
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["USE_TORCH"] = "True"

from config import Config
from reservas import GestorReservas
from llm_provider import obtener_cliente
from llm_chat import generar_respuesta_stream


# =========================
# MARKER
# =========================

def get_marker_converter():
    try:
        # Import perezoso: marker arrastra torch/torchvision pesados y a veces
        # incompatibles. Solo se carga si realmente hay que procesar un PDF.
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        print("Inicializando modelos de Marker...")
        return PdfConverter(artifact_dict=create_model_dict())
    except Exception as e:
        print(f"Error al inicializar Marker: {e}")
        return None


def procesar_pdf(ruta_pdf, ruta_cache, converter=None, nombre="archivo"):
    try:
        if not os.path.exists(ruta_pdf):
            print(f"ADVERTENCIA: No se encontró {nombre}")
            return ""

        if os.path.exists(ruta_cache):
            if os.path.getmtime(ruta_cache) > os.path.getmtime(ruta_pdf):
                print(f"Cargando {nombre} desde caché...")
                with open(ruta_cache, "r", encoding="utf-8") as f:
                    return f.read()

        if converter is None:
            converter = get_marker_converter()
        if converter is None:
            return ""

        print(f"Procesando {nombre} con Marker...")
        rendered = converter(ruta_pdf)

        with open(ruta_cache, "w", encoding="utf-8") as f:
            f.write(rendered.markdown)

        return rendered.markdown

    except Exception as e:
        print(f"Error procesando {nombre}: {e}")
        return ""


# RAG y Reranking eliminados (se pasa el menú completo directamente en el prompt de Gemini)

#========================= # PROMPT # =========================
def crear_system_prompt(contexto_carta, contexto_horario): 
    return f"""Eres 'Alchi', metre de L'Alchimie, y atiendes como asistente telefónico.

Objetivo principal:
- Conversación rápida y fluida.
- Respuestas breves, claras y directas.

Estilo:
- Máximo 1-2 frases por respuesta.
- Evita introducciones largas, relleno o repeticiones.
- Sé amable y profesional, pero conciso.
- Haz solo una pregunta de seguimiento cada vez cuando falte información.

Reglas de contenido:
- Usa EXCLUSIVAMENTE este contexto.
- No inventes datos ni enlaces.
- Si falta información, dilo de forma corta.
- El restaurante no tiene enlaces web en este sistema.

Contexto horario:
{contexto_horario}

Contexto menú:
{contexto_carta}

Reglas de horario:
- Distingue horario de apertura del restaurante y horario de cocina.
- Si preguntan por "cenas", da horario de cenas (cocina).
- Si preguntan por "comidas", da horario de comidas (cocina).
- Si preguntan por "horario" general, da ambos de forma corta.
- Las reservas solo se realizan en horario de cocina.
- Cuando una reserva quede registrada como pendiente, indícale al cliente que no cuelgue y que espere el SMS con el código para dártelo.
- No menciones el código en ningún momento; el cliente debe leerlo del SMS y decírtelo.
- Si no te facilita el código de 4 dígitos, la reserva no quedará confirmada.
"""
# =========================
# TURNO (compartido texto/voz)
# =========================

def procesar_turno(msg, cliente, carta_md, markdown_horario, gestor, historial):
    """Generador de chunks de texto para un turno. Decide reserva vs RAG+LLM
    y actualiza el historial al terminar el stream."""
    if gestor.hay_flujo_reserva_activo() or gestor.detectar_intencion(msg):
        respuesta = gestor.procesar_turno(msg)
        mesas_debug = gestor.datos.get("mesa_ids", [])
        if not mesas_debug and gestor.ultima_accion == "RESERVA_CONFIRMADA":
            mesas_debug = gestor.ultima_mesas_asignadas

        print(f"\n[DEBUG] Datos: {gestor.datos}")
        print(f"[DEBUG] Mesas asignadas: {mesas_debug if mesas_debug else 'ninguna'}")
        print(f"[DEBUG] Estado: {gestor.estado}")
        print(f"[DEBUG] Acción: {gestor.ultima_accion}")
        print(f"[DEBUG] Sistema: {respuesta}\n")

        yield respuesta
        return

    sys_prompt = crear_system_prompt(carta_md, markdown_horario)

    mensajes = (
        [{"role": "system", "content": sys_prompt}] +
        historial +
        [{"role": "user", "content": msg}]
    )

    full = ""
    for chunk in generar_respuesta_stream(
        cliente,
        mensajes,
        model=Config.GEMINI_MODEL,
        temperature=Config.TEMPERATURE,
        max_tokens=Config.MAX_TOKENS,
    ):
        full += chunk
        yield chunk

    historial.append({"role": "user", "content": msg})
    historial.append({"role": "assistant", "content": full})


# =========================
# CHAT
# =========================

def chatear(cliente, carta_md, markdown_horario):
    print("\n" + "=" * 60)
    print("  ASISTENTE ALCHI  ")
    print("=" * 60 + "\n")

    gestor = GestorReservas(llm_client=cliente)
    historial = []

    while True:
        try:
            msg = input("Tú: ").strip()

            if msg.lower() in ["salir", "exit", "quit"]:
                print("\nHasta pronto.\n")
                break

            if not msg:
                continue

            print("Alchi: ", end="", flush=True)
            for chunk in procesar_turno(msg, cliente, carta_md, markdown_horario, gestor, historial):
                print(chunk, end="", flush=True)
            print("\n")

        except KeyboardInterrupt:
            print("\n\nAdiós.")
            break
        except Exception as e:
            print(f"\nError: {e}")
            break


# =========================
# MAIN
# =========================

def main():
    parser = argparse.ArgumentParser(description="Asistente Alchi")
    parser.add_argument("--server", action="store_true", help="Modo servidor HTTP multi-hilo (Centralita Local)")
    parser.add_argument("--voz", action="store_true", help="Modo conversación por voz (STT + TTS para terminal, o habilita simulación por voz en el servidor)")
    parser.add_argument("--texto", action="store_true", help="Modo terminal por texto (por defecto)")
    
    parser.add_argument("--port", type=int, default=8000, help="Puerto para el servidor HTTP (por defecto: 8000)")
    parser.add_argument("--host", type=str, default="localhost", help="Host para el servidor HTTP (por defecto: localhost)")
    args = parser.parse_args()

    print("\nIniciando Alchi...")

    base = PROJECT_ROOT

    ruta_carta_pdf = os.path.join(base, Config.ARCHIVO_PDF)
    ruta_carta_md = os.path.join(base, Config.ARCHIVO_CARTA_MD)

    ruta_horario_pdf = os.path.join(base, Config.ARCHIVO_HORARIO_PDF)
    ruta_horario_md = os.path.join(base, Config.ARCHIVO_HORARIO_MD)

    converter = None
    if not os.path.exists(ruta_carta_md) or not os.path.exists(ruta_horario_md):
        converter = get_marker_converter()

    carta_md = procesar_pdf(ruta_carta_pdf, ruta_carta_md, converter, "carta")
    if not carta_md:
        print("Error cargando carta.")
        return

    horario_md = procesar_pdf(ruta_horario_pdf, ruta_horario_md, converter, "horario")

    cliente = obtener_cliente()

    if args.server:
        from ServidorCentralita.server import iniciar_servidor
        iniciar_servidor(cliente, carta_md, horario_md, host=args.host, port=args.port, voz_enabled=args.voz)
    elif args.voz:
        from voice import iniciar_bucle_voz
        iniciar_bucle_voz(cliente, carta_md, horario_md, procesar_turno)
    else:
        chatear(cliente, carta_md, horario_md)


if __name__ == "__main__":
    main()