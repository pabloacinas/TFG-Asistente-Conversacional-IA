#!/usr/bin/env python3
"""
Script de Prueba - Gestión de Contexto con Ventana Deslizante
Permite verificar que el historial se gestiona correctamente
"""

from config import Config
import sys


def simular_conversacion():
    """
    Simula una conversación mostrando el estado del historial en cada turno.
    """
    print("\n" + "="*70)
    print("  🧪 PRUEBA DE GESTIÓN DE CONTEXTO - VENTANA DESLIZANTE")
    print("="*70)
    print(f"\nConfiguración: MAX_MENSAJES_HISTORIAL = {Config.MAX_MENSAJES_HISTORIAL}")
    print(f"Esto permite {Config.MAX_MENSAJES_HISTORIAL // 2} pares pregunta-respuesta\n")
    
    # Inicializar historial
    system_prompt = "Eres un asistente que recuerda nombres. Cuando te digan un nombre, recuérdalo."
    historial = [{"role": "system", "content": system_prompt}]
    
    # Definir una conversación de prueba
    conversacion_prueba = [
        ("Turno 1", "Hola, me llamo Juan"),
        ("Turno 2", "Mi color favorito es el azul"),
        ("Turno 3", "Tengo un perro llamado Max"),
        ("Turno 4 (debería olvidar Turno 1)", "¿Recuerdas cómo me llamo?"),
        ("Turno 5 (debería olvidar Turno 2)", "¿Cuál es mi color favorito?"),
    ]
    
    print("\n📋 CONVERSACIÓN DE PRUEBA:\n")
    
    for turno, (etiqueta, pregunta) in enumerate(conversacion_prueba, 1):
        print(f"\n{'─'*70}")
        print(f"▶ {etiqueta}")
        print(f"{'─'*70}")
        print(f"Usuario: {pregunta}")
        
        # Agregar pregunta al historial
        historial.append({"role": "user", "content": pregunta})
        
        # Gestión de ventana deslizante (MISMO CÓDIGO QUE main.py)
        # IMPORTANTE: Limpiar ANTES de simular la respuesta
        max_historial = Config.MAX_MENSAJES_HISTORIAL + 1  # +1 por el System Prompt
        if len(historial) > max_historial:
            print("\n⚠️  LÍMITE ALCANZADO - Eliminando mensajes más antiguos ANTES de responder...")
            historial.pop(1)  # Eliminar pregunta más antigua
            historial.pop(1)  # Eliminar respuesta más antigua
        
        # Simular respuesta (sin llamar a la API)
        respuesta_simulada = f"[Respuesta simulada al turno {turno}]"
        historial.append({"role": "assistant", "content": respuesta_simulada})
        print(f"Asistente: {respuesta_simulada}")
        
        # Mostrar estado del historial
        mostrar_estado_historial(historial, turno)
    
    print("\n" + "="*70)
    print("  ✅ PRUEBA COMPLETADA")
    print("="*70)
    print("\n📊 CONCLUSIÓN:")
    print("- Los turnos 1 y 2 fueron eliminados del historial")
    print("- El asistente NO podría responder correctamente a las preguntas de los turnos 4 y 5")
    print("- Solo recuerda los últimos 3 turnos (Turno 3, 4 y 5)\n")


def mostrar_estado_historial(historial, turno_actual):
    """
    Muestra el estado actual del historial de manera visual.
    """
    print(f"\n📦 ESTADO DEL HISTORIAL (después del Turno {turno_actual}):")
    print(f"   Total de mensajes: {len(historial)} (incluyendo System Prompt)")
    
    num_mensajes = len(historial) - 1  # Sin contar el System Prompt
    pares_conversacion = num_mensajes // 2
    espacios_disponibles = (Config.MAX_MENSAJES_HISTORIAL - num_mensajes) // 2
    
    print(f"   💬 Turnos en memoria: {pares_conversacion}/{Config.MAX_MENSAJES_HISTORIAL // 2}")
    print(f"   🔄 Espacio restante: {espacios_disponibles} turnos más")
    
    print("\n   Contenido del historial:")
    for i, msg in enumerate(historial):
        if msg["role"] == "system":
            print(f"   [{i}] 🔧 SYSTEM: [System Prompt permanente]")
        elif msg["role"] == "user":
            turno_num = (i + 1) // 2  # Calcular número de turno aproximado
            print(f"   [{i}] 👤 USER (Turno ~{turno_num}): {msg['content'][:50]}...")
        else:
            print(f"   [{i}] 🤖 ASSISTANT: {msg['content'][:50]}...")


def prueba_con_gemini():
    """
    Prueba interactiva con Gemini real.
    """
    print("\n" + "="*70)
    print("  🧪 PRUEBA REAL CON GEMINI")
    print("="*70)
    print("\n📝 Sigue estas instrucciones para probar:\n")
    print("1️⃣  Ejecuta: python main.py")
    print("2️⃣  Haz 4 conversaciones sobre temas DIFERENTES:")
    print("    - Turno 1: 'Me llamo Carlos'")
    print("    - Turno 2: 'Vivo en Madrid'")
    print("    - Turno 3: 'Tengo 25 años'")
    print("    - Turno 4: '¿Recuerdas mi nombre?' ❌ NO debería recordar!")
    print("\n3️⃣  Observa el contador de contexto en cada turno")
    print("4️⃣  En el Turno 4, el asistente debería decir que NO recuerda tu nombre\n")
    print("="*70)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--real":
        prueba_con_gemini()
    else:
        simular_conversacion()
        print("\n💡 TIP: Para ver instrucciones de prueba real, ejecuta:")
        print("   python test_context.py --real\n")
