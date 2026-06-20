import http.server
import json
import mimetypes
import os
import queue
import re
import sys
import threading
import time
import uuid
import traceback

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NUCLEO_PATH = os.path.join(PROJECT_ROOT, "NucleoAlchi")
if NUCLEO_PATH not in sys.path:
    sys.path.insert(0, NUCLEO_PATH)

# Almacén en memoria de llamadas activas y logs
llamadas_activas = {}
llamadas_lock = threading.Lock()

log_buffer = []
log_lock = threading.Lock()

def registrar_log(msg):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {msg}"
    print(log_line, flush=True)
    with log_lock:
        log_buffer.append(log_line)
        if len(log_buffer) > 150:
            log_buffer.pop(0)
            
    # Guardar en archivo persistente para poder revisar cuando se quedan "pilladas"
    try:
        with open("server.log", "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except Exception as e:
        print(f"Error escribiendo en log persistente: {e}", flush=True)

class LlamadaThread(threading.Thread):
    """
    Hilo dedicado a gestionar el ciclo de vida y la conversación de una llamada.
    Cada llamada tiene su propio GestorReservas y su propio historial de chat.
    """
    def __init__(self, id_llamada, telefono, nombre, cliente, carta_md, horario_md):
        super().__init__(name=f"HiloLlamada-{id_llamada[:8]}", daemon=True)
        self.id_llamada = id_llamada
        self.telefono = telefono
        self.nombre_cliente = nombre
        self.cliente = cliente
        self.carta_md = carta_md
        self.horario_md = horario_md
        
        # Aislamiento de base de datos y modelo de reservas
        from reservas import GestorReservas
        self.gestor = GestorReservas(llm_client=cliente)
        self.historial = []
        
        self.cola_entrada = queue.Queue()
        self.cola_salida = queue.Queue()
        self.activo = True
        self.inicio = time.time()
        self.ultima_actividad = time.time()
        self.estado = "iniciando"
        self.procesando = False
        
    def run(self):
        registrar_log(f"[{self.name}] Hilo INICIADO para la llamada {self.id_llamada[:8]} ({self.telefono} - {self.nombre_cliente})")
        self.estado = "activa"
        self.ultima_actividad = time.time()
        
        # Saludo inicial
        from config import Config
        saludo = Config.VOZ_SALUDO_INICIAL
        
        # Enviamos saludo inicial
        self.cola_salida.put({"tipo": "chunk", "contenido": saludo})
        self.cola_salida.put({"tipo": "fin_turno", "contenido": ""})
        
        while self.activo:
            try:
                # Escuchar por entrada de usuario en la cola con un timeout para revisar inactividad
                item = self.cola_entrada.get(timeout=1.0)
                if item is None:
                    # Señal de colgar
                    registrar_log(f"[{self.name}] Recibida señal de colgar.")
                    break
                
                msg = item.get("mensaje", "").strip()
                if not msg:
                    continue
                
                self.procesando = True
                self.ultima_actividad = time.time()
                registrar_log(f"[{self.name}] Procesando mensaje de usuario: {msg!r}")
                
                from main import procesar_turno
                
                # Ejecutar el turno usando el generador
                stream = procesar_turno(
                    msg, 
                    self.cliente, 
                    self.carta_md, 
                    self.horario_md, 
                    self.gestor, 
                    self.historial
                )
                
                for chunk in stream:
                    if not self.activo:
                        break
                    self.cola_salida.put({"tipo": "chunk", "contenido": chunk})
                
                self.cola_salida.put({"tipo": "fin_turno", "contenido": ""})
                self.procesando = False
                
            except queue.Empty:
                # Revisar inactividad (colgar automáticamente tras 5 minutos de silencio)
                if time.time() - self.ultima_actividad > 300:
                    registrar_log(f"[{self.name}] Llamada colgada por inactividad de 5 minutos.")
                    self.cola_salida.put({"tipo": "fin_llamada", "contenido": "Llamada terminada por inactividad."})
                    break
                continue
            except Exception as e:
                traza = traceback.format_exc()
                registrar_log(f"[{self.name}] ERROR en ciclo de conversación: {e}\nDetalles:\n{traza}")
                self.cola_salida.put({"tipo": "error", "contenido": f"Error: {e}"})
                self.procesando = False
                break
                
        self.activo = False
        self.estado = "terminada"
        registrar_log(f"[{self.name}] Hilo FINALIZADO para la llamada {self.id_llamada[:8]}")

    def enviar_mensaje(self, mensaje):
        if not self.activo:
            return False
        self.cola_entrada.put({"mensaje": mensaje})
        self.ultima_actividad = time.time()
        return True

    def colgar(self):
        if not self.activo:
            return
        self.activo = False
        self.cola_entrada.put(None) # Señal de fin de hilo

class CentralitaHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    """
    Manejador HTTP para despachar páginas estáticas, APIs de la centralita
    y streams de Server-Sent Events (SSE).
    """
    
    def log_message(self, format, *args):
        # Desviar logs estándar de HTTP a nuestro logger personalizado
        registrar_log(f"HTTP {self.address_string()} - - {format % args}")

    def do_GET(self):
        url_path = self.path.split('?')[0]
        
        # 1. Rutas de API
        if url_path == "/api/llamadas":
            self._api_listar_llamadas()
        elif url_path == "/api/logs":
            self._api_listar_logs()
        elif url_path == "/api/config":
            self._api_obtener_config()
        elif url_path == "/api/tts":
            self._api_generar_tts()
        # 2. Archivos Estáticos
        elif url_path in ("/", "/index.html"):
            self._servir_archivo_estatico("web/index.html", "text/html")
        elif url_path == "/web/style.css":
            self._servir_archivo_estatico("web/style.css", "text/css")
        elif url_path == "/web/app.js":
            self._servir_archivo_estatico("web/app.js", "application/javascript")
        else:
            # Intento genérico de servir archivos bajo 'web/'
            safe_path = url_path.lstrip('/')
            base_dir = os.path.dirname(os.path.abspath(__file__))
            full_path = os.path.join(base_dir, safe_path)
            
            if safe_path.startswith("web/") and os.path.exists(full_path) and os.path.isfile(full_path):
                mime_type, _ = mimetypes.guess_type(full_path)
                self._servir_archivo_estatico(safe_path, mime_type or "application/octet-stream")
            else:
                self.send_error(404, "Recurso no encontrado")

    def do_POST(self):
        url_path = self.path.split('?')[0]
        
        # Rutas de API POST
        if url_path == "/api/llamadas":
            self._api_crear_llamada()
        elif re.match(r"^/api/llamadas/[a-f0-9\-]+/mensaje$", url_path):
            id_llamada = url_path.split('/')[3]
            self._api_enviar_mensaje(id_llamada)
        elif re.match(r"^/api/llamadas/[a-f0-9\-]+/colgar$", url_path):
            id_llamada = url_path.split('/')[3]
            self._api_colgar(id_llamada)
        else:
            self.send_error(404, "Endpoint API no encontrado")

    # ==========================================
    # IMPLEMENTACIÓN DE ENDPOINTS
    # ==========================================
    
    def _servir_archivo_estatico(self, ruta_relativa, content_type):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_dir, ruta_relativa)
        
        try:
            if not os.path.exists(full_path):
                self.send_error(404, f"Archivo {ruta_relativa} no encontrado")
                return
                
            with open(full_path, "rb") as f:
                contenido = f.read()
                
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(contenido)))
            self.end_headers()
            self.wfile.write(contenido)
        except Exception as e:
            self.send_error(500, f"Error al servir archivo estático: {e}")

    def _api_listar_llamadas(self):
        with llamadas_lock:
            # Limpiar llamadas terminadas viejas (>10s) para no saturar memoria
            ahora = time.time()
            for lid, llam in list(llamadas_activas.items()):
                if not llam.activo and (ahora - llam.ultima_actividad > 10):
                    del llamadas_activas[lid]
            
            resultado = []
            for lid, llam in llamadas_activas.items():
                resultado.append({
                    "id": llam.id_llamada,
                    "telefono": llam.telefono,
                    "nombre": llam.nombre_cliente,
                    "activo": llam.activo,
                    "estado": llam.estado,
                    "procesando": llam.procesando,
                    "duracion": int(time.time() - llam.inicio),
                    "hilo_nombre": llam.name,
                    "ultima_accion": llam.gestor.ultima_accion,
                    "estado_reserva": llam.gestor.estado,
                    "datos_reserva": llam.gestor.datos
                })
                
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(resultado, ensure_ascii=False).encode('utf-8'))

    def _api_obtener_config(self):
        from config import Config
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({
            "voz_enabled": getattr(self.server, "voz_enabled", False),
            "usar_google_cloud": Config.TTS_WEB_USAR_GOOGLE_CLOUD
        }, ensure_ascii=False).encode('utf-8'))

    def _api_generar_tts(self):
        import urllib.parse
        parsed_url = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed_url.query)
        texto = params.get("texto", [""])[0].strip()
        
        if not texto:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "El parámetro 'texto' es requerido"}).encode('utf-8'))
            return
            
        try:
            from google.cloud import texttospeech as tts
            from config import Config
            
            client = tts.TextToSpeechClient()
            
            # Usar la misma configuración de voz del archivo config.py
            voz = tts.VoiceSelectionParams(
                language_code=Config.TTS_LANGUAGE,
                name=Config.TTS_VOICE,
            )
            
            # En la web solicitamos codificación MP3 para compatibilidad nativa con la etiqueta <audio>
            audio_config = tts.AudioConfig(
                audio_encoding=tts.AudioEncoding.MP3
            )
            
            synthesis_input = tts.SynthesisInput(text=texto)
            
            registrar_log(f"Generando Google TTS MP3 para: '{texto[:30]}...' usando {Config.TTS_VOICE}")
            
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voz,
                audio_config=audio_config
            )
            
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(response.audio_content)))
            self.end_headers()
            self.wfile.write(response.audio_content)
            
        except Exception as e:
            traza = traceback.format_exc()
            registrar_log(f"Error generando Google TTS en el servidor: {e}\nDetalles:\n{traza}")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def _api_listar_logs(self):
        with log_lock:
            logs = list(log_buffer)
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(logs, ensure_ascii=False).encode('utf-8'))

    def _api_crear_llamada(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        try:
            params = json.loads(body) if body else {}
        except Exception:
            params = {}
            
        telefono = params.get("telefono", "").strip()
        nombre = params.get("nombre", "").strip() or "Cliente Anónimo"
        
        if not telefono:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "El parámetro 'telefono' es requerido"}).encode('utf-8'))
            return
            
        id_llamada = str(uuid.uuid4())
        
        # Recuperar recursos cargados desde el servidor
        server_inst = self.server
        
        hilo = LlamadaThread(
            id_llamada=id_llamada,
            telefono=telefono,
            nombre=nombre,
            cliente=server_inst.cliente,
            carta_md=server_inst.carta_md,
            horario_md=server_inst.horario_md
        )
        
        with llamadas_lock:
            llamadas_activas[id_llamada] = hilo
            
        hilo.start()
        
        # Esperar a que el saludo esté en la cola de salida
        saludo = ""
        try:
            item = hilo.cola_salida.get(timeout=3.0)
            if item and item.get("tipo") == "chunk":
                saludo = item.get("contenido")
                # Sacar también el fin de turno correspondiente
                hilo.cola_salida.get(timeout=1.0)
        except queue.Empty:
            saludo = "Hola, soy Alchi de L'Alchimie. ¿En qué puedo ayudarle?"
            
        self.send_response(201)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({
            "id": id_llamada,
            "saludo": saludo,
            "hilo_nombre": hilo.name
        }, ensure_ascii=False).encode('utf-8'))

    def _api_enviar_mensaje(self, id_llamada):
        with llamadas_lock:
            llamada = llamadas_activas.get(id_llamada)
            
        if not llamada:
            self.send_error(404, "Llamada no encontrada o ya finalizada")
            return
            
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        try:
            params = json.loads(body) if body else {}
        except Exception:
            params = {}
            
        mensaje = params.get("mensaje", "").strip()
        if not mensaje:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "El parámetro 'mensaje' es requerido"}).encode('utf-8'))
            return
            
        # Comprobar si ya está procesando
        if llamada.procesando:
            self.send_response(409) # Conflict
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "El asistente ya está procesando un turno para esta llamada"}).encode('utf-8'))
            return
            
        # Enviar mensaje al hilo
        enviado = llamada.enviar_mensaje(mensaje)
        if not enviado:
            self.send_error(500, "No se pudo entregar el mensaje al hilo de la llamada")
            return
            
        # Retornar flujo de respuesta usando Server-Sent Events (SSE)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        
        while llamada.activo:
            try:
                # Esperar chunks de respuesta
                item = llamada.cola_salida.get(timeout=0.1)
                tipo = item.get("tipo")
                contenido = item.get("contenido")
                
                # Transmitir en formato SSE
                event_data = {"tipo": tipo, "contenido": contenido}
                self.wfile.write(f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n".encode('utf-8'))
                self.wfile.flush()
                
                # Parar el bucle de respuesta de este turno al encontrar los terminales
                if tipo in ("fin_turno", "fin_llamada", "error"):
                    break
            except queue.Empty:
                # Mantener conexión viva enviando ping de SSE
                try:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                except Exception:
                    # Conexión cerrada abruptamente por el cliente
                    registrar_log(f"Cliente cerró la conexión para la llamada {id_llamada[:8]}")
                    break
                continue
            except Exception as e:
                traza = traceback.format_exc()
                registrar_log(f"Error en streaming de respuesta: {e}\nDetalles:\n{traza}")
                break

    def _api_colgar(self, id_llamada):
        with llamadas_lock:
            llamada = llamadas_activas.get(id_llamada)
            
        if not llamada:
            self.send_error(404, "Llamada no encontrada")
            return
            
        llamada.colgar()
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "colgada", "id": id_llamada}).encode('utf-8'))

