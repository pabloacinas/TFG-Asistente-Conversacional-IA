# Arquitectura e Infraestructura del Proyecto Alchi

## 1. Resumen ejecutivo
El proyecto Alchi es un asistente conversacional para restaurante con dos modos de operación:

- Modo centralita simulada (entorno local de administración y prueba).
- Modo llamada real por telefonía (Twilio Voice + WebSocket de audio + ngrok).

La solución combina:

- Motor conversacional y de reservas (núcleo de negocio).
- Procesamiento de voz (STT y TTS en Google Cloud).
- Integración de telefonía real (Twilio Media Streams).
- Persistencia de reservas en SQLite.

El objetivo arquitectónico actual está orientado a demostrar una llamada real end-to-end sin necesidad de desplegar toda la infraestructura en nube.

## 2. Jerarquía actual del repositorio
Tras la reestructuración reciente, el proyecto queda organizado por responsabilidades:

- Servidor de centralita simulada: carpeta ServidorCentralita
- Servidor de telefonía real: carpeta ServidorTelefonía
- Núcleo funcional compartido: carpeta NucleoAlchi
- Pruebas: carpeta Tests
- Recursos y documentación: carpeta Recursos

Esta separación mejora mantenimiento, comprensión del código y despliegue selectivo por módulo.

## 3. Componentes principales

### 3.1 NucleoAlchi
Contiene la lógica transversal del sistema:

- Gestión de configuración global.
- Lógica conversacional y prompt principal.
- Motor experto de reservas y estados de diálogo.
- Persistencia y validación de disponibilidad.
- Integración de LLM y generación de respuestas.
- Canal SMS para confirmaciones.
- Utilidades de voz reutilizables (STT/TTS/splitter/audio local).

Este bloque es el corazón de la aplicación y lo consumen ambos servidores.

### 3.2 ServidorCentralita
Implementa la centralita web local para simulación y administración:

- Endpoints HTTP para alta de llamada simulada, envío de mensajes, colgado y logs.
- Streaming de respuestas por SSE al frontend web.
- Gestión de llamadas concurrentes con hilos y colas de entrada/salida.
- Interfaz web para pruebas funcionales sin dependencia de telefonía externa.

Uso recomendado:

- Probar diálogo y reglas de reserva en entorno controlado.
- Depurar lógica de negocio de forma rápida.

### 3.3 ServidorTelefonía
Implementa el flujo de llamada real con Twilio:

- Endpoint de webhook de voz que devuelve TwiML.
- Endpoint WebSocket para Media Streams bidireccional.
- Conversión y empaquetado de audio compatible con telefonía.
- Hilo por llamada para ejecutar escucha, comprensión, respuesta y síntesis.

Uso recomendado:

- Demo real desde móvil.
- Validación de latencia y experiencia de usuario en llamada real.

### 3.4 Tests
Incluye pruebas unitarias y funcionales del núcleo:

- Reservas y estado del gestor.
- Horarios y validaciones.
- Asignación de mesas y operaciones de base de datos.
- Pruebas de parsing/regex.

## 4. Flujo funcional de una llamada real

### 4.1 Flujo de alto nivel
1. Usuario llama al número de Twilio.
2. Twilio invoca el webhook de voz del servidor.
3. El webhook devuelve instrucciones TwiML para abrir stream de audio por WebSocket.
4. Twilio envía audio de entrada por eventos media.
5. El servidor procesa audio con STT y obtiene texto final.
6. El núcleo decide acción (reserva o respuesta general).
7. El texto de salida se sintetiza a audio.
8. El audio se devuelve a Twilio por WebSocket.
9. Twilio lo reproduce al usuario.

### 4.2 Adaptación de audio para telefonía
La telefonía opera con restricciones distintas al audio local. La solución adoptada usa:

- Entrada: audio mu-law a 8 kHz (formato propio de telefonía).
- STT configurado para consumir audio de telefonía.
- Salida TTS convertida y fragmentada en frames de 20 ms para Twilio.

Esto permite una integración estable sin requerir infraestructura compleja adicional.

## 5. Cambios recientes más relevantes

### 5.1 Integración real de telefonía
Se añadió el servidor de telefonía dedicado para permitir llamadas reales desde móvil con Twilio y ngrok.

Impacto:

- Pasa de simulación offline a demostración real end-to-end.
- Se conserva el núcleo de negocio existente.
- Se desacopla el canal de entrada de voz del canal de administración web.

### 5.2 Política de confirmación por código SMS
Se ajustó el flujo para reforzar seguridad y coherencia UX:

- El sistema ya no verbaliza el código de confirmación durante la llamada.
- El código llega únicamente por SMS.
- El usuario debe leer y dictar el código para confirmar la reserva.

Resultado:

- Menor exposición accidental de códigos.
- Flujo más realista en escenarios de llamada.

### 5.3 Reestructuración modular del proyecto
Se reorganizaron carpetas por dominios técnicos (centralita, telefonía, núcleo, tests, recursos).

Beneficios:

- Mejor separación de responsabilidades.
- Menor acoplamiento entre módulos.
- Más claridad para mantenimiento y defensa del proyecto.

### 5.4 Gestión de secretos
Se consolidó el uso de archivo local de secretos ignorado por control de versiones, evitando bloqueos por protección de secretos y reduciendo riesgo de filtración.

## 6. Infraestructura de ejecución actual

### 6.1 Entorno de desarrollo
- Sistema operativo: Windows.
- Runtime: Python 3.11.
- Ejecución local de servicios.

### 6.2 Servicios externos
- LLM y voz: Google Cloud (Gemini, STT, TTS).
- Telefonía y SMS: Twilio.
- Exposición pública temporal para webhook: ngrok.

### 6.3 Persistencia
- Base de datos SQLite para reservas y asignación de mesas.
- Adecuado para demo y baja concurrencia.

## 7. Puesta en marcha operativa

### 7.1 Centralita simulada
Ejecutar el núcleo en modo servidor para levantar el panel de administración local.

### 7.2 Telefonía real
1. Levantar servidor de telefonía.
2. Exponer puerto local con ngrok.
3. Configurar webhook de voz del número de Twilio apuntando al endpoint de voz.
4. Realizar llamada desde móvil.

