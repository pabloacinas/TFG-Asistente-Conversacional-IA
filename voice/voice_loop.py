"""Bucle conversacional por voz: STT → procesar_turno → splitter → TTS."""
import threading
import time

from config import Config
from reservas import GestorReservas

from .audio_io import MicrofonoStream, ReproductorPCM
from .sentence_splitter import dividir_en_frases
from .stt import transcribir_streaming
from .tts import hablar_texto, sintetizar_streaming


PALABRAS_SALIR = {"salir", "adiós", "adios", "hasta luego", "chao"}


def _transcribir_un_turno(reproductor):
    """Abre micro, devuelve texto final del usuario o cadena vacía si error."""
    try:
        with MicrofonoStream() as mic:
            ultimo_parcial = ""
            print("\n[Escuchando...]", flush=True)
            for texto, is_final in transcribir_streaming(mic):
                if is_final:
                    return texto.strip()
                if texto != ultimo_parcial:
                    ultimo_parcial = texto
                    print(f"  …{texto}", end="\r", flush=True)
        return ""
    except Exception as e:
        print(f"\n[VOZ] Error STT: {e}")
        return ""


def _hablar_respuesta(stream_chunks, reproductor, cancel_event):
    """Consume chunks de texto del LLM, los trocea en frases y los manda a TTS."""
    def _texto_visible():
        for ch in stream_chunks:
            if cancel_event.is_set():
                return
            print(ch, end="", flush=True)
            yield ch
        print()

    frases = dividir_en_frases(_texto_visible())
    sintetizar_streaming(frases, reproductor, cancel_event=cancel_event)


def iniciar_bucle_voz(cliente, coleccion, markdown_horario, procesar_turno):
    """Bucle principal de modo voz."""
    print("\n" + "=" * 60)
    print("  ASISTENTE ALCHI — MODO VOZ  ")
    print("=" * 60 + "\n")

    gestor = GestorReservas(llm_client=cliente)
    historial = []
    reproductor = ReproductorPCM()

    try:
        # Saludo inicial
        print(f"Alchi: {Config.VOZ_SALUDO_INICIAL}")
        try:
            hablar_texto(Config.VOZ_SALUDO_INICIAL, reproductor)
            reproductor.esperar_vacio(timeout=10)
        except Exception as e:
            print(f"[VOZ] Error TTS saludo: {e}")
            return

        while True:
            try:
                msg = _transcribir_un_turno(reproductor)
                if not msg:
                    continue

                print(f"\nTú: {msg}")

                if msg.lower().strip(" .?!") in PALABRAS_SALIR:
                    despedida = "Hasta pronto."
                    print(f"Alchi: {despedida}")
                    hablar_texto(despedida, reproductor)
                    reproductor.esperar_vacio(timeout=10)
                    break

                cancel_event = threading.Event()
                reproductor.reanudar()

                print("Alchi: ", end="", flush=True)
                stream = procesar_turno(msg, cliente, coleccion, markdown_horario, gestor, historial)
                try:
                    _hablar_respuesta(stream, reproductor, cancel_event)
                except Exception as e:
                    print(f"\n[VOZ] Error TTS: {e}")
                    cancel_event.set()
                    reproductor.cancelar()

                reproductor.esperar_vacio(timeout=60)
                # Pequeña pausa para dar tiempo al stream de audio a vaciarse
                time.sleep(0.2)

            except KeyboardInterrupt:
                print("\n\nAdiós.")
                break
            except Exception as e:
                print(f"\n[VOZ] Error: {e}")
                continue
    finally:
        try:
            reproductor.cerrar()
        except Exception:
            pass
