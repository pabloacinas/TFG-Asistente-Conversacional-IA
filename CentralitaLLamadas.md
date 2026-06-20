# Walkthrough: Centralita Telefónica Local Multi-Hilo

Hemos adaptado con éxito la aplicación para que funcione como un servicio en segundo plano (servidor HTTP multi-hilo local). Esto permite simular y recibir múltiples llamadas entrantes concurrentes. Cada llamada es atendida en su propio hilo de ejecución (`LlamadaThread`) con un estado de reservas y un historial conversacional completamente aislados.

---

## Cambios Realizados

### 1. Parámetros CLI y Control del Servidor
- **[main.py](file:///c:/Users/Usuario/Desktop/TFG/RAG/main.py):** Agregados argumentos CLI `--server`, `--port`, y `--host`. Cuando `--server` está activo, inicializa el cliente Gemini y los datos RAG de la carta/horario y levanta el servidor HTTP.

### 2. Servidor HTTP Multi-Hilo y Ciclo de Hilos de Llamada
- **[server.py](file:///c:/Users/Usuario/Desktop/TFG/RAG/server.py):**
  - Implementa la clase de hilos `LlamadaThread` que hereda de `threading.Thread`. Cada hilo contiene su propio `GestorReservas` y cola de entrada/salida de mensajes.
  - Ofrece desconexión automática por inactividad tras 5 minutos de silencio.
  - Expone endpoints REST/SSE para la centralita:
    - `/api/llamadas` (GET / POST)
    - `/api/llamadas/<id>/mensaje` (POST con streaming SSE de respuestas del LLM)
    - `/api/llamadas/<id>/colgar` (POST para terminar el hilo)
    - `/api/logs` (GET para monitorizar eventos)

### 3. Dashboard Web Premium y Lógica de Simulación
- **[web/index.html](file:///c:/Users/Usuario/Desktop/TFG/RAG/web/index.html):** Maquetación responsiva con estilo de centralita/consola de control.
- **[web/style.css](file:///c:/Users/Usuario/Desktop/TFG/RAG/web/style.css):** Estilos oscuros premium, glassmorphism e indicadores de estado animados (pulsación de llamada, ondas de sonido al hablar Alchi).
- **[web/app.js](file:///c:/Users/Usuario/Desktop/TFG/RAG/web/app.js):** Lógica interactiva que utiliza lectores de streams de `Fetch` para decodificar las respuestas SSE en tiempo real y gestiona las llamadas concurrentes.

---

## Pruebas y Verificación

### Validación de Sintaxis
Compilación correcta sin errores de sintaxis en `main.py` y `server.py`:
`python -m py_compile main.py server.py`

### Verificación End-to-End
Se inició el servidor y se realizó una prueba completa usando un subagente de navegación:
1. Simulación exitosa de la llamada de Carlos Gómez (`+34600111222`).
2. Creación inmediata del hilo dedicado en segundo plano.
3. Envío del mensaje y streaming en tiempo real de la respuesta de Alchi acerca del horario del restaurante.
4. Desconexión correcta y terminación del hilo tras colgar.

### Grabación de la Simulación en el Dashboard
A continuación se muestra el flujo interactivo de la prueba de centralita:

![Demostración de la Centralita Local](/C:/Users/Usuario/.gemini/antigravity-ide/brain/0ccb5b42-f4fa-4ea5-b9d0-21a14fc91bbd/test_centralita_flow_1781216835346.webp)
