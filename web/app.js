// Estado de la Aplicación
let activeCalls = {};
let selectedCallId = null;
let callHistory = {}; // Almacena { id_llamada: [ { role, content, time } ] }
let totalCallsCount = 0;
let logsInterval = null;
let listInterval = null;

// Variables de Voz (Configuración y Toggles)
let voiceEnabledOnServer = false;
let usarGoogleCloud = false; // Se recupera dinámicamente desde config.py
let recognition = null;
let isRecording = false;
let currentAudio = null;

// Cola de Reproducción de Voz (Pipelining de frases)
let speechQueue = [];
let isSpeaking = false;
let streamFinished = false;
let lastSentenceIndex = 0;

// Selectores del DOM
const callSimulatorForm = document.getElementById('call-simulator-form');
const callerPhoneInput = document.getElementById('caller-phone');
const callerNameInput = document.getElementById('caller-name');
const callsList = document.getElementById('calls-list');
const noCallsMessage = document.getElementById('no-calls-message');
const chatContainer = document.getElementById('chat-container');
const consoleHeader = document.getElementById('console-header');
const chatInputArea = document.getElementById('chat-input-area');
const chatMessageInput = document.getElementById('chat-message-input');
const btnSendMessage = document.getElementById('btn-send-message');
const btnHangupCall = document.getElementById('btn-hangup-call');
const serverLogs = document.getElementById('server-logs');
const btnClearLogs = document.getElementById('btn-clear-logs');
const voiceWaves = document.getElementById('voice-waves');
const btnMic = document.getElementById('btn-mic');
const voiceOptionsBar = document.getElementById('voice-options-bar');
const chkTts = document.getElementById('chk-tts');
const chkContinuous = document.getElementById('chk-continuous');

// Indicadores globales
const threadCountBadge = document.getElementById('thread-count');
const totalCallsBadge = document.getElementById('total-calls');

// Formatear hora actual
function getFormattedTime() {
    const now = new Date();
    return now.toTimeString().split(' ')[0];
}

// Inicialización
document.addEventListener('DOMContentLoaded', () => {
    // Escuchar envío de formulario para simular llamada
    callSimulatorForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const telefono = callerPhoneInput.value.trim();
        const nombre = callerNameInput.value.trim();
        if (telefono) {
            iniciarNuevaLlamada(telefono, nombre);
        }
    });

    // Enviar mensaje en chat
    btnSendMessage.addEventListener('click', enviarMensajeActual);
    chatMessageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            enviarMensajeActual();
        }
    });

    // Colgar llamada actual
    btnHangupCall.addEventListener('click', () => {
        if (selectedCallId) {
            colgarLlamada(selectedCallId);
        }
    });

    // Limpiar logs visuales
    btnClearLogs.addEventListener('click', () => {
        serverLogs.innerHTML = `<div class="log-line system-msg">[Sistema] Logs limpiados visualmente.</div>`;
    });

    // Inicializar características de voz
    inicializarFuncionesVoz();

    // Iniciar intervalos de actualización
    iniciarActualizacionPeriodica();
});

// Arrancar timers
function iniciarActualizacionPeriodica() {
    // Actualizar lista de hilos cada 2 segundos
    fetchActiveCalls();
    listInterval = setInterval(fetchActiveCalls, 2000);

    // Actualizar logs del servidor cada 1.5 segundos
    fetchServerLogs();
    logsInterval = setInterval(fetchServerLogs, 1500);

    // Actualizar duraciones mostradas localmente cada segundo
    setInterval(actualizarDuracionesLocales, 1000);
}

