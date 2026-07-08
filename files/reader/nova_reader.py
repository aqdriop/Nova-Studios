"""
📖 NOVA READER — Lee y resume PDFs, libros, documentos
======================================================
- Carga PDF, TXT, DOCX, MD
- Resúmenes inteligentes con IA
- Pregunta cualquier cosa sobre el documento
- Extracción de ideas clave, citas, glosario
- Genera apuntes en Markdown
"""
import os, sys, json, threading, urllib.request, urllib.error
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# VERSION (para el sistema de actualizaciones)
# ============================================================
VERSION = "1.0.0"
MODULO_ID = "reader"

PARENT = os.path.dirname(APP_DIR)
CONFIG = os.path.join(PARENT, "config.json")
APUNTES_DIR = os.path.join(APP_DIR, "apuntes")
os.makedirs(APUNTES_DIR, exist_ok=True)

# Importar la librería compartida de IA
sys.path.insert(0, APP_DIR)
from nova_ia_lib import llamar_llm, dialogo_config, listar_modelos

try: from PyPDF2 import PdfReader; PDF_OK = True
except:
    try: from pypdf import PdfReader; PDF_OK = True
    except: PDF_OK = False
try: from docx import Document; DOCX_OK = True
except: DOCX_OK = False
try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_OK = True
except:
    OCR_OK = False

def cargar_config():
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return {}

