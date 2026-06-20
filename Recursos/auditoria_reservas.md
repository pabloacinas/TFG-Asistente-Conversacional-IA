# Auditoría del Flujo de Reservas y Modo Voz

He analizado el código relacionado con el modo voz y el flujo de reservas (`main.py`, `reservas.py` y los archivos en la carpeta `voice/`). A continuación, detallo los problemas encontrados y las mejoras propuestas, confirmando tus sospechas.

## 1. Interrupción de la Conversación (Voice Interruption)
Tienes razón en sospechar que no está funcionando correctamente.

* **El Problema:** En `voice_loop.py`, el flujo es totalmente secuencial: primero el sistema te escucha (`_transcribir_un_turno`), luego procesa la respuesta, y finalmente habla (`_hablar_respuesta`). Mientras el bot está hablando y reproduciendo audio (TTS), **el micrófono no está escuchando**. Por lo tanto, no hay forma física de interrumpirlo; cualquier cosa que digas mientras habla será ignorada.
* **La Solución:** Hay que implementar audio bidireccional (full-duplex). El micrófono (`MicrofonoStream`) debe estar escuchando continuamente en un hilo secundario (`background thread`). Si detecta voz del usuario mientras el TTS está reproduciendo, debe activar el `cancel_event` para detener la reproducción de audio instantáneamente e iniciar un nuevo turno.

## 2. Bloqueo en el Flujo de Reservas (Exit Reservation Flow)
Efectivamente, una vez que entras, no puedes salir.

* **El Problema:** En `reservas.py`, si `detectar_intencion` devuelve `True` o si falta algún dato, la variable `self.reserva_en_curso` se mantiene como `True`. No hay ninguna lógica para detectar cuándo el usuario se arrepiente o quiere cancelar (ej. "cancela", "ya no quiero", "olvídalo"). Al no haber salida, el bot entra en un bucle infinito pidiéndote el dato que falta.
* **La Solución:** Hay que ampliar la función `detectar_intencion()` (o crear una nueva `detectar_cancelacion()`) que busque frases clave para abortar la reserva. Si se detectan, se debe llamar a `self.reset()` (que devuelve el estado a `INACTIVO`) y responder al usuario confirmando la cancelación de la solicitud.

## 3. Extracción de Datos "Hardcodeada" (Hardcoded Regex vs Interpretación)
Tus sospechas sobre que la extracción está hardcodeada son correctas.

* **El Problema:** El código en `_extraer_personas_regex` se basa en Expresiones Regulares (Regex) muy específicas:
  `r"\b(?:mesa\s+para\s+(\d+)|para\s+(\d+)(?:\s+personas?|\s+comensales?)?|(\d+)\s*(?:personas?|comensales))\b"`
  Aunque este Regex *debería* capturar "para 5 personas", **solo busca dígitos (`\d+`)**. Si el sistema de voz a texto (STT) transcribe lo que has dicho como "para **cinco** personas" en lugar de "5", el Regex falla por completo.
  Además, cuando el Regex falla, entra en acción el LLM como plan de respaldo (`_extraer_datos_con_llm`). Sin embargo, el LLM puede devolver algo como `{"personas": "cinco"}`, y la función de limpieza `int("cinco")` fallará porque espera un número entero, devolviendo `None` y obligando al bot a volver a preguntar.
* **La Solución:**
  1. **Actualizar el Regex:** Añadir soporte para números en texto ("uno", "dos", "tres", "cuatro", "cinco", etc.) y convertirlos a enteros internamente.
  2. **Mejorar el Fallback del LLM:** Asegurarse de que el prompt del LLM o el parseador posterior puedan convertir palabras como "cinco" a enteros `5` antes de que falle.
  3. **Enfoque más semántico:** Reducir la dependencia del Regex manual y apoyarse más en el LLM para extraer la información usando *Function Calling* (herramientas estructuradas), que es mucho más fiable interpretando intenciones.

## 4. Mejoras para la Fluidez de la Conversación
Actualmente, las preguntas que hace el bot cuando le falta información (ej: *"¿Para cuántas personas sería la reserva?"*) están hardcodeadas en la función `generar_respuesta_controlada`. Esto hace que el bot suene robótico, repetitivo y poco fluido.

* **Mejora:** En lugar de devolver cadenas de texto estáticas, se puede inyectar el estado actual en el prompt del LLM. Por ejemplo: `"Al usuario le falta proporcionar el número de personas. Hazle una pregunta natural y corta para pedirle este dato, teniendo en cuenta el contexto de la charla"`. De esta manera, el bot variará sus respuestas y sonará mucho más humano e inteligente.

---
*Cuando estés listo, dímelo y podemos empezar a aplicar estas correcciones paso a paso.*