// Inicializar Reconocimiento y Síntesis de voz locales
async function inicializarFuncionesVoz() {
    try {
        const response = await fetch('/api/config');
        if (response.ok) {
            const config = await response.json();
            if (config.voz_enabled) {
                voiceEnabledOnServer = true;
                usarGoogleCloud = config.usar_google_cloud;
                voiceOptionsBar.style.display = 'flex';
                btnMic.style.display = 'inline-flex';
                console.log(`Modo de voz activa. Usar Google Cloud TTS: ${usarGoogleCloud}`);
            }
        }
    } catch (e) {
        console.error('Error al obtener config del servidor:', e);
    }

    // Comprobar compatibilidad con Web Speech API para STT
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.lang = 'es-ES';
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onstart = () => {
            isRecording = true;
            btnMic.classList.add('recording');
            btnMic.innerHTML = '<i data-lucide="mic-off"></i>';
            lucide.createIcons();
            chatMessageInput.placeholder = "Escuchando... Habla ahora";
        };

        recognition.onend = () => {
            isRecording = false;
            btnMic.classList.remove('recording');
            btnMic.innerHTML = '<i data-lucide="mic"></i>';
            lucide.createIcons();
            const call = activeCalls[selectedCallId];
            if (call && call.activo) {
                chatMessageInput.placeholder = "Escribe el mensaje o simula la voz del cliente...";
            } else {
                chatMessageInput.placeholder = "Llamada finalizada.";
            }
        };

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            console.log('STT Transcripción:', transcript);
            chatMessageInput.value = transcript;
            enviarMensajeActual();
        };

        recognition.onerror = (event) => {
            console.error('Error STT:', event.error);
        };

        // Escuchar click en botón micro
        btnMic.addEventListener('click', () => {
            toggleGrabacion();
        });
    } else {
        console.warn('Este navegador no soporta reconocimiento de voz (SpeechRecognition).');
    }
}

// Activar/desactivar grabación de voz del usuario
function toggleGrabacion() {
    if (!recognition) return;
    if (isRecording) {
        recognition.stop();
    } else {
        limpiarColaVoz();
        recognition.start();
    }
}

// Limpiar la cola de voz y detener síntesis/reproducción actual
function limpiarColaVoz() {
    speechQueue = [];
    isSpeaking = false;
    streamFinished = false;
    lastSentenceIndex = 0;
    
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
    }
}

// Encolar una nueva frase para sintetizar en tiempo real (Soporta Híbrido)
function encolarFrase(texto) {
    if (!voiceEnabledOnServer || !chkTts.checked) return;

    // Limpiar texto para evitar fallos de lectura (etiquetas HTML, markdown, emojis)
    let limpio = texto.replace(/<\/?[^>]+(>|$)/g, "");
    limpio = limpio.replace(/\[.*?\]/g, "");
    limpio = limpio.replace(/\*+/g, "").trim();

    if (!limpio) return;

    if (usarGoogleCloud) {
        // Encolar elemento con precarga asíncrona de Google Cloud TTS
        const url = `/api/tts?texto=${encodeURIComponent(limpio)}`;
        const audioObj = new Audio(url);
        audioObj.preload = "auto";
        speechQueue.push({
            texto: limpio,
            audio: audioObj,
            esGoogle: true
        });
    } else {
        // Encolar texto puro para SpeechSynthesis nativa
        speechQueue.push({
            texto: limpio,
            audio: null,
            esGoogle: false
        });
    }
    
    procesarColaVoz();
}

// Procesar cola de voz secuencialmente (Google Cloud TTS o local según bandera)
function procesarColaVoz() {
    if (isSpeaking || speechQueue.length === 0) {
        return;
    }

    isSpeaking = true;
    const item = speechQueue.shift();
    
    if (item.esGoogle) {
        currentAudio = item.audio;

        currentAudio.onended = () => {
            currentAudio = null;
            isSpeaking = false;
            
            if (speechQueue.length > 0) {
                procesarColaVoz();
            } else if (streamFinished) {
                dispararMicroContinuo();
            }
        };

        currentAudio.onerror = (e) => {
            console.error("Error al reproducir audio de Google Cloud TTS, usando fallback local:", e);
            currentAudio = null;
            hablarTextoBrowserFallback(item.texto);
        };

        currentAudio.play().catch(err => {
            console.error("Error de auto-play o carga de audio en Google Cloud TTS, usando fallback local:", err);
            currentAudio = null;
            hablarTextoBrowserFallback(item.texto);
        });
    } else {
        // Ejecutar síntesis local directamente
        hablarTextoBrowserFallback(item.texto);
    }
}

