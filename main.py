"""
Asistente de IA Local - Alchi (Versión RAG Real)
Utiliza Marker para procesar el PDF y ChromaDB para búsqueda semántica.
Conectado a LM Studio (API compatible con OpenAI)
"""

import os
import sys

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["USE_TORCH"] = "True"

from openai import OpenAI
import chromadb
from chromadb.utils import embedding_functions
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict

from config import Config
from reservas import GestorReservas


def procesar_carta_pdf():
    """
    Usa la librería Marker para convertir el PDF a Markdown con sistema de caché.
    Solo procesa el PDF si no existe el caché o si el PDF es más nuevo.
    """
    try:
        ruta_pdf = os.path.join(os.path.dirname(__file__), Config.ARCHIVO_PDF)
        ruta_cache = os.path.join(os.path.dirname(__file__), Config.ARCHIVO_CARTA_MD)

        if not os.path.exists(ruta_pdf):
            print(f"ADVERTENCIA: No se encontró el archivo {Config.ARCHIVO_PDF}")
            return ""

        if os.path.exists(ruta_cache):
            fecha_pdf = os.path.getmtime(ruta_pdf)
            fecha_cache = os.path.getmtime(ruta_cache)

            if fecha_cache > fecha_pdf:
                print("Cargando carta desde caché...")
                with open(ruta_cache, "r", encoding="utf-8") as f:
                    return f.read()

        print("Inicializando modelos de Marker...")
        converter = PdfConverter(artifact_dict=create_model_dict())

        print(f"Procesando '{Config.ARCHIVO_PDF}' con Marker...")
        rendered = converter(ruta_pdf)

        with open(ruta_cache, "w", encoding="utf-8") as f:
            f.write(rendered.markdown)

        return rendered.markdown

    except Exception as e:
        print(f"Error al procesar el PDF con Marker: {e}")
        return ""


