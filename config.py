"""
Configuración del Asistente Alchi
Parámetros de conexión a LM Studio y configuración del sistema
"""


class Config:
    """
    Clase de configuración para el asistente Alchi.
    Centraliza todos los parámetros configurables.
    """
    
    # Configuración de LM Studio
    LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
    LM_STUDIO_API_KEY = "sk-lm-jFlKn5OW:UyVY24IrqfspZCJCGFru"
    
    # Configuración del modelo
    MODEL_NAME = "local-model"  # LM Studio detecta automáticamente el modelo cargado
    TEMPERATURE = 0.7
    MAX_TOKENS = 800
    
    # Configuración de ventana deslizante (Sliding Window)
    # Para Gemma3-4b con context window de 3,072 tokens:
    # - System Prompt (carta): ~1,200 tokens
    # - MAX_TOKENS (respuesta): 800 tokens
    # - Disponible para historial: ~1,070 tokens (~5 turnos seguros)
    MAX_MENSAJES_HISTORIAL = 10  # Número máximo de mensajes (sin contar System Prompt)
    # Esto equivale a 5 pares de pregunta-respuesta (ÓPTIMO para tu modelo)
    
    # Archivos
    ARCHIVO_CARTA = "CartaRestaurantePruebasRAG.txt"
    
    # Configuración de interfaz
    MOSTRAR_INFO_CONTEXTO = True  # Mostrar información del contexto en cada turno
