
"""
Asistente de IA Local - Alchi
Conectado a LM Studio (API compatible con OpenAI)
"""

from openai import OpenAI
import os
import sys
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from config import Config


def procesar_carta_pdf():
    """
    Usa la librería Marker para convertir la carta en PDF a Markdown.
    Este proceso se realiza en cada inicio del programa.
    """
    try:
        ruta_pdf = os.path.join(os.path.dirname(__file__), Config.ARCHIVO_PDF)
        
        if not os.path.exists(ruta_pdf):
            print(f"⚠️  ADVERTENCIA: No se encontró el archivo {Config.ARCHIVO_PDF}")
            return ""

        print("🧠 Inicializando modelos de Marker (esto puede tardar unos segundos)...")
        # Inicializar el convertidor con los modelos necesarios
        converter = PdfConverter(
            artifact_dict=create_model_dict(),
        )

        print(f"📄 Procesando '{Config.ARCHIVO_PDF}'...")
        # Ejecutar la conversión
        # 'rendered' contiene .markdown, .json, e .images
        rendered = converter(ruta_pdf)
        
        return rendered.markdown

    except Exception as e:
        print(f"⚠️  Error al procesar el PDF con Marker: {e}")
        return ""


def crear_system_prompt(contexto_carta):
    """
    Crea el System Prompt con el contexto de la carta del restaurante.
    """
    prompt = f"""Eres 'Alchi', un asistente de IA amable y profesional del restaurante L'Alchimie Gastronomique.

Tu función es ayudar a los clientes con información sobre el menú, precios, ingredientes, alérgenos y condiciones de servicio.

A continuación tienes toda la información actualizada de nuestra carta:

{contexto_carta}

Instrucciones:
- Responde de manera clara, cordial y profesional
- Si te preguntan sobre platos, precios o ingredientes, usa la información de la carta
- Si no tienes información sobre algo específico, admítelo honestamente
- Sugiere platos cuando sea apropiado
- Alerta sobre alérgenos cuando sea relevante
"""
    return prompt


def inicializar_cliente():
    """
    Inicializa y configura el cliente de OpenAI para conectarse a LM Studio.
    """
    cliente = OpenAI(
        base_url=Config.LM_STUDIO_BASE_URL,
        api_key=Config.LM_STUDIO_API_KEY
    )
    return cliente


def verificar_conexion(cliente):
    """
    Verifica si el servidor de LM Studio está disponible.
    """
    try:
        # Intenta hacer una llamada simple para verificar la conexión
        respuesta = cliente.chat.completions.create(
            model=Config.MODEL_NAME,
            messages=[{"role": "user", "content": "test"}],
            max_tokens=1
        )
        return True
    except Exception as e:
        return False


def chatear_con_alchi(cliente, system_prompt):
    """
    Bucle principal de conversación con el asistente Alchi.
    
    Implementa ventana deslizante (Sliding Window) para evitar saturar el contexto:
    - Mantiene el System Prompt siempre
    - Conserva solo los últimos 6 mensajes (3 pares pregunta-respuesta)
    - La carta del restaurante se inyecta una sola vez en el System Prompt inicial
    """
    print("\n" + "="*60)
    print("  🍴  BIENVENIDO AL ASISTENTE ALCHI  🍴")
    print("  Restaurante L'Alchimie Gastronomique")
    print("="*60)
    print("\nEscribe 'salir', 'exit' o 'quit' para terminar la conversación.\n")
    
    # Historial de conversación
    historial = [{"role": "system", "content": system_prompt}]
    
    while True:
        try:
            # Solicitar entrada del usuario
            mensaje_usuario = input("Tú: ").strip()
            
            # Comandos para salir
            if mensaje_usuario.lower() in ['salir', 'exit', 'quit', 'adios', 'adiós']:
                print("\n👋 ¡Gracias por visitarnos! Esperamos verte pronto en L'Alchimie.\n")
                break
            
            # Ignorar mensajes vacíos
            if not mensaje_usuario:
                continue
            
            # Agregar mensaje del usuario al historial
            historial.append({"role": "user", "content": mensaje_usuario})
            
            # Gestión de ventana deslizante (Sliding Window)
            # IMPORTANTE: Limpiar ANTES de llamar a la API para que no vea mensajes antiguos
            max_historial = Config.MAX_MENSAJES_HISTORIAL + 1  # +1 por el System Prompt
            if len(historial) > max_historial:
                # Eliminar los dos mensajes más antiguos (pregunta y respuesta)
                # Siempre preservamos el System Prompt en la posición 0
                historial.pop(1)  # Eliminar pregunta más antigua
                historial.pop(1)  # Eliminar respuesta más antigua
            
            # Llamar a LM Studio para obtener respuesta
            print("Alchi: ", end="", flush=True)
            
            respuesta = cliente.chat.completions.create(
                model=Config.MODEL_NAME,
                messages=historial,
                temperature=Config.TEMPERATURE,
                max_tokens=Config.MAX_TOKENS,
                stream=True  # Streaming para respuesta en tiempo real
            )
            
            # Procesar y mostrar la respuesta en streaming
            respuesta_completa = ""
            for chunk in respuesta:
                if chunk.choices[0].delta.content:
                    contenido = chunk.choices[0].delta.content
                    print(contenido, end="", flush=True)
                    respuesta_completa += contenido
            
            print("\n")  # Salto de línea al final
            
            # Agregar respuesta del asistente al historial
            historial.append({"role": "assistant", "content": respuesta_completa})
            
            # Mostrar información del contexto si está habilitado
            if Config.MOSTRAR_INFO_CONTEXTO:
                num_mensajes = len(historial) - 1  # Sin contar el System Prompt
                pares_conversacion = num_mensajes // 2
                espacios_disponibles = (Config.MAX_MENSAJES_HISTORIAL - num_mensajes) // 2
                print(f"\n💬 Contexto: {pares_conversacion}/{Config.MAX_MENSAJES_HISTORIAL // 2} turnos | "
                      f"🔄 Espacio: {espacios_disponibles} turnos más\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 Conversación interrumpida. ¡Hasta pronto!\n")
            break
            
        except Exception as e:
            print(f"\n❌ Error durante la conversación: {e}")
            print("Por favor, verifica que LM Studio esté funcionando correctamente.\n")
            break


def main():
    """
    Función principal del programa.
    """
    print("\n🔄 Iniciando asistente Alchi...")
    
    # Leer el contexto de la carta
    print("📖 Cargando información del restaurante (procesando PDF)...")
    contexto_carta = procesar_carta_pdf()
    
    if not contexto_carta:
        print("⚠️  El asistente funcionará sin el contexto de la carta.")
    
    # Crear el System Prompt
    system_prompt = crear_system_prompt(contexto_carta)
    
    # Inicializar el cliente
    print(f"🔌 Conectando con LM Studio ({Config.LM_STUDIO_BASE_URL})...")
    try:
        cliente = inicializar_cliente()
        
        # Verificar conexión
        if not verificar_conexion(cliente):
            print("\n❌ ERROR: No se puede conectar con LM Studio.")
            print("\nPor favor, verifica que:")
            print("  1. LM Studio está abierto y ejecutándose")
            print("  2. Has cargado un modelo en LM Studio")
            print("  3. El servidor local está activo en http://localhost:1234")
            print("\n")
            sys.exit(1)
        
        print("✅ Conexión establecida con éxito!")
        
        # Iniciar chat
        chatear_con_alchi(cliente, system_prompt)
        
    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO: {e}")
        print("\nNo se pudo inicializar el cliente de OpenAI.")
        print("Verifica que LM Studio esté correctamente configurado.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