def segmentar_texto(texto):
    """
    Divide el texto de la carta en fragmentos manejables.
    """
    print(f"Segmentando texto en fragmentos de {Config.CHUNK_SIZE} caracteres...")
    chunks = []
    inicio = 0

    while inicio < len(texto):
        fin = inicio + Config.CHUNK_SIZE

        if fin < len(texto):
            ultimo_salto = texto.rfind("\n", inicio, fin)
            if ultimo_salto != -1 and ultimo_salto > inicio + (Config.CHUNK_SIZE // 2):
                fin = ultimo_salto

        chunk = texto[inicio:fin].strip()
        if chunk:
            chunks.append(chunk)

        inicio = fin - Config.CHUNK_OVERLAP
        if inicio < 0:
            inicio = 0
        if inicio >= len(texto):
            break

    print(f"Se han generado {len(chunks)} fragmentos.")
    return chunks


def crear_indice_rag(markdown_carta):
    """
    Crea o recrea la colección de ChromaDB sin borrar manualmente la carpeta.
    Esto evita errores de bloqueo de archivos en Windows.
    """
    try:
        os.makedirs(Config.DB_PATH_VECTORIAL, exist_ok=True)

        cliente_db = chromadb.PersistentClient(path=Config.DB_PATH_VECTORIAL)

        modelo_embeddings = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        nombre_coleccion = "carta_restaurante"

        try:
            cliente_db.delete_collection(name=nombre_coleccion)
            print("Colección vectorial anterior eliminada.")
        except Exception:
            pass

        coleccion = cliente_db.create_collection(
            name=nombre_coleccion,
            embedding_function=modelo_embeddings
        )

        fragmentos = segmentar_texto(markdown_carta)
        ids = [f"chunk_{i}" for i in range(len(fragmentos))]

        coleccion.add(
            documents=fragmentos,
            ids=ids
        )

        print("Base de datos vectorial creada con éxito.")
        return coleccion

    except Exception as e:
        print(f"Error al crear la base de datos vectorial: {e}")
        return None


def buscar_contexto_relevante(coleccion, consulta_usuario):
    """
    Busca los fragmentos más relevantes en la base de datos vectorial.
    """
    if not coleccion:
        return ""

    try:
        resultados = coleccion.query(
            query_texts=[consulta_usuario],
            n_results=Config.TOP_K_RESULTS
        )

        contexto = "\n\n---\n\n".join(resultados["documents"][0])
        return contexto
    except Exception as e:
        print(f"Error en la recuperación RAG: {e}")
        return ""


def crear_system_prompt_dinamico(contexto_recuperado):
    """
    Crea el system prompt para consultas generales del restaurante.
    No se usa para confirmar reservas.
    """
    prompt = f"""Eres 'Alchi', el metre amable y profesional de L'Alchimie.

PERSONALIDAD:
- Sé hospitalario, cálido y educado.
- Respuestas breves y directas, máximo 3 frases.
- No uses rellenos técnicos ni paréntesis.

INFORMACIÓN DEL MENÚ:
{contexto_recuperado}

REGLAS IMPORTANTES:
- Si el usuario está preguntando por la carta, platos, precios o información del restaurante, responde con naturalidad.
- No inventes datos que no estén en el contexto.
- No confirmes reservas por tu cuenta.
"""
    return prompt


def inicializar_cliente():
    """
    Inicializa el cliente de OpenAI para LM Studio.
    """
    return OpenAI(
        base_url=Config.LM_STUDIO_BASE_URL,
        api_key=Config.LM_STUDIO_API_KEY
    )


def verificar_conexion(cliente):
    """
    Verifica disponibilidad de LM Studio.
    """
    try:
        cliente.chat.completions.create(
            model=Config.MODEL_NAME,
            messages=[{"role": "user", "content": "test"}],
            max_tokens=1
        )
        return True
    except Exception:
        return False


def chatear_con_alchi(cliente, coleccion_rag):
    """
    Bucle principal:
    - Reservas: manda el backend con respuesta controlada.
    - Carta y consultas generales: responde el LLM con RAG.
    """
    print("\n" + "=" * 60)
    print("  ASISTENTE ALCHI (IA + RAG + RESERVAS)")
    print("  Restaurante L'Alchimie Gastronomique")
    print("=" * 60)
    print("\nEscribe 'salir', 'exit' o 'quit' para terminar la conversación.\n")

    gestor_reservas = GestorReservas(llm_client=cliente, model_name=Config.MODEL_NAME)
    historial_mensajes = []

    while True:
        try:
            mensaje_usuario = input("Tú: ").strip()

            if mensaje_usuario.lower() in ["salir", "exit", "quit"]:
                print("\nHasta pronto.\n")
                break

            if not mensaje_usuario:
                continue

            es_turno_reserva = (
                gestor_reservas.hay_flujo_reserva_activo()
                or gestor_reservas.detectar_intencion(mensaje_usuario)
            )

            if es_turno_reserva:
                respuesta_controlada = gestor_reservas.procesar_turno(mensaje_usuario)

                print(f"\n[DEBUG] Datos: {gestor_reservas.datos}")
                print(f"[DEBUG] Estado: {gestor_reservas.estado}")
                print(f"[DEBUG] Acción: {gestor_reservas.ultima_accion}")
                print(f"[DEBUG] Sistema: {respuesta_controlada}\n")

                print(f"Alchi: {respuesta_controlada}\n")
                continue

            contexto_relevante = buscar_contexto_relevante(coleccion_rag, mensaje_usuario)
            system_prompt = crear_system_prompt_dinamico(contexto_relevante)

            mensajes_api = (
                [{"role": "system", "content": system_prompt}] +
                historial_mensajes +
                [{"role": "user", "content": mensaje_usuario}]
            )

            print("Alchi: ", end="", flush=True)
            respuesta = cliente.chat.completions.create(
                model=Config.MODEL_NAME,
                messages=mensajes_api,
                temperature=Config.TEMPERATURE,
                max_tokens=Config.MAX_TOKENS,
                stream=True
            )

            respuesta_completa = ""
            for chunk in respuesta:
                if chunk.choices[0].delta.content:
                    contenido = chunk.choices[0].delta.content
                    print(contenido, end="", flush=True)
                    respuesta_completa += contenido
            print("\n")

            historial_mensajes.append({"role": "user", "content": mensaje_usuario})
            historial_mensajes.append({"role": "assistant", "content": respuesta_completa})

            if len(historial_mensajes) > Config.MAX_MENSAJES_HISTORIAL:
                historial_mensajes = historial_mensajes[-Config.MAX_MENSAJES_HISTORIAL:]

        except KeyboardInterrupt:
            print("\n\nAdiós.")
            break
        except Exception as e:
            print(f"\nError: {e}")
            break


def main():
    print("\nIniciando sistema RAG Alchi...")

    markdown_carta = procesar_carta_pdf()
    if not markdown_carta:
        print("No se pudo procesar la carta. Abortando...")
        return

    print("Construyendo base de datos de conocimiento...")
    coleccion_rag = crear_indice_rag(markdown_carta)
    if not coleccion_rag:
        print("Error al crear el índice RAG.")
        return

    cliente = inicializar_cliente()
    if not verificar_conexion(cliente):
        print("\nError: No hay conexión con LM Studio.")
        return

    print("Todo listo. Iniciando chat.")
    chatear_con_alchi(cliente, coleccion_rag)


if __name__ == "__main__":
    main()