import json
import os
import re
from datetime import datetime, timedelta

from db_manager import DBManager
from config import Config


class ServicioReservasReal:
    def __init__(self):
        base_dir = os.path.dirname(__file__)
        db_path = os.path.join(base_dir, Config.DB_SQLITE_PATH)
        schema_path = os.path.join(base_dir, Config.SCHEMA_SQL_PATH)
        self.db = DBManager(db_path, schema_path)

    def normalizar_fecha(self, fecha_str):
        try:
            return datetime.strptime(fecha_str, "%d/%m/%Y").strftime("%Y-%m-%d")
        except Exception:
            return fecha_str


class GestorReservas:
    def __init__(self, llm_client=None, model_name=None):
        self.servicio = ServicioReservasReal()
        self.llm_client = llm_client
        self.model_name = model_name
        self.reset()

    def reset(self):
        self.reserva_en_curso = False
        self.estado = "INACTIVO"
        self.datos = {
            "fecha": None,
            "hora": None,
            "personas": None,
            "nombre": None,
            "telefono": None,
            "mesa_id": None
        }
        self.disponibilidad_comprobada = False
        self.alternativas = []
        self.ultima_respuesta_sistema = ""
        self.ultima_accion = None

    def es_hora_en_horario_cocina(self, hora_str):
        """
        Valida si una hora está dentro de los turnos de comida (13:00-15:30) o cena (20:30-23:00).
        """
        try:
            h, m = map(int, hora_str.split(":"))
            total_minutos = h * 60 + m

            # Comida: 13:00 (780 min) a 15:30 (930 min)
            comida = (13 * 60 <= total_minutos <= 15 * 60 + 30)
            # Cena: 20:30 (1230 min) a 23:00 (1380 min)
            cena = (20 * 60 + 30 <= total_minutos <= 23 * 60)

            return comida or cena
        except Exception:
            return False

    def es_fecha_valida(self, fecha_str):
        """
        Comprueba si el restaurante está abierto ese día (cerrado lunes=0 y martes=1).
        """
        try:
            # fecha_str es "dd/mm/yyyy"
            dt = datetime.strptime(fecha_str, "%d/%m/%Y")
            # weekday(): Monday=0, Tuesday=1, ...
            return dt.weekday() not in [0, 1]
        except Exception:
            return True

    def detectar_intencion(self, mensaje):
        msg = mensaje.lower().strip()
        palabras_clave = [
            "reservar",
            "reserva",
            "mesa",
            "quiero reservar",
            "hacer una reserva",
            "tenéis mesa",
            "tienen mesa",
            "hay sitio",
            "hay hueco"
        ]
        return any(palabra in msg for palabra in palabras_clave)

    def hay_flujo_reserva_activo(self):
        return self.reserva_en_curso or self.estado != "INACTIVO"

    def procesar_turno(self, mensaje):
        self.extraer_datos(mensaje, self.estado)
        self.actualizar_estado()

        # 1. Validar si el día está abierto (Lunes/Martes cerrado)
        if self.datos["fecha"] and not self.es_fecha_valida(self.datos["fecha"]):
            self.ultima_respuesta_sistema = (
                "Lo siento, el restaurante permanece cerrado los lunes y martes. "
                "¿Qué otro día te vendría bien?"
            )
            self.datos["fecha"] = None
            self._reset_disponibilidad()
            self.estado = "PIDIENDO_FECHA"
            return self.ultima_respuesta_sistema

        # 2. Validar si la hora está en horario de cocina
        if self.datos["hora"] and not self.es_hora_en_horario_cocina(self.datos["hora"]):
            self.ultima_respuesta_sistema = (
                f"Lo siento, la cocina está abierta de 13:00 a 15:30 y de 20:30 a 23:00. "
                f"¿A qué hora prefieres reservar?"
            )
            self.datos["hora"] = None  # Resetear para pedir de nuevo
            self.actualizar_estado()
            return self.ultima_respuesta_sistema

        if self.estado == "COMPROBANDO_DISPONIBILIDAD":
            self.comprobar_disponibilidad()
            self.actualizar_estado()

        if self.estado == "LISTO":
            ok = self.servicio.db.crear_reserva_con_mesa(
                self.servicio.normalizar_fecha(self.datos["fecha"]),
                self.datos["hora"],
                self.datos["personas"],
                self.datos["nombre"],
                self.datos["telefono"],
                self.datos["mesa_id"]
            )

            if ok:
                respuesta = (
                    f"Reserva confirmada para {self.datos['personas']} personas "
                    f"el {self.datos['fecha']} a las {self.datos['hora']}, "
                    f"a nombre de {self.datos['nombre']}."
                )
                self.ultima_respuesta_sistema = respuesta
                self.ultima_accion = "RESERVA_CONFIRMADA"
                self.reset()
                return respuesta

            self.ultima_respuesta_sistema = (
                "Ha ocurrido un problema al guardar la reserva. "
                "Por favor, indíqueme de nuevo la hora y el número de personas."
            )
            self.ultima_accion = "ERROR_GUARDADO"
            self._reset_disponibilidad()
            self.actualizar_estado()
            return self.ultima_respuesta_sistema

        respuesta = self.generar_respuesta_controlada()
        self.ultima_respuesta_sistema = respuesta
        print("DEBUG FECHA:", self.datos["fecha"])
        return respuesta

    def extraer_datos(self, mensaje, estado_actual):
        msg_original = mensaje.strip()
        msg = msg_original.lower().strip()

        if self.detectar_intencion(msg):
            self.reserva_en_curso = True

        self._extraer_fecha_regex(msg)
        self._extraer_hora_regex(msg, estado_actual)
        self._extraer_personas_regex(msg, estado_actual)
        self._extraer_telefono_regex(msg)
        self._extraer_nombre_regex(msg_original, estado_actual)

        if self._deberia_usar_llm_extractor():
            extraidos = self._extraer_datos_con_llm(msg_original, estado_actual)
            self._fusionar_datos_extraidos(extraidos)

        if (
            self.datos["fecha"]
            or self.datos["hora"]
            or self.datos["personas"]
            or self.datos["nombre"]
            or self.datos["telefono"]
        ):
            self.reserva_en_curso = True
            if self.detectar_intencion(msg):
                self.reserva_en_curso = True

    def _deberia_usar_llm_extractor(self):
        if not self.llm_client or not self.model_name:
            return False

        if not self.reserva_en_curso and self.estado == "INACTIVO":
            return False

        campos_principales = [self.datos["fecha"], self.datos["hora"], self.datos["personas"]]
        if any(valor is None for valor in campos_principales):
            return True

        if self.estado in ["PIDIENDO_NOMBRE", "PIDIENDO_TELEFONO"]:
            return True

        return False

    def _extraer_datos_con_llm(self, mensaje, estado_actual):
        hoy = datetime.now().strftime("%d/%m/%Y")

        system_prompt = f"""
Eres un extractor de datos para reservas de restaurante.

Tu trabajo es leer el mensaje del cliente y devolver SOLO un JSON válido con este esquema exacto:

{{
  "intencion_reserva": true o false o null,
  "fecha": "dd/mm/yyyy" o null,
  "hora": "HH:MM" o null,
  "personas": numero o null,
  "nombre": "texto" o null,
  "telefono": "9 digitos" o null
}}

Reglas:
- No inventes datos.
- Si algo no está claro, devuelve null.
- Si el cliente dice "hoy", usa {hoy}.
- Si dice "mañana", usa la fecha de mañana respecto a {hoy}.
- La hora debe ir en formato HH:MM.
- Interpretaras cualquier hora como horario de restaurante (PM), por ejemplo "a las 8" → "20:00".
- Si el mensaje parece contener solo un nombre, devuélvelo en "nombre".
- Si contiene un teléfono español, devuélvelo sin espacios.
- Devuelve solo JSON, sin explicaciones, sin bloques markdown.
"""

        user_prompt = f"""
Estado actual: {estado_actual}
Datos ya capturados:
- fecha: {self.datos["fecha"]}
- hora: {self.datos["hora"]}
- personas: {self.datos["personas"]}
- nombre: {self.datos["nombre"]}
- telefono: {self.datos["telefono"]}

Mensaje del cliente:
{mensaje}
"""

        try:
            respuesta = self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt.strip()},
                    {"role": "user", "content": user_prompt.strip()}
                ],
                temperature=0,
                max_tokens=200
            )

            contenido = respuesta.choices[0].message.content.strip()
            contenido = self._limpiar_json_llm(contenido)
            data = json.loads(contenido)

            if not isinstance(data, dict):
                return {}

            return data

        except Exception:
            return {}

    def _limpiar_json_llm(self, contenido):
        contenido = contenido.strip()

        if contenido.startswith("```"):
            contenido = re.sub(r"^```(?:json)?", "", contenido.strip(), flags=re.IGNORECASE).strip()
            contenido = re.sub(r"```$", "", contenido.strip()).strip()

        inicio = contenido.find("{")
        fin = contenido.rfind("}")
        if inicio != -1 and fin != -1 and fin > inicio:
            contenido = contenido[inicio:fin + 1]

        return contenido

    def _fusionar_datos_extraidos(self, extraidos):
        if not extraidos:
            return

        if extraidos.get("intencion_reserva") is True:
            self.reserva_en_curso = True

        nueva_fecha = self._normalizar_fecha_extraida(extraidos.get("fecha"))
        nueva_fecha = None
        nueva_hora = self._normalizar_hora_extraida(extraidos.get("hora"))
        nuevas_personas = self._normalizar_personas_extraidas(extraidos.get("personas"))
        nuevo_nombre = self._normalizar_nombre_extraido(extraidos.get("nombre"))
        nuevo_telefono = self._normalizar_telefono_extraido(extraidos.get("telefono"))

        if nueva_fecha and not self.datos["fecha"]:
            self.datos["fecha"] = nueva_fecha
            self._reset_disponibilidad()

        if nueva_hora and nueva_hora != self.datos["hora"]:
            self.datos["hora"] = nueva_hora
            self._reset_disponibilidad()

        if nuevas_personas and nuevas_personas != self.datos["personas"]:
            self.datos["personas"] = nuevas_personas
            self._reset_disponibilidad()

        if nuevo_nombre and not self.datos["nombre"]:
            self.datos["nombre"] = nuevo_nombre

        if nuevo_telefono and not self.datos["telefono"]:
            self.datos["telefono"] = nuevo_telefono

    def _normalizar_fecha_extraida(self, fecha):
        if not fecha or not isinstance(fecha, str):
            return None

        fecha = fecha.strip()

        for formato in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(fecha, formato)
                return dt.strftime("%d/%m/%Y")
            except ValueError:
                continue

        return None

    def _normalizar_hora_extraida(self, hora):
        if not hora or not isinstance(hora, str):
            return None

        hora = hora.strip()
        match = re.fullmatch(r"(\d{1,2}):(\d{2})", hora)
        if not match:
            return None

        h = int(match.group(1))
        m = int(match.group(2))

        if h > 23 or m > 59:
            return None

        return f"{h:02d}:{m:02d}"

    def _normalizar_personas_extraidas(self, personas):
        if personas is None:
            return None

        try:
            valor = int(personas)
            if valor <= 0:
                return None
            return valor
        except Exception:
            return None

    def _normalizar_nombre_extraido(self, nombre):
        if not nombre or not isinstance(nombre, str):
            return None

        nombre = self._limpiar_nombre(nombre)
        return nombre

    def _normalizar_telefono_extraido(self, telefono):
        if not telefono:
            return None

        telefono = re.sub(r"\D", "", str(telefono))
        if len(telefono) == 9:
            return telefono

        return None

    def _extraer_fecha_regex(self, msg):
        dias_semana = {
            "lunes": 0,
            "martes": 1,
            "miercoles": 2,
            "miércoles": 2,
            "jueves": 3,
            "viernes": 4,
            "sabado": 5,
            "sábado": 5,
            "domingo": 6
        }
        # CASO: "lunes que viene", "martes que viene", etc.
        for nombre_dia, num_dia in dias_semana.items():

    # "próximo jueves", "proximo jueves", "jueves que viene"
            if (
                f"proximo {nombre_dia}" in msg or
                f"próximo {nombre_dia}" in msg or
                f"{nombre_dia} que viene" in msg
            ):
                hoy = datetime.now()

                dias_hasta = (num_dia - hoy.weekday()) % 7
                dias_hasta += 7  # SIEMPRE siguiente semana

                fecha = hoy + timedelta(days=dias_hasta)
                self.datos["fecha"] = fecha.strftime("%d/%m/%Y")

                print("DEBUG DETECTADO PROXIMO DIA:", self.datos["fecha"])
                return
            hoy = datetime.now()

        if "hoy" in msg:
            self.datos["fecha"] = hoy.strftime("%d/%m/%Y")
            return

        if "mañana" in msg or "manana" in msg:
            self.datos["fecha"] = (hoy + timedelta(days=1)).strftime("%d/%m/%Y")
            return

        match_completa = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", msg)
        if match_completa:
            dia = int(match_completa.group(1))
            mes = int(match_completa.group(2))
            anio = int(match_completa.group(3))

            if anio < 100:
                anio += 2000

            try:
                fecha = datetime(anio, mes, dia)
                fecha_formateada = fecha.strftime("%d/%m/%Y")
                if fecha_formateada != self.datos["fecha"]:
                    self.datos["fecha"] = fecha_formateada
                    self._reset_disponibilidad()
                return
            except ValueError:
                pass

        match_dia_mes = re.search(r"\b(\d{1,2})[/-](\d{1,2})\b", msg)
        if match_dia_mes:
            dia = int(match_dia_mes.group(1))
            mes = int(match_dia_mes.group(2))
            anio = hoy.year

            try:
                fecha = datetime(anio, mes, dia)
                if fecha.date() < hoy.date():
                    fecha = datetime(anio + 1, mes, dia)

                fecha_formateada = fecha.strftime("%d/%m/%Y")
                if fecha_formateada != self.datos["fecha"]:
                    self.datos["fecha"] = fecha_formateada
                    self._reset_disponibilidad()

            except ValueError:
                pass

    def _extraer_hora_regex(self, msg, estado_actual):
        match_hora = re.search(
            r"(?:a las|a la|sobre las|sobre la|hora)\s*(\d{1,2})(?:[:h](\d{2}))?|\b(\d{1,2}):(\d{2})\b",
            msg
        )

        if match_hora:
            h = match_hora.group(1) or match_hora.group(3)
            m = match_hora.group(2) or match_hora.group(4) or "00"

            try:
                h_int = int(h)
                m_int = int(m)

                if h_int > 23 or m_int > 59:
                    return

                # Todo se interpreta como horario de restaurante (PM)
                if h_int < 12:
                    h_int += 12

                nueva_hora = f"{h_int:02d}:{m_int:02d}"
                if nueva_hora != self.datos["hora"]:
                    self.datos["hora"] = nueva_hora
                    self._reset_disponibilidad()
                return
            except ValueError:
                return

        if estado_actual == "PIDIENDO_HORA":
            solo_numero = re.search(r"^\s*(\d{1,2})(?:[:h](\d{2}))?\s*$", msg)
            if solo_numero:
                try:
                    h_int = int(solo_numero.group(1))
                    m_int = int(solo_numero.group(2) or "00")

                    if h_int > 23 or m_int > 59:
                        return

                    nueva_hora = f"{h_int:02d}:{m_int:02d}"
                    if nueva_hora != self.datos["hora"]:
                        self.datos["hora"] = nueva_hora
                        self._reset_disponibilidad()
                except ValueError:
                    return

    def _extraer_personas_regex(self, msg, estado_actual):
        match_personas = re.search(
            r"\b(?:mesa\s+para\s+(\d+)|para\s+(\d+)(?:\s+personas?|\s+comensales?)?|(\d+)\s*(?:personas?|comensales))\b",
            msg
        )

        if match_personas:
            valor = match_personas.group(1) or match_personas.group(2) or match_personas.group(3)
            nuevas_personas = int(valor)
            if nuevas_personas != self.datos["personas"]:
                self.datos["personas"] = nuevas_personas
                self._reset_disponibilidad()
            return

        if estado_actual == "PIDIENDO_PERSONAS":
            solo_numero = re.search(r"^\s*(\d+)\s*$", msg)
            if solo_numero:
                nuevas_personas = int(solo_numero.group(1))
                if nuevas_personas != self.datos["personas"]:
                    self.datos["personas"] = nuevas_personas
                    self._reset_disponibilidad()
                return

        if estado_actual in ["PIDIENDO_PERSONAS", "PIDIENDO_HORA"]:
            solo_para_numero = re.search(r"^\s*para\s+(\d+)\s*$", msg)
            if solo_para_numero:
                nuevas_personas = int(solo_para_numero.group(1))
                if nuevas_personas != self.datos["personas"]:
                    self.datos["personas"] = nuevas_personas
                    self._reset_disponibilidad()

    def _extraer_telefono_regex(self, msg):
        match_telefono = re.search(r"(?<!\d)(\d(?:[\s\-]?\d){8,})(?!\d)", msg)
        if not match_telefono:
            return

        telefono = re.sub(r"[\s\-]", "", match_telefono.group(1))
        if len(telefono) == 9:
            self.datos["telefono"] = telefono

    def _extraer_nombre_regex(self, mensaje_original, estado_actual):
        msg = mensaje_original.strip()
        msg_lower = msg.lower()

        patrones = [
            r"\bme llamo\s+([A-Za-zÁÉÍÓÚáéíóúÑñ ]{2,50})\b",
            r"\bsoy\s+([A-Za-zÁÉÍÓÚáéíóúÑñ ]{2,50})\b",
            r"\ba nombre de\s+([A-Za-zÁÉÍÓÚáéíóúÑñ ]{2,50})\b",
            r"\bnombre\s*[:\-]?\s*([A-Za-zÁÉÍÓÚáéíóúÑñ ]{2,50})\b"
        ]

        for patron in patrones:
            match = re.search(patron, msg, re.IGNORECASE)
            if match:
                nombre = self._limpiar_nombre(match.group(1))
                if nombre:
                    self.datos["nombre"] = nombre
                    return

        if estado_actual == "PIDIENDO_NOMBRE":
            if self._parece_nombre_simple(msg_lower):
                nombre = self._limpiar_nombre(msg)
                if nombre:
                    self.datos["nombre"] = nombre

    def _parece_nombre_simple(self, msg):
        respuestas_invalidas = {
            "si", "sí", "no", "vale", "ok", "de acuerdo", "perfecto", "bien"
        }

        if msg in respuestas_invalidas:
            return False

        if any(char.isdigit() for char in msg):
            return False

        palabras = msg.split()
        if len(palabras) == 0 or len(palabras) > 3:
            return False

        return all(re.fullmatch(r"[a-záéíóúñ]+", palabra, re.IGNORECASE) for palabra in palabras)

    def _limpiar_nombre(self, nombre):
        nombre = nombre.strip()
        nombre = re.split(
            r"\b(?:telefono|teléfono|tel|para|personas|persona|comensales?)\b",
            nombre,
            maxsplit=1,
            flags=re.IGNORECASE
        )[0]
        nombre = re.sub(r"\s+", " ", nombre).strip()

        if not nombre:
            return None

        palabras = nombre.split()
        if len(palabras) > 3:
            return None

        return nombre.title()

    def _reset_disponibilidad(self):
        self.datos["mesa_id"] = None
        self.disponibilidad_comprobada = False
        self.alternativas = []

    def actualizar_estado(self):
        if not self.reserva_en_curso:
            self.estado = "INACTIVO"
            self.ultima_accion = "SIN_RESERVA"
            return

        if not self.datos["fecha"]:
            self.estado = "PIDIENDO_FECHA"
            self.ultima_accion = "PEDIR_FECHA"
        elif not self.datos["hora"]:
            self.estado = "PIDIENDO_HORA"
            self.ultima_accion = "PEDIR_HORA"
        elif not self.datos["personas"]:
            self.estado = "PIDIENDO_PERSONAS"
            self.ultima_accion = "PEDIR_PERSONAS"
        elif not self.disponibilidad_comprobada:
            self.estado = "COMPROBANDO_DISPONIBILIDAD"
            self.ultima_accion = "COMPROBAR_DISPONIBILIDAD"
        elif self.datos["mesa_id"] is None:
            self.estado = "OFRECIENDO_ALTERNATIVAS"
            self.ultima_accion = "OFRECER_ALTERNATIVAS"
        elif not self.datos["nombre"]:
            self.estado = "PIDIENDO_NOMBRE"
            self.ultima_accion = "PEDIR_NOMBRE"
        elif not self.datos["telefono"]:
            self.estado = "PIDIENDO_TELEFONO"
            self.ultima_accion = "PEDIR_TELEFONO"
        else:
            self.estado = "LISTO"
            self.ultima_accion = "GUARDAR_RESERVA"

    def comprobar_disponibilidad(self):
        if not self.datos["fecha"] or not self.datos["hora"] or not self.datos["personas"]:
            return

        mesa = self.servicio.db.encontrar_mesa_disponible(
            self.servicio.normalizar_fecha(self.datos["fecha"]),
            self.datos["hora"],
            self.datos["personas"]
        )

        self.disponibilidad_comprobada = True

        if mesa:
            self.datos["mesa_id"] = mesa["id"]
            self.alternativas = []
        else:
            self.datos["mesa_id"] = None
            raw_alternativas = self.servicio.db.buscar_huecos_alternativos(
                self.servicio.normalizar_fecha(self.datos["fecha"]),
                self.datos["hora"],
                self.datos["personas"]
            )
            # Filtrar solo las que están en horario de cocina
            self.alternativas = [h for h in raw_alternativas if self.es_hora_en_horario_cocina(h)]

    def generar_respuesta_controlada(self):
        if self.estado == "PIDIENDO_FECHA":
            return "¿Para qué día sería la reserva?"

        if self.estado == "PIDIENDO_HORA":
            return "¿Para qué hora sería la reserva?"

        if self.estado == "PIDIENDO_PERSONAS":
            return "¿Para cuántas personas sería la reserva?"

        if self.estado == "PIDIENDO_NOMBRE":
            return "Perfecto, tenemos disponibilidad. ¿A nombre de quién hacemos la reserva?"

        if self.estado == "PIDIENDO_TELEFONO":
            return "Gracias. ¿Me facilitas un teléfono de contacto?"

        if self.estado == "OFRECIENDO_ALTERNATIVAS":
            if self.alternativas:
                alternativas_txt = ", ".join(self.alternativas)
                return (
                    f"Lo siento, no tenemos disponibilidad a las {self.datos['hora']}. "
                    f"Puedo ofrecerte estas alternativas: {alternativas_txt}. "
                    f"¿Te encaja alguna?"
                )

            return (
                f"Lo siento, no tenemos disponibilidad a las {self.datos['hora']} "
                f"y no he encontrado alternativas cercanas. "
                f"¿Prefieres probar otra hora?"
            )

        return "¿En qué puedo ayudarte con la reserva?"

    def obtener_contexto_para_llm(self):
        if not self.hay_flujo_reserva_activo():
            return ""

        return f"""
[SISTEMA - DATOS REALES]: {self.datos}
[SISTEMA - ESTADO]: {self.estado}
[SISTEMA - ACCION]: {self.ultima_accion}
[SISTEMA - MENSAJE]: {self.ultima_respuesta_sistema}
"""