// Fallback: Síntesis de voz nativa del navegador si falla Google Cloud TTS o si usarGoogleCloud es False
function hablarTextoBrowserFallback(textoLimpio) {
    if (!('speechSynthesis' in window)) {
        isSpeaking = false;
        procesarColaVoz();
        return;
    }
    
    const utterance = new SpeechSynthesisUtterance(textoLimpio);
    utterance.lang = 'es-ES';

    const voices = window.speechSynthesis.getVoices();
    let preferredVoice = voices.find(v => v.lang.startsWith('es-ES') && v.name.includes('Google'));
    if (!preferredVoice) preferredVoice = voices.find(v => v.lang.startsWith('es'));
    if (preferredVoice) utterance.voice = preferredVoice;

    utterance.onend = () => {
        isSpeaking = false;
        
        if (speechQueue.length > 0) {
            procesarColaVoz();
        } else if (streamFinished) {
            dispararMicroContinuo();
        }
    };

    utterance.onerror = (e) => {
        console.error("Error en fallback de síntesis del navegador:", e);
        isSpeaking = false;
        procesarColaVoz();
    };

    window.speechSynthesis.speak(utterance);
}

// Disparador del micrófono en modo continuo / manos libres
function dispararMicroContinuo() {
    const call = activeCalls[selectedCallId];
    if (chkContinuous.checked && selectedCallId && call?.activo && !isRecording) {
        setTimeout(() => {
            if (selectedCallId && activeCalls[selectedCallId]?.activo && !isRecording) {
                recognition.start();
            }
        }, 500);
    }
}

// GET /api/llamadas - Listar hilos activos
async function fetchActiveCalls() {
    try {
        const response = await fetch('/api/llamadas');
        if (!response.ok) throw new Error('Error al listar llamadas');
        const calls = await response.json();
        
        const activeIds = calls.map(c => c.id);
        let realThreadCount = 0;
        
        calls.forEach(call => {
            if (call.activo) realThreadCount++;
            
            if (!activeCalls[call.id]) {
                activeCalls[call.id] = call;
                if (!callHistory[call.id]) {
                    callHistory[call.id] = [];
                }
            } else {
                activeCalls[call.id] = { ...activeCalls[call.id], ...call };
            }
        });

        Object.keys(activeCalls).forEach(id => {
            if (!activeIds.includes(id)) {
                delete activeCalls[id];
                if (selectedCallId === id) {
                    resetearConsola();
                }
            }
        });

        threadCountBadge.textContent = realThreadCount;
        renderCallsList();
    } catch (e) {
        console.error('Error actualizando llamadas:', e);
    }
}

// GET /api/logs - Listar registros del backend
async function fetchServerLogs() {
    try {
        const response = await fetch('/api/logs');
        if (!response.ok) throw new Error('Error al obtener logs');
        const logs = await response.json();
        
        const currentScroll = serverLogs.scrollTop + serverLogs.clientHeight;
        const totalHeight = serverLogs.scrollHeight;
        const isNearBottom = (totalHeight - currentScroll) < 30;

        serverLogs.innerHTML = logs.map(line => {
            let cssClass = '';
            if (line.includes('[ERROR]') || line.includes('ERROR')) cssClass = 'color: #ef4444;';
            else if (line.includes('INICIADO') || line.includes('iniciando')) cssClass = 'color: #10b981;';
            else if (line.includes('FINALIZADO') || line.includes('terminada')) cssClass = 'color: #94a3b8; font-style: italic;';
            else if (line.includes('HTTP')) cssClass = 'color: #64748b;';
            return `<div class="log-line" style="${cssClass}">${line}</div>`;
        }).join('');

        if (isNearBottom || serverLogs.childNodes.length <= logs.length) {
            serverLogs.scrollTop = serverLogs.scrollHeight;
        }
    } catch (e) {
        console.error('Error actualizando logs:', e);
    }
}

