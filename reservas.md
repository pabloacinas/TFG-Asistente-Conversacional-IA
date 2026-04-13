# Sistema de Reservas — Resumen Completo

## 1. Visión General

El sistema de reservas está diseñado con una arquitectura **híbrida y robusta**:

- 🧠 **LLM (IA)** → interpreta lenguaje natural
- ⚙️ **Backend (Python)** → gestiona lógica real y estado
- 🗄️ **Base de datos** → fuente de verdad (mesas, reservas)

👉 Principio clave:
> El LLM **nunca decide ni confirma reservas**. Solo interpreta y comunica.

---

## 2. Flujo General de una Reserva

1. Usuario envía mensaje
2. Se extraen datos (regex + LLM)
3. Se actualiza estado
4. Se valida disponibilidad (BD)
5. Se solicita información faltante
6. Se confirma reserva (solo backend)

---

## 3. Datos necesarios

Para completar una reserva se necesitan:

- 📅 Fecha
- 🕐 Hora
- 👥 Número de personas
- 👤 Nombre
- 📞 Teléfono

---

## 4. Máquina de Estados

El sistema funciona como una máquina de estados:

| Estado | Descripción |
|------|------------|
| `INACTIVO` | No hay reserva en curso |
| `PIDIENDO_FECHA` | Falta fecha |
| `PIDIENDO_HORA` | Falta hora |
| `PIDIENDO_PERSONAS` | Falta número de personas |
| `COMPROBANDO_DISPONIBILIDAD` | Se consulta la BD |
| `PIDIENDO_NOMBRE` | Hay mesa, falta nombre |
| `PIDIENDO_TELEFONO` | Falta teléfono |
| `OFRECIENDO_ALTERNATIVAS` | No hay disponibilidad |
| `LISTO` | Se puede confirmar |

---

## 5. Extracción de datos

### 5.1 Regex (rápido y fiable)
Detecta:
- Teléfonos
- Horas claras (`14:00`)
- Personas (`para 4`)

### 5.2 LLM (flexible)
Interpreta:
- “mañana a la hora de comer”
- “somos tres”
- “mi pareja y yo”
- “sobre las 2 y media”

👉 El LLM devuelve JSON estructurado que el backend valida.

---

## 6. Validación de negocio

### 6.1 Horario de cocina

El sistema valida que la reserva esté dentro del horario:

Ejemplo:
- Comida → 13:00–16:00
- Cena → 20:30–23:30

❌ Fuera de ese horario → reserva rechazada

---

### 6.2 Disponibilidad de mesas

Se usa lógica de solapamiento:

```sql
hora_inicio < nueva_hora_fin AND hora_fin > nueva_hora_inicio

Esto garantiza que:

- no haya dos reservas en la misma mesa al mismo tiempo  
- se respeten los turnos de 1 hora  

---

## 7. Asignación de mesa

Cuando hay disponibilidad:

- Se busca una mesa con capacidad ≥ personas  
- Se prioriza la mesa más pequeña posible (optimización)  
- Se asigna temporalmente hasta confirmar  

**Resultado:**

- mesa_id asignado  
- flujo continúa a nombre/teléfono  

---

## 8. Casos posibles

### 8.1 Caso ideal

- Usuario da datos completos o progresivos  
- Hay disponibilidad  
- Se recogen nombre y teléfono  
- Se guarda la reserva  

✔ **Resultado:** reserva confirmada  

---

### 8.2 Datos incompletos

**Ejemplo:**

> “quiero reservar”

→ el sistema va pidiendo:

- hora  
- personas  
- etc.  

---

### 8.3 Datos desordenados

**Ejemplo:**

> “somos 4 mañana a las 15”

✔ El orden no importa  
✔ Se extraen todos los datos correctamente  

---

### 8.4 Lenguaje natural

**Ejemplo:**

> “mañana sobre las dos, venimos tres”

✔ El LLM interpreta  
✔ Backend valida  

---

### 8.5 Sin disponibilidad

- No hay mesa suficiente  
- o hay conflicto de horarios  

**Resultado:**

- estado → `OFRECIENDO_ALTERNATIVAS`  
- se proponen nuevas horas  

---

### 8.6 Cambio de datos

**Ejemplo:**

> “mejor a las 15”

✔ Se resetea disponibilidad  
✔ Se recalcula todo  

---

### 8.7 Hora fuera de horario

**Ejemplo:**

> “a las 3 de la mañana”

❌ Se rechaza directamente  
✔ No se consulta BD  

---

### 8.8 Datos inválidos

**Ejemplo:**

- teléfono incorrecto  
- nombre ambiguo (“sí”)  

✔ Se ignoran  
✔ Se vuelven a pedir  

---

### 8.9 Interrupciones

**Ejemplo:**

> “olvídalo”

✔ Se puede resetear el flujo  

---

### 8.10 Seguridad crítica

✔ El sistema nunca confirma reservas sin backend  
✔ Evita alucinaciones del LLM  

---

## 9. Alternativas de horario

Cuando no hay disponibilidad:

- Se buscan horarios cercanos  
- Solo hacia adelante  
- Intervalos de 30 minutos  
- Máximo 3 opciones  

**Ejemplo:**

- 14:30  
- 15:00  
- 15:30  

---

## 10. Base de datos

### Tablas principales

#### mesas
- id  
- capacidad  

#### reservas
- fecha  
- hora  
- personas  
- nombre  
- teléfono  

#### reservas_mesas
- mesa_id  
- reserva_id  
- fecha  
- hora_inicio  
- hora_fin  

---

## 14. Limitaciones actuales

- Horario de cocina hardcodeado  
- No detecta reservas duplicadas  
- No permite modificar reservas  
- No permite cancelar reservas  
- No gestiona múltiples mesas por reserva  
- No optimiza agrupación de mesas grandes  