class CentralitaServer(http.server.ThreadingHTTPServer):
    """
    Servidor HTTP multi-hilo que expone las propiedades necesarias
    para que los hilos de llamada accedan a los recursos de LLM y RAG.
    """
    def __init__(self, server_address, RequestHandlerClass, cliente, carta_md, horario_md, voz_enabled=False):
        super().__init__(server_address, RequestHandlerClass)
        self.cliente = cliente
        self.carta_md = carta_md
        self.horario_md = horario_md
        self.voz_enabled = voz_enabled
        self.running = True

def iniciar_servidor(cliente, carta_md, horario_md, host="localhost", port=8000, voz_enabled=False):
    """
    Arranca el servidor de la centralita telefónica local e inicia el bucle de escucha.
    """
    server_address = (host, port)
    
    # Crear carpeta web si no existe para asegurar integridad
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "web"), exist_ok=True)
    
    httpd = CentralitaServer(
        server_address, 
        CentralitaHTTPRequestHandler,
        cliente=cliente,
        carta_md=carta_md,
        horario_md=horario_md,
        voz_enabled=voz_enabled
    )
    
    registrar_log(f"============================================================")
    registrar_log(f"  CENTRALITA LOCAL ALCHI — HILO EN ESCUCHA ACTIVO")
    registrar_log(f"  Servidor corriendo en: http://{host}:{port}")
    registrar_log(f"  Para simular llamadas, abre esa dirección en tu navegador")
    registrar_log(f"============================================================")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        registrar_log("Apagando servidor de centralita...")
    finally:
        httpd.running = False
        # Terminar todos los hilos de llamadas activas
        with llamadas_lock:
            for llam in llamadas_activas.values():
                llam.colgar()
        httpd.server_close()
        registrar_log("Servidor detenido.")