// Pintar la lista de hilos en la izquierda
function renderCallsList() {
    const calls = Object.values(activeCalls);
    
    if (calls.length === 0) {
        noCallsMessage.style.display = 'flex';
        callsList.innerHTML = '';
        return;
    }
    
    noCallsMessage.style.display = 'none';
    
    callsList.innerHTML = calls.map(call => {
        const isSelected = selectedCallId === call.id ? 'active-card' : '';
        const isRinging = call.estado === 'iniciando' ? 'ringing-card' : '';
        const badgeClass = `status-${call.estado}`;
        
        const totalSeconds = call.duracion || 0;
        const mins = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
        const secs = (totalSeconds % 60).toString().padStart(2, '0');
        const durationStr = `${mins}:${secs}`;

        return `
            <div class="call-card ${isSelected} ${isRinging}" onclick="seleccionarLlamada('${call.id}')">
                <div class="call-card-header">
                    <span class="call-card-phone">${call.telefono}</span>
                    <span class="call-status-badge ${badgeClass}">${call.estado}</span>
                </div>
                <div class="call-card-body">
                    <span class="call-card-name">${call.nombre}</span>
                    <span id="duracion-${call.id}" data-start="${call.inicio}" data-active="${call.activo}">${durationStr}</span>
                </div>
                <div class="call-card-actions">
                    <button class="btn-card-action" onclick="event.stopPropagation(); seleccionarLlamada('${call.id}')">
                        <i data-lucide="eye" style="width:12px; height:12px;"></i> Conectar
                    </button>
                    ${call.activo ? `
                        <button class="btn-card-action btn-card-hangup" onclick="event.stopPropagation(); colgarLlamada('${call.id}')">
                            <i data-lucide="phone-off" style="width:12px; height:12px;"></i> Colgar
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');
    
    lucide.createIcons();
}

// Tickers locales para la duración de la llamada (evitar retraso visual por pooling)
function actualizarDuracionesLocales() {
    document.querySelectorAll('[id^="duracion-"]').forEach(span => {
        const start = parseFloat(span.getAttribute('data-start'));
        const isActive = span.getAttribute('data-active') === 'true';
        if (isActive && start) {
            const diff = Math.floor(Date.now() / 1000 - start);
            const mins = Math.floor(diff / 60).toString().padStart(2, '0');
            const secs = (diff % 60).toString().padStart(2, '0');
            span.textContent = `${mins}:${secs}`;
        }
    });
}

// POST /api/llamadas - Simular llamada entrante
async function iniciarNuevaLlamada(telefono, nombre) {
    try {
        const response = await fetch('/api/llamadas', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ telefono, nombre })
        });
        
        if (!response.ok) throw new Error('Error al simular llamada entrante');
        
        const data = await response.json();
        
        totalCallsCount++;
        totalCallsBadge.textContent = totalCallsCount;
        
        activeCalls[data.id] = {
            id: data.id,
            telefono: telefono,
            nombre: nombre,
            activo: true,
            estado: 'activa',
            duracion: 0,
            inicio: Date.now() / 1000,
            hilo_nombre: data.hilo_nombre
        };
        
        callHistory[data.id] = [
            { role: 'assistant', content: data.saludo, time: getFormattedTime() }
        ];
        
        seleccionarLlamada(data.id);
        
        // Inicializar cola de voz y reproducir el saludo inicial de inmediato
        limpiarColaVoz();
        encolarFrase(data.saludo);
        streamFinished = true; // El saludo es de bloque único
        
        fetchActiveCalls();
    } catch (e) {
        alert('Error al simular llamada: ' + e.message);
    }
}

