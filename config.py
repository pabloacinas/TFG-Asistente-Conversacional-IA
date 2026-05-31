import os

"""
Configuración del Asistente Alchi
Parámetros del sistema y conexión con Vertex AI + Gemini
"""


class Config:
    """
    Clase de configuración para el asistente Alchi.
    Centraliza todos los parámetros configurables.
    """
    
    # =========================
    # GOOGLE CLOUD / GEMINI
    # =========================
    GCP_PROJECT_ID = "project-46852ceb-4e38-4026-ab4"
    GCP_LOCATION = "us-central1"
    GEMINI_MODEL = "gemini-2.5-flash"

    # =========================
    # CONFIGURACIÓN MODELO
    # =========================
    TEMPERATURE = 0.7
    MAX_TOKENS = 800
    
    # Ventana deslizante del historial.
    # Esta limitación era clave con modelos locales pequeños; con Gemini puede
    # relajarse si se quiere priorizar memoria conversacional sobre coste/latencia.
    MAX_MENSAJES_HISTORIAL = 20
    
    # Parámetros de RAG. El tamaño de chunk y el reranking se mantuvieron por
    # calidad de recuperación, aunque ya no son una restricción dura de contexto.
    CHUNK_SIZE = 800        # Tamaño máximo de cada fragmento (caracteres)
    CHUNK_OVERLAP = 100      # Solapamiento entre fragmentos para no perder contexto
    TOP_K_RESULTS = 4        # Número de fragmentos más relevantes a recuperar por consulta
    DB_PATH_VECTORIAL = "vector_db"    # Directorio de la DB vectorial
    
    # Configuración de Base de Datos Real (SQLite)
    DB_SQLITE_PATH = os.path.join("database", "alchi_restaurante.db")
    SCHEMA_SQL_PATH = os.path.join("database", "schema.sql")
    CAPACIDAD_MAX_POR_HORA = 20  # Aforo máximo del restaurante por turno
    
    # Archivos
    ARCHIVO_PDF = "Carta de Alchi Burger.pdf"
    ARCHIVO_CARTA_MD = "carta_cache.md"  # Archivo de caché para el texto extraído
    ARCHIVO_HORARIO_PDF = "horario.pdf"
    ARCHIVO_HORARIO_MD = "horario_cache.md"
    
    # Configuración de interfaz
    MOSTRAR_INFO_CONTEXTO = True  # Mostrar información del contexto en cada turno

    # =========================
    # VOZ (STT + TTS)
    # =========================
    # Speech-to-Text
    STT_LANGUAGE = "es-ES"
    STT_MODEL = "latest_long"            # alternativa: "chirp_2" para baja latencia
    STT_SAMPLE_RATE = 16000              # Hz, mono int16 desde el micro

    # Text-to-Speech (Chirp3-HD streaming)
    TTS_LANGUAGE = "es-ES"
    TTS_VOICE = "es-ES-Chirp3-HD-Leda"  # fallback automático a Neural2 si no disponible
    TTS_VOICE_FALLBACK = "es-ES-Neural2-C"
    TTS_SAMPLE_RATE = 24000              # Chirp3-HD usa 24kHz LINEAR16

    # Comportamiento conversacional
    VOZ_END_UTTERANCE_SILENCE_MS = 800   # silencio para considerar fin de turno del usuario
    VOZ_BARGE_IN_ENABLED = True          # cortar TTS si el usuario empieza a hablar
    VOZ_FRASE_MIN_CHARS = 40             # tamaño mínimo de buffer para flushear frase sin puntuación
    VOZ_SALUDO_INICIAL = "Hola, soy Alchi de L'Alchimie. ¿En qué puedo ayudarle?"
