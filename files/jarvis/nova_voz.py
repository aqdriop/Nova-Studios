"""
nova_voz.py - Sistema de voz profesional para NOVA Jarvis
==========================================================
Wake word "Hey Jarvis" + escucha continua + interrupcion + Whisper.

Uso:
    from nova_voz import VozProfesional
    voz = VozProfesional(
        wake_words=["hey jarvis", "jarvis"],
        on_wake=lambda: print("activado"),
        on_transcripcion=lambda t: print(f"dijo: {t}"),
    )
    voz.iniciar()
    ...
    voz.parar()

Requiere (opcional): pip install SpeechRecognition PyAudio
Whisper opcional: pip install openai-whisper (mas preciso pero pesado)
"""
import threading, queue, time, os

# Dependencias opcionales
try:
    import speech_recognition as sr
    SR_OK = True
except ImportError:
    SR_OK = False

try:
    import whisper
    WHISPER_OK = True
    _whisper_model = None
except ImportError:
    WHISPER_OK = False


# ============================================================
# CLASE PRINCIPAL
# ============================================================
class VozProfesional:
    """
    Sistema de voz avanzado:
    - Escucha continua en background
    - Detecta wake word ("hey jarvis") y activa modo comando
    - Callback cuando detecta comando completo
    - Puede usar Google (rapido) o Whisper (preciso pero local)
    - Puede ser interrumpido mientras habla el asistente
    """

    def __init__(self,
                    wake_words=("hey jarvis", "jarvis", "oye jarvis"),
                    on_wake=None,
                    on_transcripcion=None,
                    on_estado=None,
                    idioma="es-ES",
                    motor="google",  # "google" o "whisper"
                    ):
        self.wake_words = [w.lower() for w in wake_words]
        self.on_wake = on_wake
        self.on_transcripcion = on_transcripcion
        self.on_estado = on_estado
        self.idioma = idioma
        self.motor = motor if (motor != "whisper" or WHISPER_OK) else "google"

        self.activo = False
        self.escuchando_comando = False
        self.hilo = None
        self.recognizer = None
        self.microfono = None

        # Cola para procesar audio
        self.audio_queue = queue.Queue()

        # Cuando el asistente esta hablando, podemos interrumpirlo
        self.asistente_hablando = False
        self.interrupcion_callback = None

    def disponible(self):
        return SR_OK

    def iniciar(self):
        """Inicia la escucha continua en background."""
        if not SR_OK:
            self._notif_estado("Sin SpeechRecognition instalado")
            return False
        if self.activo:
            return True
        try:
            self.recognizer = sr.Recognizer()
            # Ajustar sensibilidad
            self.recognizer.energy_threshold = 300
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.8

            self.microfono = sr.Microphone()
            with self.microfono as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)

            self.activo = True
            self.hilo = threading.Thread(target=self._loop_escucha, daemon=True)
            self.hilo.start()
            self._notif_estado("Escuchando 'Hey Jarvis'...")
            return True
        except Exception as e:
            self._notif_estado(f"Error iniciando: {e}")
            return False

    def parar(self):
        self.activo = False
        self.escuchando_comando = False
        self._notif_estado("Detenido")

    def notificar_asistente_hablando(self, hablando):
        """Llamar cuando el asistente empieza/termina de hablar."""
        self.asistente_hablando = hablando

    def _notif_estado(self, texto):
        if self.on_estado:
            try: self.on_estado(texto)
            except Exception: pass

    def _loop_escucha(self):
        """Loop principal: siempre escuchando, o wake word o comando completo."""
        while self.activo:
            try:
                # Escuchar un fragmento corto
                with self.microfono as source:
                    audio = self.recognizer.listen(source,
                        timeout=None, phrase_time_limit=6)

                # Procesar en background para no bloquear
                threading.Thread(target=self._procesar_audio,
                                  args=(audio,), daemon=True).start()
            except sr.WaitTimeoutError:
                continue
            except Exception as e:
                print(f"[VozPro] Error escucha: {e}")
                time.sleep(0.5)

    def _procesar_audio(self, audio):
        try:
            # Transcribir
            texto = self._transcribir(audio)
            if not texto:
                return
            texto_low = texto.lower().strip()

            # Modo comando: enviar transcripcion directamente
            if self.escuchando_comando:
                self.escuchando_comando = False
                if self.on_transcripcion:
                    self.on_transcripcion(texto)
                self._notif_estado("Escuchando 'Hey Jarvis'...")
                return

            # Buscar wake word
            for wake in self.wake_words:
                if wake in texto_low:
                    # Extraer lo que dijo despues del wake word (si dijo algo)
                    resto = texto_low.split(wake, 1)[1].strip()
                    if resto:
                        # Ejemplo: "hey jarvis que hora es" -> se envia "que hora es"
                        if self.on_transcripcion:
                            self.on_transcripcion(resto)
                    else:
                        # Solo dijo la wake word, esperamos comando
                        self.escuchando_comando = True
                        if self.on_wake:
                            self.on_wake()
                        self._notif_estado("Te escucho...")
                    return

            # Si el asistente esta hablando y detectamos habla, es interrupcion
            if self.asistente_hablando and self.interrupcion_callback:
                if "para" in texto_low or "stop" in texto_low or "silencio" in texto_low:
                    self.interrupcion_callback()

        except Exception as e:
            print(f"[VozPro] Error procesando: {e}")

    def _transcribir(self, audio):
        """Devuelve el texto transcrito, o cadena vacia si no entendio."""
        if self.motor == "whisper" and WHISPER_OK:
            return self._transcribir_whisper(audio)
        return self._transcribir_google(audio)

    def _transcribir_google(self, audio):
        try:
            return self.recognizer.recognize_google(audio, language=self.idioma)
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            print(f"[VozPro] Google error: {e}")
            return ""

    def _transcribir_whisper(self, audio):
        global _whisper_model
        try:
            if _whisper_model is None:
                # Cargar modelo pequeño (tiny/base son rapidos)
                _whisper_model = whisper.load_model("base")
            # Guardar audio a wav temporal
            import tempfile, wave
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                wav_data = audio.get_wav_data()
                f.write(wav_data)
                ruta = f.name
            result = _whisper_model.transcribe(ruta,
                language=self.idioma.split("-")[0],
                fp16=False)
            try: os.unlink(ruta)
            except: pass
            return result.get("text", "").strip()
        except Exception as e:
            print(f"[VozPro] Whisper error: {e}")
            return ""


# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    print("Test de VozProfesional")
    print(f"  SpeechRecognition: {'OK' if SR_OK else 'FALTA (pip install SpeechRecognition PyAudio)'}")
    print(f"  Whisper: {'OK' if WHISPER_OK else 'opcional (pip install openai-whisper)'}")

    if not SR_OK:
        print("Instala las dependencias primero")
        exit()

    def on_wake():
        print(">>> DESPERTADO! Te escucho...")
    def on_trans(texto):
        print(f">>> COMANDO: {texto}")
    def on_est(texto):
        print(f"[estado] {texto}")

    voz = VozProfesional(
        wake_words=["hey jarvis", "jarvis"],
        on_wake=on_wake,
        on_transcripcion=on_trans,
        on_estado=on_est,
    )
    voz.iniciar()
    print("\nDi 'Hey Jarvis' para probar. Ctrl+C para salir.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        voz.parar()
        print("\nSaliendo.")