// Seleccionar un hilo de llamada en la consola
function seleccionarLlamada(id) {
    selectedCallId = id;
    renderCallsList();
    
    const call = activeCalls[id];
    if (!call) return;
    
    consoleHeader.innerHTML = `
        <div class="call-info-large">
            <h2>
                <i data-lucide="phone" class="${call.activo ? 'active-pulse' : ''}" style="color: ${call.activo ? 'var(--color-success)' : 'var(--text-muted)'}"></i>
                Llamada de <strong>${call.nombre}</strong> (${call.telefono})
            </h2>
            <p class="subtitle">Hilo de ejecución asignado: <code style="font-family: var(--font-mono); color: var(--color-primary);">${call.hilo_nombre || 'Desconocido'}</code></p>
        </div>
    `;
    
    chatInputArea.style.display = 'flex';
    
    if (!call.activo) {
        chatMessageInput.disabled = true;
        chatMessageInput.placeholder = "Llamada finalizada.";
        btnSendMessage.disabled = true;
        btnMic.disabled = true;
    } else {
        chatMessageInput.disabled = false;
        chatMessageInput.placeholder = "Escribe el mensaje o simula la voz del cliente...";
        btnSendMessage.disabled = false;
        btnMic.disabled = false;
    }
    
    renderChatMessages();
    lucide.createIcons();
}

// Resetear consola a vacío
function resetearConsola() {
    selectedCallId = null;
    consoleHeader.innerHTML = `
        <div class="call-info-large">
            <h2><i data-lucide="headset"></i> Consola del Asistente</h2>
            <p class="subtitle">Selecciona una llamada activa de la izquierda para interactuar y escuchar el hilo.</p>
        </div>
    `;
    chatContainer.innerHTML = `
        <div class="empty-chat-state">
            <i data-lucide="message-square"></i>
            <p>Esperando llamada activa para visualizar el flujo conversacional.</p>
        </div>
    `;
    chatInputArea.style.display = 'none';
    voiceWaves.style.display = 'none';
    lucide.createIcons();
}

