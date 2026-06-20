# 🍴 Asistente Alchi v3.0 - RAG + Sistema Experto de Reservas

Asistente de IA local avanzado para el restaurante **L'Alchimie Gastronomique**. Combina búsqueda semántica en la carta (RAG) con un motor de gestión de reservas híbrido (Reglas + LLM).

## 🚀 Características Principales

### 🧠 Motor de Reservas Híbrido
- **Extracción Dual:** Utiliza expresiones regulares para capturas rápidas y llamadas especializadas al LLM para procesar lenguaje natural complejo, devolviendo datos estructurados en JSON.
- **Máquina de Estados:** Un flujo de conversación controlado (`GestorReservas`) que garantiza la recolección de todos los datos necesarios (fecha, hora, personas, nombre, teléfono) antes de confirmar.
- **Validación en Tiempo Real:** El sistema detecta incoherencias y solicita aclaraciones si los datos no se capturan correctamente.

### 🏢 Gestión de Sala Inteligente (SQLite)
- **Asignación Dinámica de Mesas:** Busca automáticamente la mesa que mejor se adapta al tamaño del grupo.
- **Control de Aforo y Tiempo:** Implementa bloqueos de 1 hora por reserva, verificando solapamientos de horarios para garantizar que nunca haya sobreventa.
- **Búsqueda de Alternativas:** Si no hay hueco a la hora solicitada, el sistema sugiere automáticamente los próximos horarios disponibles.

### 📖 RAG (Retrieval-Augmented Generation)
- **Marker-PDF:** Conversión de alta fidelidad de la carta PDF a Markdown con sistema de **caché persistente**.
- **ChromaDB:** Almacenamiento vectorial local para búsquedas semánticas precisas.
- **Contexto Optimizado:** Inyecta solo los fragmentos relevantes del menú en el prompt para respuestas rápidas y precisas.

## 🛠️ Requisitos e Instalación

1. **Python 3.10+** e instalación de dependencias:
   ```bash
   pip install -r requirements.txt
   ```
2. **Google Cloud (Vertex AI):** Proyecto con permisos para usar Gemini y credenciales configuradas en el entorno.
3. **Base de Datos:** El archivo SQLite se genera automáticamente. Para configurar las mesas, usa el script en `database/schema.sql`.

## 📁 Estructura del Proyecto

- `main.py`: Orquestador principal y bucle de chat.
- `reservas.py`: Lógica experta de conversación, extracción LLM y estados.
- `db_manager.py`: Controlador de base de datos, aforo y lógica de asignación de mesas.
- `config.py`: Configuración centralizada del sistema.
- `database/`: Scripts SQL y archivo `.db` persistente.
- `vector_db/`: Base de datos de vectores para la carta.

## 💡 Cómo interactuar
- **Consultas:** Pregunta sobre platos, ingredientes o precios ("¿Qué postres tenéis?", "¿Tenéis platos veganos?").
- **Reservas:** Inicia el flujo con frases naturales ("Quiero una mesa para mañana", "Reserva a nombre de Juan"). El sistema te guiará paso a paso.

---
*Desarrollado como parte del TFG - Sistema RAG y Gestión de Reservas con Vertex AI + Gemini.*
