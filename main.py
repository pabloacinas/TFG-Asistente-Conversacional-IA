"""
Asistente de IA Local - Alchi (IA + RAG + RESERVAS + HORARIO)
"""

import os
import sys

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["USE_TORCH"] = "True"

import chromadb
from chromadb.utils import embedding_functions
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict

from config import Config
from reservas import GestorReservas
from llm_provider import obtener_cliente
from llm_chat import generar_respuesta_stream
from sentence_transformers import SentenceTransformer, util
model_rerank = SentenceTransformer("all-MiniLM-L6-v2")


# =========================
# MARKER
# =========================

def get_marker_converter():
    try:
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


# =========================
# RAG
# =========================

def segmentar_texto(texto):
    # LEGACY DESACTIVADO:
    # print(f"Segmentando texto en fragmentos de {Config.CHUNK_SIZE} caracteres...")
    # chunks = []
    # inicio = 0
    #
    # while inicio < len(texto):
    #     fin = inicio + Config.CHUNK_SIZE
    #
    #     if fin < len(texto):
    #         ultimo_salto = texto.rfind("\n", inicio, fin)
    #         if ultimo_salto != -1 and ultimo_salto > inicio + (Config.CHUNK_SIZE // 2):
    #             fin = ultimo_salto
    #
    #     chunk = texto[inicio:fin].strip()
    #     if chunk:
    #         chunks.append(chunk)
    #
    #     inicio = fin - Config.CHUNK_OVERLAP
    #     if inicio < 0:
    #         inicio = 0
    #     if inicio >= len(texto):
    #         break
    #
    # print(f"Se han generado {len(chunks)} fragmentos.")
    # return chunks
    return [texto]


def crear_indice_rag(markdown):
    try:
        os.makedirs(Config.DB_PATH_VECTORIAL, exist_ok=True)

        cliente_db = chromadb.PersistentClient(path=Config.DB_PATH_VECTORIAL)

        embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        nombre = "carta_restaurante"

        try:
            cliente_db.delete_collection(name=nombre)
            print("Colección anterior eliminada.")
        except:
            pass

        coleccion = cliente_db.create_collection(
            name=nombre,
            embedding_function=embedding_fn
        )

        chunks = [markdown]
        ids = ["chunk_0"]

        # chunks = segmentar_texto(markdown)
        # ids = [f"chunk_{i}" for i in range(len(chunks))]

        coleccion.add(documents=chunks, ids=ids)

        print("Base vectorial creada.")
        return coleccion

    except Exception as e:
        print(f"Error RAG: {e}")
        return None


def buscar_contexto(coleccion, consulta):
    try:
        res = coleccion.query(query_texts=[consulta], n_results=Config.TOP_K_RESULTS)
        return "\n\n---\n\n".join(res["documents"][0])
    except Exception as e:
        print(f"Error búsqueda: {e}")
        return ""

# =========================
# Reranking
# =========================

def rerank_chunks(consulta, chunks, top_k=2):
    # LEGACY DESACTIVADO:
    # if not chunks:
    #     return ""
    #
    # emb_query = model_rerank.encode(consulta, convert_to_tensor=True)
    # emb_chunks = model_rerank.encode(chunks, convert_to_tensor=True)
    #
    # scores = util.cos_sim(emb_query, emb_chunks)[0]
    #
    # ranked = sorted(
    #     zip(chunks, scores),
    #     key=lambda x: x[1],
    #     reverse=True
    # )
    #
    # top_chunks = [chunk for chunk, _ in ranked[:top_k]]
    # return "\n\n".join(top_chunks)
    if not chunks:
        return ""
    return "\n\n".join(chunks[:top_k])

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
"""
# =========================
# CHAT
# =========================

def chatear(cliente, coleccion, markdown_horario):
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

            # =========================
            # RESERVAS (CONTROL TOTAL)
            # =========================
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

                print(f"Alchi: {respuesta}\n")
                continue

            # =========================
            # RAG + LLM (SIN OPTIMIZACIONES LEGACY)
            # =========================
            ctx = buscar_contexto(coleccion, msg)

            # resultados = coleccion.query(
            #     query_texts=[msg],
            #     n_results=5
            # )
            #
            # chunks = resultados["documents"][0]
            #
            # ctx = rerank_chunks(msg, chunks, top_k=2)
            sys_prompt = crear_system_prompt(ctx, markdown_horario)

            mensajes = (
                [{"role": "system", "content": sys_prompt}] +
                historial +
                [{"role": "user", "content": msg}]
            )

            print("Alchi: ", end="", flush=True)

            full = ""
            for chunk in generar_respuesta_stream(
                cliente,
                mensajes,
                model=Config.GEMINI_MODEL,
                temperature=Config.TEMPERATURE,
                max_tokens=Config.MAX_TOKENS,
            ):
                print(chunk, end="", flush=True)
                full += chunk

            print("\n")

            historial.append({"role": "user", "content": msg})
            historial.append({"role": "assistant", "content": full})

            # if len(historial) > Config.MAX_MENSAJES_HISTORIAL:
            #     historial = historial[-Config.MAX_MENSAJES_HISTORIAL:]

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
    print("\nIniciando Alchi...")

    base = os.path.dirname(__file__)

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

    print("Construyendo RAG...")
    coleccion = crear_indice_rag(carta_md)
    if not coleccion:
        return

    cliente = obtener_cliente()

    chatear(cliente, coleccion, horario_md)


if __name__ == "__main__":
    main()