// Renderizar lista de mensajes del chat
function renderChatMessages() {
    const history = callHistory[selectedCallId] || [];
    
    if (history.length === 0) {
        chatContainer.innerHTML = `
            <div class="empty-chat-state">
                <i data-lucide="message-square"></i>
                <p>No hay mensajes en esta conversación.</p>
            </div>
        `;
        return;
    }
    
    chatContainer.innerHTML = history.map(msg => {
        const isBot = msg.role === 'assistant';
        const msgClass = isBot ? 'msg-bot' : 'msg-user';
        const label = isBot ? 'Alchi (IA)' : 'Cliente';
        
        return `
            <div class="chat-msg ${msgClass}">
                <div class="chat-bubble">
                    ${msg.content}
                </div>
                <span class="msg-meta">${label} • ${msg.time}</span>
            </div>
        `;
    }).join('');
    
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Enviar un mensaje
async function enviarMensajeActual() {
    const text = chatMessageInput.value.trim();
    if (!text || !selectedCallId) return;
    
    const id = selectedCallId;
    
    // Cancelar cualquier reproducción en curso al enviar nuevo mensaje
    limpiarColaVoz();
    
    callHistory[id].push({
        role: 'user',
        content: text,
        time: getFormattedTime()
    });
    
    chatMessageInput.value = '';
    renderChatMessages();
    
    const botMsgIndex = callHistory[id].push({
        role: 'assistant',
        content: '',
        time: getFormattedTime()
    }) - 1;
    
    voiceWaves.style.display = 'flex';
    
    try {
        const response = await fetch(`/api/llamadas/${id}/mensaje`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mensaje: text })
        });
        
        if (response.status === 409) {
            callHistory[id][botMsgIndex].content = "<em>[Sistema: El asistente está ocupado procesando otro turno]</em>";
            renderChatMessages();
            voiceWaves.style.display = 'none';
            return;
        }
        
        if (!response.ok) throw new Error('Error al enviar el mensaje');
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop();
            
            for (const line of lines) {
                if (line.trim().startsWith("data: ")) {
                    const dataStr = line.replace(/^data:\s*/, '').trim();
                    try {
                        const payload = JSON.parse(dataStr);
                        
                        if (payload.tipo === 'chunk') {
                            callHistory[id][botMsgIndex].content += payload.contenido;
                            renderChatMessages();
                            
                            // PIPELINING DE VOZ EN TIEMPO REAL:
                            // Detectar frases completadas en el texto acumulado del bot
                            const fullText = callHistory[id][botMsgIndex].content;
                            const currentDiff = fullText.substring(lastSentenceIndex);
                            
                            // Buscar límites de frases (punto, interrogación, exclamación, salto de línea)
                            // que vayan seguidos de espacios.
                            const regexBoundaries = /([.?!¿¡\n])\s+/g;
                            let match;
                            let lastBoundary = 0;
                            
                            while ((match = regexBoundaries.exec(currentDiff)) !== null) {
                                const sentence = currentDiff.substring(lastBoundary, match.index + match[1].length).trim();
                                if (sentence) {
                                    encolarFrase(sentence);
                                }
                                lastBoundary = match.index + match[0].length;
                            }
                            
                            // Mover el índice de lectura local por la cantidad de texto procesado
                            lastSentenceIndex += lastBoundary;
                            
                        } else if (payload.tipo === 'fin_turno') {
                            voiceWaves.style.display = 'none';
                            
                            // Encolar cualquier fragmento final restante del stream
                            const fullText = callHistory[id][botMsgIndex].content;
                            const remainingText = fullText.substring(lastSentenceIndex).trim();
                            if (remainingText) {
                                encolarFrase(remainingText);
                            }
                            
                            streamFinished = true;
                            
                            // Disparo directo si no hay nada en cola ni hablando actualmente
                            if (speechQueue.length === 0 && !isSpeaking) {
                                dispararMicroContinuo();
                            }
                            
                        } else if (payload.tipo === 'fin_llamada') {
                            callHistory[id][botMsgIndex].content += `\n\n<em>[${payload.contenido}]</em>`;
                            renderChatMessages();
                            voiceWaves.style.display = 'none';
                            
                            encolarFrase(payload.contenido);
                            streamFinished = true;
                            
                            colgarLlamadaLocal(id);
                        } else if (payload.tipo === 'error') {
                            callHistory[id][botMsgIndex].content += `\n\n<em>[Error en el hilo: ${payload.contenido}]</em>`;
                            renderChatMessages();
                            voiceWaves.style.display = 'none';
                        }
                    } catch (err) {
                        console.error('Error parseando SSE chunk:', err, line);
                    }
                }
            }
        }
        
    } catch (e) {
        callHistory[id][botMsgIndex].content = `Error al conectar con el servidor: ${e.message}`;
        renderChatMessages();
        voiceWaves.style.display = 'none';
    }
}

// POST /api/llamadas/<id>/colgar - Terminar llamada e hilo
async function colgarLlamada(id) {
    try {
        const response = await fetch(`/api/llamadas/${id}/colgar`, {
            method: 'POST'
        });
        if (!response.ok) throw new Error('Error al colgar la llamada');
        
        colgarLlamadaLocal(id);
        fetchActiveCalls();
    } catch (e) {
        console.error('Error al colgar la llamada:', e);
    }
}

// Colgar de forma local/actualizar UI
function colgarLlamadaLocal(id) {
    if (activeCalls[id]) {
        activeCalls[id].activo = false;
        activeCalls[id].estado = 'terminada';
    }
    
    // Detener grabaciones y lecturas de voz
    limpiarColaVoz();
    
    // Si es la seleccionada, deshabilitar caja de texto
    if (selectedCallId === id) {
        chatMessageInput.disabled = true;
        chatMessageInput.placeholder = "Llamada finalizada.";
        btnSendMessage.disabled = true;
        btnMic.disabled = true;
        voiceWaves.style.display = 'none';
    }
    
    // Agregar nota de fin de llamada al historial si no existe
    const history = callHistory[id] || [];
    const lastMsg = history[history.length - 1];
    if (lastMsg && !lastMsg.content.includes("[Llamada finalizada]")) {
        history.push({
            role: 'system',
            content: '<em>[Llamada finalizada por el usuario/centralita]</em>',
            time: getFormattedTime()
        });
        if (selectedCallId === id) {
            renderChatMessages();
        }
    }
}
