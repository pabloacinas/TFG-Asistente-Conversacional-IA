# 🧠 Por Qué el Asistente "Olvida" y "Recuerda"

## Escenario Real

### Situación 1: Hablando de Otros Temas
```
[System Prompt: "Eres Alchi del restaurante..."]  ← Siempre presente
Turno 1: "¿Qué opinas del clima?"
Turno 2: "Háblame de matemáticas"
Turno 3: "¿Qué es la fotosíntesis?"
```

**¿Qué ve el modelo?**
- ✅ System Prompt dice: "Eres Alchi del restaurante"
- ❌ PERO los últimos 3 mensajes NO mencionan el restaurante
- ⚖️ **El modelo balancea**: "Debo ser Alchi, pero estamos hablando de otros temas"
- 🎭 **Resultado**: Puede responder de forma más genérica y "olvidar" su personaje

---

### Situación 2: Vuelves a Hablar del Restaurante
```
[System Prompt: "Eres Alchi del restaurante..."]  ← Siempre presente
Turno 3: "¿Qué es la fotosíntesis?"
Turno 4: "¿Qué platos de pescado tenéis?"  ← TRIGGER
```

**¿Qué ve el modelo ahora?**
- ✅ System Prompt dice: "Eres Alchi del restaurante"
- ✅ El mensaje RECIENTE menciona el restaurante
- 🎯 **Alineación perfecta**: System + contexto reciente = restaurante
- 🎭 **Resultado**: "¡Ah sí! Soy Alchi del restaurante" (vuelve al personaje)

---

## 🔍 La Realidad Técnica

### NO es que "olvide" la información
- El System Prompt con la carta **NUNCA** se elimina
- **SIEMPRE** está en la posición [0] del historial

### Es un problema de "atención" del modelo
Los LLMs usan un mecanismo llamado **attention** que funciona así:

```
Peso de Atención = Relevancia × Posición

System Prompt:     Relevancia ALTA × Posición FIJA    = Influencia CONSTANTE
Mensaje Reciente:  Relevancia ALTA × Posición CERCANA = Influencia MUY ALTA
Mensaje Antiguo:   Relevancia BAJA × Posición LEJANA  = Influencia BAJA
```

### Cuando hablas de otros temas
```
System: "Eres Alchi"      [Peso: 30%]
Reciente: "fotosíntesis"  [Peso: 70%]  ← DOMINANTE
────────────────────────────────────────
Resultado: Responde de forma más genérica
```

### Cuando vuelves al restaurante
```
System: "Eres Alchi"      [Peso: 30%]  ← SE ALINEA
Reciente: "platos pescado" [Peso: 70%]  ← SE ALINEA
────────────────────────────────────────
Resultado: REFUERZO TOTAL = Alchi al 100%
```

---

## 💡 Analogía Humana

Es como si tuvieras un compañero de trabajo:

**Situación A**: Estás en la oficina (restaurante), hablas de trabajo  
→ Actúa como tu colega profesional ✅

**Situación B**: Salen a tomar café y hablan de fútbol  
→ Actúa más casual, menos "rol profesional" ⚽

**Situación C**: Vuelven a la oficina y mencionas un proyecto  
→ Vuelve inmediatamente al modo profesional 💼

**NO olvidó que es tu colega**, solo ajustó su comportamiento al contexto.

---

## 🔧 Soluciones si Quieres que SIEMPRE Sea Alchi

### Opción 1: System Prompt Más Fuerte
```python
prompt = """Eres 'Alchi', EXCLUSIVAMENTE un asistente del restaurante.

IMPORTANTE: Debes SIEMPRE mantener tu rol de Alchi.
- Si te preguntan temas no relacionados al restaurante, redirige la conversación
- Ejemplo: "Soy Alchi, del restaurante. Prefiero hablar sobre nuestro menú..."
"""
```

### Opción 2: Recordatorio Periódico
Cada 3 turnos, inyectar automáticamente un mensaje como:
```python
{"role": "system", "content": "Recuerda: Eres Alchi del restaurante L'Alchimie"}
```

### Opción 3: Validar Preguntas Off-Topic
```python
if not es_relacionado_con_restaurante(mensaje_usuario):
    respuesta = "Como Alchi del restaurante L'Alchimie, prefiero ayudarte con consultas sobre nuestro menú..."
```

---

## 📊 Resumen Visual

```
┌─────────────────────────────────────────┐
│  HISTORIAL EN MEMORIA                  │
├─────────────────────────────────────────┤
│ [0] 🔧 SYSTEM: Eres Alchi...           │ ← SIEMPRE AQUÍ
│ [1] 👤 USER: ¿clima?                   │
│ [2] 🤖 ASST: [respuesta genérica]      │
│ [3] 👤 USER: ¿matemáticas?             │
│ [4] 🤖 ASST: [respuesta genérica]      │
└─────────────────────────────────────────┘
        ↓ Contexto reciente domina
     Se "olvida" del personaje


┌─────────────────────────────────────────┐
│  HISTORIAL EN MEMORIA                  │
├─────────────────────────────────────────┤
│ [0] 🔧 SYSTEM: Eres Alchi...           │ ← SIEMPRE AQUÍ
│ [1] 👤 USER: ¿matemáticas?             │
│ [2] 🤖 ASST: [respuesta genérica]      │
│ [3] 👤 USER: ¿platos de pescado?       │ ← TRIGGER
│ [4] 🤖 ASST: [modo Alchi 100%]         │
└─────────────────────────────────────────┘
        ↓ System + Reciente alineados
     "Recuerda" su rol perfectamente
```

---

## ✅ Conclusión

**NO hay olvido real** - Es el comportamiento natural de los LLMs:
- El System Prompt SIEMPRE está presente
- El modelo ajusta su tono según el contexto RECIENTE
- Cuando el contexto vuelve al tema del restaurante, el System Prompt se "reactiva"

Es una característica, no un bug. Para conversaciones más "fieles" al personaje, necesitarías implementar las soluciones mencionadas arriba.
