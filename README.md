# 🍴 Asistente Alchi - Restaurante L'Alchimie Gastronomique

Asistente de IA local que se conecta a **LM Studio** para responder consultas sobre el menú del restaurante.

## 📋 Requisitos Previos

1. **Python 3.8 o superior** instalado
2. **LM Studio** descargado y ejecutándose
3. Un modelo cargado en LM Studio
4. El servidor local de LM Studio activo en `http://localhost:1234`

## 🚀 Instalación

1. Instala las dependencias:
```bash
pip install -r requirements.txt
```

O instala directamente:
```bash
pip install openai
```

## 🎯 Configuración de LM Studio

1. Abre LM Studio
2. Carga un modelo (recomendado: cualquier modelo GPT-like)
3. Ve a la pestaña "Server" o "Local Server"
4. Inicia el servidor local (debe estar en puerto 1234)
5. Verifica que muestre: `Server running on http://localhost:1234`

## ▶️ Uso

Ejecuta el asistente:
```bash
python main.py
```

## 💬 Ejemplo de Conversación

```
Tú: Hola, ¿qué platos de pescado tenéis?

Alchi: ¡Bienvenido a L'Alchimie! Tenemos varias opciones de pescado sostenible:
- Lubina Salvaje a la Sal (28€)
- Bacalao Skrei en Tempura (26,50€)
- Arroz Meloso de Bogavante (32€/persona, mínimo 2 personas)
...
```

## 🛑 Comandos

- `salir`, `exit`, `quit`: Termina la conversación
- `Ctrl+C`: Interrumpe el programa

## 🔧 Solución de Problemas

### Error: "No se puede conectar con LM Studio"
- Verifica que LM Studio esté abierto
- Asegúrate de que has cargado un modelo
- Confirma que el servidor local está activo

### Error: "No se encontró CartaRestaurantePruebasRAG.txt"
- El archivo debe estar en la misma carpeta que `main.py`

## 📁 Estructura del Proyecto

```
RAG/
├── main.py                          # Programa principal
├── config.py                        # Configuración (API, parámetros)
├── CartaRestaurantePruebasRAG.txt  # Carta del restaurante (contexto)
├── requirements.txt                 # Dependencias
└── README.md                        # Este archivo
```

## 🔑 Configuración

La configuración se encuentra en [config.py](config.py). Puedes personalizar:

```python
# Conexión a LM Studio
LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
LM_STUDIO_API_KEY = "sk-lm-jFlKn5OW:UyVY24IrqfspZCJCGFru"

# Parámetros del modelo
TEMPERATURE = 0.7
MAX_TOKENS = 800

# Ventana deslizante (memoria de conversación)
MAX_MENSAJES_HISTORIAL = 6  # 3 pares pregunta-respuesta

# Interfaz
MOSTRAR_INFO_CONTEXTO = True  # Mostrar contador de contexto
```

## ✨ Características

✅ Lectura automática de la carta del restaurante  
✅ Inyección del contexto en el System Prompt  
✅ Streaming de respuestas en tiempo real  
✅ Manejo de errores si LM Studio está apagado  
✅ Interfaz de chat por consola  
✅ Historial de conversación con ventana deslizante  
✅ **Contador de contexto en tiempo real** 📊  
✅ **Configuración centralizada** en archivo separado  

---

Desarrollado como parte del TFG - Asistente IA con RAG