def extraer_texto(ruta):
    """Extrae texto del archivo. Devuelve (texto, advertencia)."""
    ext = os.path.splitext(ruta)[1].lower()
    try:
        if ext in (".txt", ".md", ".py", ".js", ".html", ".css", ".json", ".csv", ".log", ".xml"):
            with open(ruta, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(), None
        if ext == ".pdf":
            if not PDF_OK: return None, "Falta pypdf (pip install pypdf)"
            reader = PdfReader(ruta)
            texto = "\n".join((p.extract_text() or "") for p in reader.pages)
            # Si extrajo poco o nada → probablemente es PDF escaneado
            if len(texto.strip()) < 50:
                if OCR_OK:
                    # Intentar OCR (más lento pero funciona con escaneados)
                    try:
                        imgs = convert_from_path(ruta, dpi=200)
                        textos_ocr = []
                        for img in imgs:
                            textos_ocr.append(pytesseract.image_to_string(img, lang="spa+eng"))
                        return "\n".join(textos_ocr), None
                    except Exception as e:
                        return None, (f"PDF escaneado/imagen y OCR falló: {e}\n\n"
                                       "Instala Tesseract: https://github.com/UB-Mannheim/tesseract/wiki")
                else:
                    return None, ("Este PDF parece escaneado (es imagen). "
                                   "Para leerlo necesitas OCR:\n"
                                   "  pip install pytesseract pdf2image\n"
                                   "Y luego instalar Tesseract:\n"
                                   "  https://github.com/UB-Mannheim/tesseract/wiki")
            return texto, None
        if ext == ".docx":
            if not DOCX_OK: return None, "Falta python-docx (pip install python-docx)"
            doc = Document(ruta)
            return "\n".join(p.text for p in doc.paragraphs), None
        return None, f"Formato no soportado: {ext}"
    except Exception as e:
        return None, str(e)

class NovaReader:
    def __init__(self):
        self.cfg = cargar_config()
        self.proveedor = self.cfg.get("reader_proveedor", "Gemini")
        self.modelo = self.cfg.get("reader_modelo", "gemini-2.5-flash")
        self.api_key = self.cfg.get("api_keys", {}).get(self.proveedor, "")
        self.texto_actual = ""
        self.archivo_actual = ""
        self.procesando = False  # Para evitar múltiples acciones simultáneas
        # Límite de chars distinto por proveedor (cada uno acepta lo que acepta)
        self.LIMITES = {
            "Gemini": 800000,   # Gemini 2.5 Flash: contexto enorme
            "OpenAI": 100000,   # GPT-4o: ~128k tokens ~ 400k chars
            "Groq": 30000,      # Más restrictivo
            "Ollama": 30000,    # Depende del modelo local
        }

        self.root = tk.Tk()
        self.root.title("📖 NOVA Reader")
        self.root.geometry("950x720")
        self.root.configure(bg="#1a1a2e")
        self._build()

    def _build(self):
        # Topbar
        top = tk.Frame(self.root, bg="#0f0f1e", height=50)
        top.pack(fill="x"); top.pack_propagate(False)
        tk.Label(top, text="📖  NOVA Reader", bg="#0f0f1e", fg="#a78bfa",
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=14, pady=8)
        tk.Button(top, text="⚙ Config", command=self._config,
                  bg="#1e1e3a", fg="white", relief="flat", padx=10, pady=4,
                  cursor="hand2").pack(side="right", padx=4, pady=10)
        tk.Button(top, text="📁 Mis apuntes", command=self._abrir_apuntes,
                  bg="#1e1e3a", fg="white", relief="flat", padx=10, pady=4,
                  cursor="hand2").pack(side="right", padx=4, pady=10)

        # Botón abrir
        abrir_frame = tk.Frame(self.root, bg="#1a1a2e")
        abrir_frame.pack(fill="x", padx=14, pady=10)
        tk.Button(abrir_frame, text="📂  ABRIR DOCUMENTO (PDF/TXT/DOCX/MD)",
                  command=self._abrir_archivo, bg="#7c3aed", fg="white",
                  font=("Segoe UI", 12, "bold"), relief="flat",
                  padx=20, pady=12, cursor="hand2").pack(fill="x")

        self.lbl_archivo = tk.Label(self.root, text="(ningún documento cargado)",
                                     bg="#1a1a2e", fg="#94a3b8",
                                     font=("Segoe UI", 9, "italic"))
        self.lbl_archivo.pack()

        # Acciones
        acc = tk.Frame(self.root, bg="#1a1a2e")
        acc.pack(fill="x", padx=14, pady=6)
        for txt, cmd, col in [
            ("📝 Resumir", lambda: self._accion("resumir"), "#3b82f6"),
            ("🎯 Ideas clave", lambda: self._accion("ideas"), "#22c55e"),
            ("📖 Generar apuntes", lambda: self._accion("apuntes"), "#f59e0b"),
            ("💬 Generar quiz", lambda: self._accion("quiz"), "#ec4899"),
            ("🗣️ Explica como a un niño", lambda: self._accion("simple"), "#06b6d4"),
        ]:
            tk.Button(acc, text=txt, command=cmd, bg=col, fg="white",
                      relief="flat", padx=10, pady=8, font=("Segoe UI", 9, "bold"),
                      cursor="hand2").pack(side="left", padx=2, fill="x", expand=True)

        # Pregunta libre
        pf = tk.Frame(self.root, bg="#1a1a2e"); pf.pack(fill="x", padx=14, pady=6)
        tk.Label(pf, text="💬 Pregunta lo que quieras sobre el documento:",
                 bg="#1a1a2e", fg="#a78bfa", font=("Segoe UI", 10, "bold")
                 ).pack(anchor="w")
        ef = tk.Frame(pf, bg="#1a1a2e"); ef.pack(fill="x", pady=4)
        self.entrada = tk.Entry(ef, bg="#282a36", fg="white", relief="flat",
                                 font=("Segoe UI", 11), insertbackground="white")
        self.entrada.pack(side="left", fill="x", expand=True, ipady=8, padx=(0,6))
        self.entrada.bind("<Return>", lambda e: self._preguntar())
        tk.Button(ef, text="Preguntar ➤", command=self._preguntar,
                  bg="#7c3aed", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=14, cursor="hand2").pack(side="right")

        # Salida
        tk.Label(self.root, text="📺 Resultado:", bg="#1a1a2e", fg="#a78bfa",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=14, pady=(8,2))
        self.salida = scrolledtext.ScrolledText(self.root, bg="#0f0f25",
            fg="#e0e7ff", font=("Segoe UI", 10), padx=12, pady=8,
            relief="flat", state="disabled", wrap="word")
        self.salida.pack(fill="both", expand=True, padx=14, pady=(0,8))
        self.salida.tag_config("info", foreground="#60a5fa")
        self.salida.tag_config("ok", foreground="#22c55e")
        self.salida.tag_config("err", foreground="#ef4444")

        # Botón guardar
        self.btn_guardar = tk.Button(self.root, text="💾 Guardar como apuntes",
                                      command=self._guardar_apuntes,
                                      bg="#22c55e", fg="white", relief="flat",
                                      padx=14, pady=6, font=("Segoe UI", 10, "bold"),
                                      cursor="hand2", state="disabled")
        self.btn_guardar.pack(pady=6)

        self._log("👋 Bienvenido a NOVA Reader\n\n"
                  "1. Carga un PDF/TXT/DOCX/MD con el botón morado\n"
                  "2. Pulsa una de las 5 acciones (Resumir, Ideas, etc.)\n"
                  "3. O escribe una pregunta concreta sobre el contenido\n\n"
                  "Asegúrate de tener configurada una IA en ⚙ Config", "info")

    def _log(self, txt, tag=None):
        self.salida.config(state="normal")
        if tag: self.salida.insert("end", txt + "\n", tag)
        else: self.salida.insert("end", txt + "\n")
        self.salida.see("end")
        self.salida.config(state="disabled")

    def _abrir_archivo(self):
        ruta = filedialog.askopenfilename(
            title="Selecciona un documento",
            filetypes=[("Todos los soportados", "*.pdf *.txt *.docx *.md"),
                       ("PDF", "*.pdf"), ("Texto", "*.txt"),
                       ("Word", "*.docx"), ("Markdown", "*.md"),
                       ("Todos", "*.*")])
        if not ruta: return
        self._log(f"\n📂 Cargando: {os.path.basename(ruta)}...", "info")
        def tarea():
            texto, err = extraer_texto(ruta)
            if err:
                self.root.after(0, self._log, f"❌ {err}", "err"); return
            self.texto_actual = texto
            self.archivo_actual = ruta
            chars = len(texto)
            palabras = len(texto.split())
            self.root.after(0, lambda: self.lbl_archivo.config(
                text=f"📄 {os.path.basename(ruta)} — {palabras:,} palabras, {chars:,} caracteres",
                fg="#22c55e"))
            self.root.after(0, self._log,
                f"✅ Documento cargado: {palabras:,} palabras", "ok")
            self.root.after(0, self._log,
                f"Vista previa: {texto[:300]}...\n", "info")
        threading.Thread(target=tarea, daemon=True).start()

    def _accion(self, tipo):
        if not self.texto_actual:
            messagebox.showwarning("Sin documento", "Carga un documento primero")
            return
        if self.procesando:
            messagebox.showinfo("Espera",
                "Ya hay una acción en curso. Espera a que termine antes de pulsar otra "
                "(evita rate limits).")
            return
        prompts = {
            "resumir": ("Eres un experto resumiendo documentos. Responde siempre basándote SOLO en el documento que se te da.",
                        "Documento a resumir:\n\n{TEXTO}\n\n"
                        "Resume el documento ANTERIOR en 5-10 frases capturando lo esencial."),
            "ideas": ("Eres experto en extraer ideas clave. Responde basándote SOLO en el documento dado.",
                      "Documento:\n\n{TEXTO}\n\n"
                      "Lista las 10 ideas MÁS IMPORTANTES del documento ANTERIOR, una por línea numerada."),
            "apuntes": ("Eres profesor experto creando apuntes de estudio. Usa SOLO el documento.",
                        "Documento:\n\n{TEXTO}\n\n"
                        "Crea apuntes COMPLETOS en Markdown con títulos, subtítulos, "
                        "puntos clave y conclusiones SOBRE EL DOCUMENTO ANTERIOR."),
            "quiz": ("Eres profesor creando exámenes. Las preguntas DEBEN basarse SOLO en el documento dado, NUNCA inventes.",
                     "Documento:\n\n{TEXTO}\n\n"
                     "Crea 10 preguntas de tipo test SOBRE EL DOCUMENTO ANTERIOR. "
                     "Cada pregunta con 4 opciones (A/B/C/D) y la respuesta correcta marcada."),
            "simple": ("Eres profesor que explica las cosas para un niño de 10 años. Usa SOLO el documento.",
                       "Documento:\n\n{TEXTO}\n\n"
                       "Explícame el DOCUMENTO ANTERIOR como si fuera para un niño, "
                       "con palabras simples y ejemplos divertidos."),
        }
        system, user_template = prompts[tipo]

        # Límite según proveedor
        limite = self.LIMITES.get(self.proveedor, 30000)
        texto = self.texto_actual[:limite]
        chars = len(self.texto_actual)
        if chars > limite:
            self._log(f"⚠️ Documento de {chars:,} chars. Usando los primeros {limite:,} "
                      f"(límite de {self.proveedor}).", "info")

        # Sustituir el placeholder por el texto real
        user = user_template.replace("{TEXTO}", texto)

        self._log(f"\n🧠 Procesando ({tipo})... espera unos segundos", "info")
        self.btn_guardar.config(state="disabled")
        self.procesando = True
        self._bloquear_botones(True)

        def tarea():
            resp, err = llamar_llm(self.proveedor, self.modelo, self.api_key,
                                    system, user)
            if err:
                self.root.after(0, self._log, f"❌ {err}", "err")
            else:
                self.root.after(0, self._log, f"\n{'='*50}\n{resp}\n{'='*50}", "ok")
                self.root.after(0, lambda: self.btn_guardar.config(state="normal"))
            self.procesando = False
            self.root.after(0, lambda: self._bloquear_botones(False))
        threading.Thread(target=tarea, daemon=True).start()

    def _bloquear_botones(self, bloquear):
        """Bloquea/desbloquea los botones de acción mientras hay una petición."""
        # Cambiar texto del estado para que se vea claro
        if bloquear:
            try:
                self.lbl_archivo.config(fg="#fbbf24")
                # Añadir indicador
                txt_actual = self.lbl_archivo.cget("text")
                if "⏳" not in txt_actual:
                    self.lbl_archivo.config(text="⏳  PROCESANDO... " + txt_actual)
            except Exception: pass
        else:
            try:
                txt = self.lbl_archivo.cget("text").replace("⏳  PROCESANDO... ", "")
                self.lbl_archivo.config(text=txt, fg="#22c55e")
            except Exception: pass

    def _preguntar(self):
        if not self.texto_actual:
            messagebox.showwarning("Sin documento", "Carga un documento primero")
            return
        if self.procesando:
            messagebox.showinfo("Espera",
                "Ya hay una acción en curso. Espera a que termine.")
            return
        pregunta = self.entrada.get().strip()
        if not pregunta: return
        self.entrada.delete(0, "end")
        self._log(f"\n❓ {pregunta}", "info")

        limite = self.LIMITES.get(self.proveedor, 30000)
        texto = self.texto_actual[:limite]
        if len(self.texto_actual) > limite:
            self._log(f"⚠️ Usando primeros {limite:,} chars del documento.", "info")

        self.procesando = True
        self._bloquear_botones(True)
        def tarea():
            system = ("Eres asistente experto. Responde basándote SOLO en el documento que te paso. "
                      "Si la respuesta no está en el documento, dilo claramente. Responde en español.")
            user = f"DOCUMENTO:\n{texto}\n\n=== PREGUNTA DEL USUARIO ===\n{pregunta}"
            resp, err = llamar_llm(self.proveedor, self.modelo, self.api_key, system, user)
            if err:
                self.root.after(0, self._log, f"❌ {err}", "err")
            else:
                self.root.after(0, self._log, f"\n{resp}\n", "ok")
                self.root.after(0, lambda: self.btn_guardar.config(state="normal"))
            self.procesando = False
            self.root.after(0, lambda: self._bloquear_botones(False))
        threading.Thread(target=tarea, daemon=True).start()

    def _guardar_apuntes(self):
        contenido = self.salida.get("1.0", "end").strip()
        if not contenido: return
        from datetime import datetime
        nombre_doc = os.path.splitext(os.path.basename(self.archivo_actual))[0] if self.archivo_actual else "apuntes"
        nombre = f"{nombre_doc}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        ruta = os.path.join(APUNTES_DIR, nombre)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(f"# Apuntes de {nombre_doc}\n\n_Generado por NOVA Reader_\n\n---\n\n")
            f.write(contenido)
        messagebox.showinfo("✅ Guardado", f"Apuntes guardados en:\n{ruta}")

    def _abrir_apuntes(self):
        try:
            if sys.platform.startswith("win"): os.startfile(APUNTES_DIR)
        except: pass

    def _config(self):
        """Diálogo de config con detección automática de modelos."""
        cfg_actual = {
            "proveedor": self.proveedor,
            "modelo": self.modelo,
            "api_key": self.api_key,
            "api_keys": self.cfg.get("api_keys", {}),
        }
        colores = {"bg":"#1a1a2e","bg2":"#282a36","fg":"#f8f8f2",
                   "accent":"#a78bfa","warn":"#fbbf24","ok":"#22c55e"}
        def on_save(nuevo):
            self.proveedor = nuevo["proveedor"]
            self.modelo = nuevo["modelo"]
            self.api_key = nuevo["api_key"]
            self.cfg["reader_proveedor"] = self.proveedor
            self.cfg["reader_modelo"] = self.modelo
            self.cfg["api_keys"] = nuevo["api_keys"]
            with open(CONFIG, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, indent=2)
        dialogo_config(self.root, cfg_actual, on_save,
                       titulo="⚙ Configuración Reader", colores=colores)

def main(): NovaReader().root.mainloop()
if __name__ == "__main__": main()
