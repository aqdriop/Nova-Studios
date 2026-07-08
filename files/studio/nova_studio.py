"""
🎬 NOVA STUDIO — Generador multimedia con IA
=============================================
Crea proyectos audiovisuales completos en minutos:
  📝 Guión generado por IA
  🎨 Imágenes generadas con Pollinations (gratis)
  🔊 Audio TTS con Edge-TTS (voces españolas)
  📦 Proyectos organizados con manifest.json
  🎞️ Storyboard visual con miniaturas
  🎵 Reproductor integrado

Parte del ecosistema NOVA AI.
"""
import os, sys, json, threading, re, time, base64
import urllib.request, urllib.parse, urllib.error
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from datetime import datetime

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# VERSION (para el sistema de actualizaciones)
# ============================================================
VERSION = "1.0.0"
MODULO_ID = "studio"

PARENT = os.path.dirname(APP_DIR)
CONFIG = os.path.join(PARENT, "config.json")
PROYECTOS_DIR = os.path.join(APP_DIR, "proyectos")
os.makedirs(PROYECTOS_DIR, exist_ok=True)

# Importar librería compartida de IA
sys.path.insert(0, APP_DIR)
from nova_ia_lib import llamar_llm, dialogo_config, listar_modelos

# Pillow para mostrar miniaturas
try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False

# pygame para reproducir audio (opcional)
try:
    import pygame
    pygame.mixer.init()
    PYGAME_OK = True
except Exception:
    PYGAME_OK = False

# edge-tts para voces (opcional, fallback a gTTS si no)
try:
    import edge_tts, asyncio
    EDGE_OK = True
except ImportError:
    EDGE_OK = False

try:
    from gtts import gTTS
    GTTS_OK = True
except ImportError:
    GTTS_OK = False

# ============================================================
# CONSTANTES
# ============================================================
ESTILOS_VISUALES = {
    "🎬 Cinematográfico": "cinematic, dramatic lighting, ultra detailed, 8k, professional photography",
    "🌸 Anime": "anime style, vibrant colors, studio ghibli, detailed manga art",
    "🕹️ Pixel Art": "pixel art, 16-bit retro game style, vibrant colors, sharp pixels",
    "🎨 Acuarela": "watercolor painting, soft brushes, artistic, pastel colors",
    "🧊 3D Render": "3D render, octane render, pixar style, soft lighting",
    "📷 Fotorrealista": "photorealistic, DSLR photo, natural lighting, sharp focus, high detail",
    "💥 Cómic": "comic book style, bold lines, vibrant colors, ink illustration",
    "📼 Retro 80s": "retro 80s aesthetic, neon colors, synthwave, vhs effect, vaporwave",
    "🌑 Dark Fantasy": "dark fantasy art, gothic, moody atmosphere, hyper detailed",
    "✨ Ilustración Infantil": "children book illustration, cute, colorful, simple shapes",
}

TIPOS_PROYECTO = {
    "🎞️ Vídeo corto (TikTok/Reel)": {
        "n_escenas": 5,
        "duracion": "15-30 segundos total",
        "prompt": "guión vertical para vídeo corto viral de redes sociales, MUY conciso, gancho fuerte al inicio",
    },
    "📖 Historia/Cuento": {
        "n_escenas": 8,
        "duracion": "narrativa completa",
        "prompt": "cuento narrativo con introducción, nudo y desenlace claros",
    },
    "📢 Anuncio publicitario": {
        "n_escenas": 4,
        "duracion": "30 segundos",
        "prompt": "anuncio publicitario persuasivo con llamada a la acción",
    },
    "🎓 Tutorial paso a paso": {
        "n_escenas": 6,
        "duracion": "1-2 minutos",
        "prompt": "tutorial educativo dividido en pasos claros y numerados",
    },
    "📺 Booktrailer/Promo": {
        "n_escenas": 6,
        "duracion": "45 segundos",
        "prompt": "trailer promocional misterioso e intrigante",
    },
    "🎙️ Podcast (sólo audio)": {
        "n_escenas": 1,
        "duracion": "2-3 minutos",
        "prompt": "monólogo de podcast informal y atractivo",
    },
    "📰 Resumen de noticia": {
        "n_escenas": 4,
        "duracion": "1 minuto",
        "prompt": "resumen informativo objetivo de una noticia",
    },
}

VOCES_TTS = {
    "👩 Elvira (España)": "es-ES-ElviraNeural",
    "👨 Álvaro (España)": "es-ES-AlvaroNeural",
    "👩 Ximena (España)": "es-ES-XimenaNeural",
    "👩 Dalia (México)": "es-MX-DaliaNeural",
    "👨 Jorge (México)": "es-MX-JorgeNeural",
    "👩 Elena (Argentina)": "es-AR-ElenaNeural",
    "👩 Salomé (Colombia)": "es-CO-SalomeNeural",
}

USER_AGENT = "NovaStudio/1.0 (Educational)"

# ============================================================
# COLORES
# ============================================================
C = {
    "bg":      "#0c0a1f",   # fondo principal (morado muy oscuro)
    "bg2":     "#1a1438",   # fondo secundario
    "bg3":     "#251b50",   # tarjetas
    "fg":      "#e9d5ff",   # texto principal (lavanda)
    "fg2":     "#a78bfa",   # texto secundario (violeta)
    "accent":  "#ec4899",   # acento (rosa fuerte)
    "accent2": "#f59e0b",   # secundario (oro)
    "ok":      "#22c55e",
    "warn":    "#fbbf24",
    "err":     "#ef4444",
}

# ============================================================
# UTILIDADES
# ============================================================
def slugify(texto):
    """Convierte texto en nombre de archivo seguro."""
    texto = re.sub(r"[^\w\s-]", "", texto).strip().lower()
    texto = re.sub(r"[-\s]+", "_", texto)
    return texto[:50] or "proyecto"

def generar_imagen_pollinations(prompt, ruta_salida, width=1024, height=1024,
                                  seed=None):
    """
    Descarga una imagen generada por Pollinations.ai (100% GRATIS, sin API key).
    """
    slug = urllib.parse.quote(prompt)
    url = (f"https://image.pollinations.ai/prompt/{slug}"
           f"?width={width}&height={height}&nologo=true")
    if seed is not None:
        url += f"&seed={seed}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        with open(ruta_salida, "wb") as f:
            f.write(r.read())
    return ruta_salida

def generar_audio_edge(texto, ruta_salida, voz="es-ES-ElviraNeural", velocidad="+0%"):
    """Genera audio TTS con edge-tts (la mejor calidad gratuita)."""
    async def _gen():
        comm = edge_tts.Communicate(texto, voz, rate=velocidad)
        await comm.save(ruta_salida)
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_gen())
        loop.close()
        return True
    except Exception as e:
        print(f"Edge-TTS falló: {e}")
        return False

def generar_audio_gtts(texto, ruta_salida, lang="es"):
    """Fallback con gTTS."""
    try:
        tts = gTTS(text=texto, lang=lang)
        tts.save(ruta_salida)
        return True
    except Exception:
        return False

# ============================================================
# APLICACIÓN PRINCIPAL
# ============================================================
class NovaStudio:
    def __init__(self, root):
        self.root = root
        self.root.title("🎬 NOVA Studio — Generador multimedia")
        self.root.geometry("1280x780")
        self.root.configure(bg=C["bg"])

        # Cargar config
        self.cfg = self._cargar_config()
        self.proveedor = self.cfg.get("studio_proveedor", "Groq")
        self.modelo = self.cfg.get("studio_modelo", "llama-3.3-70b-versatile")
        self.api_key = self.cfg.get("api_keys", {}).get(self.proveedor, "")
        self.voz = self.cfg.get("studio_voz", "es-ES-ElviraNeural")
        self.estilo = self.cfg.get("studio_estilo", "🎬 Cinematográfico")

        # Estado del proyecto actual
        self.proyecto_actual = None
        self.escenas = []  # [{texto, prompt_img, ruta_img, ruta_audio}]
        self.miniaturas = []  # Para evitar GC de tkinter
        self.procesando = False

        self._construir_ui()
        self._refrescar_proyectos()

    def _cargar_config(self):
        try:
            with open(CONFIG, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"api_keys": {}}

    def _guardar_config(self):
        try:
            with open(CONFIG, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, indent=2)
        except Exception as e:
            print(f"Error guardando config: {e}")

    # ----------------------------------------------------------
    # UI
    # ----------------------------------------------------------
    def _construir_ui(self):
        # Header
        header = tk.Frame(self.root, bg=C["bg2"], height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="🎬 NOVA Studio",
                 bg=C["bg2"], fg=C["accent"],
                 font=("Segoe UI", 18, "bold")).pack(side="left", padx=20)
        tk.Label(header, text="Generador multimedia con IA",
                 bg=C["bg2"], fg=C["fg2"],
                 font=("Segoe UI", 10, "italic")).pack(side="left", padx=5)

        # Botones header
        for txt, cmd, color in [
            ("⚙ Config IA", self._config_ia, C["bg3"]),
            ("🎙️ Voz TTS", self._config_voz, C["bg3"]),
            ("🎨 Estilo", self._config_estilo, C["bg3"]),
            ("📖 Ayuda", self._mostrar_ayuda, C["bg3"]),
        ]:
            tk.Button(header, text=txt, command=cmd,
                      bg=color, fg=C["fg"], relief="flat",
                      font=("Segoe UI", 9, "bold"), cursor="hand2",
                      padx=12, pady=4).pack(side="right", padx=4, pady=10)

        # Layout principal: izquierda (lista proyectos) | derecha (editor)
        main = tk.Frame(self.root, bg=C["bg"])
        main.pack(fill="both", expand=True)

        # ===== Sidebar izquierda =====
        sidebar = tk.Frame(main, bg=C["bg2"], width=260)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="📁 PROYECTOS",
                 bg=C["bg2"], fg=C["accent2"],
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(12, 6))

        tk.Button(sidebar, text="➕ Nuevo proyecto",
                  command=self._nuevo_proyecto_dialog,
                  bg=C["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 10, "bold"), cursor="hand2",
                  pady=6).pack(fill="x", padx=12, pady=(0, 8))

        # Lista de proyectos
        list_frame = tk.Frame(sidebar, bg=C["bg2"])
        list_frame.pack(fill="both", expand=True, padx=12, pady=6)
        scrollbar = tk.Scrollbar(list_frame, bg=C["bg2"])
        scrollbar.pack(side="right", fill="y")
        self.lista_proy = tk.Listbox(list_frame,
            bg=C["bg3"], fg=C["fg"], selectbackground=C["accent"],
            font=("Segoe UI", 10), relief="flat", borderwidth=0,
            yscrollcommand=scrollbar.set, activestyle="none")
        self.lista_proy.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.lista_proy.yview)
        self.lista_proy.bind("<<ListboxSelect>>", self._on_seleccion_proyecto)

        # Botones inferiores sidebar
        sb_btns = tk.Frame(sidebar, bg=C["bg2"])
        sb_btns.pack(fill="x", padx=12, pady=8)
        tk.Button(sb_btns, text="📂 Abrir carpeta", command=self._abrir_carpeta,
                  bg=C["bg3"], fg=C["fg"], relief="flat",
                  font=("Segoe UI", 9), cursor="hand2").pack(fill="x", pady=2)
        tk.Button(sb_btns, text="🗑️ Borrar proyecto", command=self._borrar_proyecto,
                  bg=C["err"], fg="white", relief="flat",
                  font=("Segoe UI", 9), cursor="hand2").pack(fill="x", pady=2)

        # ===== Editor derecha =====
        editor = tk.Frame(main, bg=C["bg"])
        editor.pack(side="right", fill="both", expand=True, padx=12, pady=12)

        # Notebook con pestañas
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TNotebook", background=C["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=C["bg2"], foreground=C["fg"],
                         padding=[18, 8], font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", C["accent"])],
                   foreground=[("selected", "white")])

        self.notebook = ttk.Notebook(editor)
        self.notebook.pack(fill="both", expand=True)

        # --- Pestaña 1: Guión ---
        tab1 = tk.Frame(self.notebook, bg=C["bg"])
        self.notebook.add(tab1, text="📝 Guión")

        tk.Label(tab1, text="Tu idea / tema del proyecto:",
                 bg=C["bg"], fg=C["accent2"],
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 4))
        self.entry_idea = tk.Entry(tab1, bg=C["bg3"], fg=C["fg"],
            insertbackground=C["fg"], relief="flat",
            font=("Segoe UI", 11))
        self.entry_idea.pack(fill="x", padx=10, ipady=8)

        # Opciones de tipo
        opt_frame = tk.Frame(tab1, bg=C["bg"])
        opt_frame.pack(fill="x", padx=10, pady=10)

        tk.Label(opt_frame, text="Tipo:", bg=C["bg"], fg=C["fg2"],
                 font=("Segoe UI", 10)).pack(side="left", padx=(0, 6))
        self.tipo_var = tk.StringVar(value="🎞️ Vídeo corto (TikTok/Reel)")
        tipo_combo = ttk.Combobox(opt_frame, textvariable=self.tipo_var,
            values=list(TIPOS_PROYECTO.keys()),
            state="readonly", width=30, font=("Segoe UI", 10))
        tipo_combo.pack(side="left", padx=(0, 18))

        tk.Label(opt_frame, text="Idioma:", bg=C["bg"], fg=C["fg2"],
                 font=("Segoe UI", 10)).pack(side="left", padx=(0, 6))
        self.idioma_var = tk.StringVar(value="Español")
        ttk.Combobox(opt_frame, textvariable=self.idioma_var,
            values=["Español", "English", "Français", "Italiano",
                    "Português", "Deutsch"],
            state="readonly", width=12, font=("Segoe UI", 10)).pack(side="left")

        # Botón generar guión
        tk.Button(tab1, text="✨ Generar guión con IA",
                  command=self._generar_guion,
                  bg=C["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 11, "bold"), cursor="hand2",
                  pady=8).pack(fill="x", padx=10, pady=(8, 10))

        # Área de texto del guión
        tk.Label(tab1, text="Guión generado (puedes editarlo):",
                 bg=C["bg"], fg=C["accent2"],
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(6, 4))
        self.txt_guion = scrolledtext.ScrolledText(tab1,
            bg=C["bg3"], fg=C["fg"], insertbackground=C["fg"],
            font=("Consolas", 10), wrap="word", relief="flat",
            padx=10, pady=10)
        self.txt_guion.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        # Botones inferiores guión
        bf1 = tk.Frame(tab1, bg=C["bg"])
        bf1.pack(fill="x", padx=10, pady=8)
        tk.Button(bf1, text="💾 Guardar guión", command=self._guardar_guion,
                  bg=C["bg3"], fg=C["fg"], relief="flat",
                  font=("Segoe UI", 10), cursor="hand2",
                  padx=14, pady=6).pack(side="left", padx=4)
        tk.Button(bf1, text="🎨 Generar IMÁGENES de las escenas →",
                  command=self._generar_imagenes,
                  bg=C["accent2"], fg=C["bg"], relief="flat",
                  font=("Segoe UI", 10, "bold"), cursor="hand2",
                  padx=14, pady=6).pack(side="right", padx=4)

        # --- Pestaña 2: Storyboard ---
        tab2 = tk.Frame(self.notebook, bg=C["bg"])
        self.notebook.add(tab2, text="🎨 Storyboard")

        tk.Label(tab2, text="Storyboard visual — miniaturas de cada escena",
                 bg=C["bg"], fg=C["accent2"],
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=10)

        # Canvas con scroll para el storyboard
        story_container = tk.Frame(tab2, bg=C["bg"])
        story_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        canvas = tk.Canvas(story_container, bg=C["bg"],
                            highlightthickness=0)
        sb = tk.Scrollbar(story_container, orient="vertical",
                          command=canvas.yview, bg=C["bg2"])
        self.story_frame = tk.Frame(canvas, bg=C["bg"])

        self.story_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.story_frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)

        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.story_canvas = canvas

        # Permite scroll con rueda
        def _on_mw(e):
            canvas.yview_scroll(-int(e.delta / 60), "units")
        canvas.bind_all("<MouseWheel>", _on_mw)

        # --- Pestaña 3: Audio ---
        tab3 = tk.Frame(self.notebook, bg=C["bg"])
        self.notebook.add(tab3, text="🔊 Audio")

        tk.Label(tab3, text="Generación de audio narrativo (TTS)",
                 bg=C["bg"], fg=C["accent2"],
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=10)

        audio_info = tk.Frame(tab3, bg=C["bg3"])
        audio_info.pack(fill="x", padx=10, pady=(0, 10))
        self.lbl_voz = tk.Label(audio_info, text=f"🎙️ Voz actual: {self.voz}",
                                 bg=C["bg3"], fg=C["fg"],
                                 font=("Segoe UI", 10), anchor="w")
        self.lbl_voz.pack(fill="x", padx=12, pady=8)

        if not EDGE_OK and not GTTS_OK:
            tk.Label(tab3,
                text="⚠️ Sin librería TTS. Instala:\n"
                     "  pip install edge-tts\n  pip install gtts",
                bg=C["bg"], fg=C["warn"],
                font=("Consolas", 9), justify="left").pack(anchor="w", padx=10)
        else:
            engine = "edge-tts (alta calidad)" if EDGE_OK else "gTTS (básico)"
            tk.Label(tab3, text=f"✅ Motor TTS: {engine}",
                bg=C["bg"], fg=C["ok"],
                font=("Segoe UI", 9)).pack(anchor="w", padx=10)

        tk.Button(tab3, text="🎤 Generar AUDIO de todas las escenas",
                  command=self._generar_audio,
                  bg=C["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 11, "bold"), cursor="hand2",
                  pady=8).pack(fill="x", padx=10, pady=10)

        # Lista de audios
        tk.Label(tab3, text="Audios generados:",
                 bg=C["bg"], fg=C["accent2"],
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(8, 4))

        audio_list_frame = tk.Frame(tab3, bg=C["bg"])
        audio_list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        sb_a = tk.Scrollbar(audio_list_frame)
        sb_a.pack(side="right", fill="y")
        self.lista_audio = tk.Listbox(audio_list_frame,
            bg=C["bg3"], fg=C["fg"], selectbackground=C["accent"],
            font=("Consolas", 10), relief="flat",
            yscrollcommand=sb_a.set, activestyle="none")
        self.lista_audio.pack(side="left", fill="both", expand=True)
        sb_a.config(command=self.lista_audio.yview)
        self.lista_audio.bind("<Double-Button-1>",
            lambda e: self._reproducir_audio_seleccionado())

        # Botones audio
        bfa = tk.Frame(tab3, bg=C["bg"])
        bfa.pack(fill="x", padx=10, pady=8)
        tk.Button(bfa, text="▶ Reproducir seleccionado",
                  command=self._reproducir_audio_seleccionado,
                  bg=C["bg3"], fg=C["fg"], relief="flat",
                  font=("Segoe UI", 10), cursor="hand2",
                  padx=12, pady=6).pack(side="left", padx=4)
        tk.Button(bfa, text="⏸ Parar",
                  command=self._parar_audio,
                  bg=C["bg3"], fg=C["fg"], relief="flat",
                  font=("Segoe UI", 10), cursor="hand2",
                  padx=12, pady=6).pack(side="left", padx=4)

        # --- Pestaña 4: Exportar ---
        tab4 = tk.Frame(self.notebook, bg=C["bg"])
        self.notebook.add(tab4, text="📦 Exportar")

        tk.Label(tab4, text="📦 Exportar y compartir tu proyecto",
                 bg=C["bg"], fg=C["accent2"],
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=20, pady=20)

        export_info = tk.Frame(tab4, bg=C["bg3"])
        export_info.pack(fill="x", padx=20, pady=10)
        tk.Label(export_info,
            text=("Tu proyecto se guarda automáticamente en:\n"
                  f"  {PROYECTOS_DIR}\\<nombre>\\\n\n"
                  "Contenido de cada proyecto:\n"
                  "  • guion.txt         (guión completo)\n"
                  "  • manifest.json     (metadata)\n"
                  "  • escena_01.png     (imágenes)\n"
                  "  • escena_01.mp3     (audios)\n"
                  "  • storyboard.html   (vista previa web)"),
            bg=C["bg3"], fg=C["fg"], font=("Consolas", 10),
            justify="left", anchor="w").pack(fill="x", padx=16, pady=12)

        tk.Button(tab4, text="🌐 Generar STORYBOARD HTML (todo en uno)",
                  command=self._exportar_html,
                  bg=C["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 11, "bold"), cursor="hand2",
                  pady=8).pack(fill="x", padx=20, pady=8)

        tk.Button(tab4, text="📂 Abrir carpeta del proyecto actual",
                  command=self._abrir_carpeta,
                  bg=C["bg3"], fg=C["fg"], relief="flat",
                  font=("Segoe UI", 10), cursor="hand2",
                  pady=6).pack(fill="x", padx=20, pady=4)

        tk.Button(tab4, text="🎬 Generar SCRIPT FFmpeg para hacer vídeo",
                  command=self._generar_ffmpeg,
                  bg=C["bg3"], fg=C["fg"], relief="flat",
                  font=("Segoe UI", 10), cursor="hand2",
                  pady=6).pack(fill="x", padx=20, pady=4)

        # ===== Status bar =====
        self.status = tk.Label(self.root,
            text="🎬 NOVA Studio listo. Crea un proyecto nuevo para empezar.",
            bg=C["bg2"], fg=C["fg2"],
            font=("Segoe UI", 9), anchor="w", padx=12)
        self.status.pack(side="bottom", fill="x")

    # ----------------------------------------------------------
    # Gestión de proyectos
    # ----------------------------------------------------------
    def _refrescar_proyectos(self):
        self.lista_proy.delete(0, "end")
        if not os.path.exists(PROYECTOS_DIR):
            return
        proyectos = sorted([d for d in os.listdir(PROYECTOS_DIR)
                             if os.path.isdir(os.path.join(PROYECTOS_DIR, d))],
                            reverse=True)
        for p in proyectos:
            self.lista_proy.insert("end", f"  📁 {p}")

    def _nuevo_proyecto_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("➕ Nuevo proyecto")
        dlg.geometry("440x200")
        dlg.configure(bg=C["bg"])
        dlg.transient(self.root)

        tk.Label(dlg, text="✨ Nombre del nuevo proyecto",
                 bg=C["bg"], fg=C["accent"],
                 font=("Segoe UI", 12, "bold")).pack(pady=12)

        tk.Label(dlg, text="Ej: aventura_dragones, receta_paella, viaje_japon...",
                 bg=C["bg"], fg=C["fg2"], font=("Segoe UI", 9)).pack()

        nombre_var = tk.StringVar(
            value=f"proyecto_{datetime.now().strftime('%Y%m%d_%H%M')}")
        e = tk.Entry(dlg, textvariable=nombre_var,
                     bg=C["bg3"], fg=C["fg"], insertbackground=C["fg"],
                     relief="flat", font=("Segoe UI", 11), justify="center")
        e.pack(fill="x", padx=20, pady=10, ipady=6)
        e.select_range(0, "end")
        e.focus()

        def crear():
            nombre = slugify(nombre_var.get())
            if not nombre:
                messagebox.showwarning("⚠️", "Nombre inválido"); return
            ruta = os.path.join(PROYECTOS_DIR, nombre)
            if os.path.exists(ruta):
                if not messagebox.askyesno("Existe",
                    f"El proyecto '{nombre}' ya existe. ¿Abrirlo?"):
                    return
            os.makedirs(ruta, exist_ok=True)
            self.proyecto_actual = nombre
            self.escenas = []
            self.txt_guion.delete("1.0", "end")
            self._refrescar_proyectos()
            self._actualizar_storyboard()
            self._actualizar_lista_audio()
            self.status.config(
                text=f"✅ Proyecto creado: {nombre}", fg=C["ok"])
            self.root.title(f"🎬 NOVA Studio — {nombre}")
            dlg.destroy()

        bf = tk.Frame(dlg, bg=C["bg"])
        bf.pack(pady=10)
        tk.Button(bf, text="✨ Crear", command=crear,
                  bg=C["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 10, "bold"), padx=20, pady=6,
                  cursor="hand2").pack(side="left", padx=6)
        tk.Button(bf, text="Cancelar", command=dlg.destroy,
                  bg=C["bg3"], fg=C["fg"], relief="flat",
                  font=("Segoe UI", 10), padx=16, pady=6,
                  cursor="hand2").pack(side="left", padx=6)

        dlg.bind("<Return>", lambda e: crear())

    def _on_seleccion_proyecto(self, evt=None):
        sel = self.lista_proy.curselection()
        if not sel: return
        nombre = self.lista_proy.get(sel[0]).strip().replace("📁 ", "")
        self.proyecto_actual = nombre
        self._cargar_proyecto()
        self.root.title(f"🎬 NOVA Studio — {nombre}")

    def _ruta_proyecto(self):
        if not self.proyecto_actual: return None
        return os.path.join(PROYECTOS_DIR, self.proyecto_actual)

    def _cargar_proyecto(self):
        ruta = self._ruta_proyecto()
        if not ruta: return
        # Cargar guión
        guion_path = os.path.join(ruta, "guion.txt")
        self.txt_guion.delete("1.0", "end")
        if os.path.exists(guion_path):
            with open(guion_path, "r", encoding="utf-8") as f:
                self.txt_guion.insert("1.0", f.read())
        # Cargar manifest
        manifest_path = os.path.join(ruta, "manifest.json")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.escenas = data.get("escenas", [])
                self.entry_idea.delete(0, "end")
                self.entry_idea.insert(0, data.get("idea", ""))
                if data.get("tipo"):
                    self.tipo_var.set(data["tipo"])
                if data.get("idioma"):
                    self.idioma_var.set(data["idioma"])
            except Exception:
                self.escenas = []
        else:
            self.escenas = []
        self._actualizar_storyboard()
        self._actualizar_lista_audio()
        self.status.config(text=f"📂 Proyecto cargado: {self.proyecto_actual}",
                            fg=C["fg"])

    def _guardar_manifest(self):
        ruta = self._ruta_proyecto()
        if not ruta: return
        manifest = {
            "nombre": self.proyecto_actual,
            "idea": self.entry_idea.get(),
            "tipo": self.tipo_var.get(),
            "idioma": self.idioma_var.get(),
            "estilo": self.estilo,
            "voz": self.voz,
            "fecha": datetime.now().isoformat(),
            "escenas": self.escenas,
        }
        with open(os.path.join(ruta, "manifest.json"), "w",
                   encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

    def _abrir_carpeta(self):
        ruta = self._ruta_proyecto()
        if not ruta or not os.path.exists(ruta):
            messagebox.showinfo("ℹ️", "Selecciona o crea un proyecto primero.")
            return
        try:
            os.startfile(ruta)  # Windows
        except AttributeError:
            import subprocess
            subprocess.Popen(["xdg-open", ruta])

    def _borrar_proyecto(self):
        if not self.proyecto_actual:
            messagebox.showinfo("ℹ️", "Selecciona un proyecto primero."); return
        if not messagebox.askyesno("⚠️ Borrar",
            f"¿Borrar el proyecto '{self.proyecto_actual}'?\nEsta acción NO se puede deshacer."):
            return
        import shutil
        try:
            shutil.rmtree(self._ruta_proyecto())
            self.proyecto_actual = None
            self.escenas = []
            self.txt_guion.delete("1.0", "end")
            self._refrescar_proyectos()
            self._actualizar_storyboard()
            self._actualizar_lista_audio()
            self.status.config(text="🗑️ Proyecto borrado", fg=C["warn"])
            self.root.title("🎬 NOVA Studio — Generador multimedia")
        except Exception as e:
            messagebox.showerror("❌", f"Error: {e}")

    # ----------------------------------------------------------
    # Generación del guión con IA
    # ----------------------------------------------------------
    def _generar_guion(self):
        if not self.proyecto_actual:
            messagebox.showinfo("ℹ️", "Crea un proyecto nuevo primero (➕)."); return
        idea = self.entry_idea.get().strip()
        if not idea:
            messagebox.showwarning("⚠️", "Escribe primero tu idea / tema."); return
        if not self.api_key and self.proveedor != "Ollama":
            messagebox.showwarning("⚠️", "Configura tu API Key en ⚙ Config IA."); return
        if self.procesando:
            messagebox.showinfo("ℹ️", "Espera, ya hay una tarea en proceso."); return

        tipo = TIPOS_PROYECTO[self.tipo_var.get()]
        idioma = self.idioma_var.get()
        self.procesando = True
        self.status.config(text="✨ Generando guión con IA...", fg=C["accent"])
        self.txt_guion.delete("1.0", "end")
        self.txt_guion.insert("1.0",
            "⏳ La IA está escribiendo tu guión...\n\nEsto puede tardar 10-30 segundos.")

        def tarea():
            system = (
                f"Eres un guionista profesional experto en {self.tipo_var.get()}. "
                f"Escribes en {idioma}. Eres creativo, claro y conciso."
            )
            user = f"""Crea un guión sobre: "{idea}"

Tipo: {tipo['prompt']}
Duración aproximada: {tipo['duracion']}
Número de escenas: {tipo['n_escenas']}

DEVUELVE EXACTAMENTE este formato (sin marcadores adicionales):

ESCENA 1:
NARRACIÓN: [texto que se leerá en voz alta, máximo 2-3 frases]
VISUAL: [descripción visual MUY detallada en INGLÉS para generar imagen, incluyendo elementos, ambiente, luces, ángulo]

ESCENA 2:
NARRACIÓN: ...
VISUAL: ...

(continúa hasta ESCENA {tipo['n_escenas']})

Reglas:
- NARRACIÓN debe ser natural cuando se diga en voz alta
- VISUAL debe ser MUY descriptiva, en inglés, sin diálogos
- NO añadas títulos extra, marcadores markdown ni notas
- Mantén coherencia visual entre escenas"""

            resp, err = llamar_llm(self.proveedor, self.modelo, self.api_key,
                                    system, user)
            self.root.after(0, self._guion_completo, resp, err)

        threading.Thread(target=tarea, daemon=True).start()

    def _guion_completo(self, resp, err):
        self.procesando = False
        self.txt_guion.delete("1.0", "end")
        if err:
            self.txt_guion.insert("1.0", f"❌ Error: {err}")
            self.status.config(text=f"❌ {err}", fg=C["err"])
            return
        self.txt_guion.insert("1.0", resp)
        # Parsear escenas
        self.escenas = self._parsear_guion(resp)
        self.status.config(
            text=f"✅ Guión listo: {len(self.escenas)} escenas detectadas",
            fg=C["ok"])
        self._guardar_guion()

    def _parsear_guion(self, texto):
        """Extrae escenas del formato ESCENA N: NARRACIÓN/VISUAL."""
        escenas = []
        # Dividir por "ESCENA N:"
        bloques = re.split(r"ESCENA\s+\d+\s*:", texto, flags=re.IGNORECASE)
        for bloque in bloques[1:]:  # primer split es vacío o intro
            narr = re.search(
                r"NARRACI[ÓO]N\s*:\s*(.+?)(?=\n\s*VISUAL|\Z)",
                bloque, re.DOTALL | re.IGNORECASE)
            visual = re.search(
                r"VISUAL\s*:\s*(.+?)(?=\n\s*ESCENA|\Z)",
                bloque, re.DOTALL | re.IGNORECASE)
            if narr:
                escenas.append({
                    "narracion": narr.group(1).strip(),
                    "prompt_img": (visual.group(1).strip()
                                    if visual else "scene illustration"),
                    "ruta_img": "",
                    "ruta_audio": "",
                })
        return escenas

    def _guardar_guion(self):
        if not self.proyecto_actual:
            messagebox.showinfo("ℹ️", "Crea un proyecto primero."); return
        ruta = self._ruta_proyecto()
        guion = self.txt_guion.get("1.0", "end").strip()
        with open(os.path.join(ruta, "guion.txt"), "w", encoding="utf-8") as f:
            f.write(guion)
        # Reparsear por si el usuario editó
        self.escenas = self._parsear_guion(guion)
        self._guardar_manifest()
        self.status.config(
            text=f"💾 Guión guardado ({len(self.escenas)} escenas)", fg=C["ok"])

    # ----------------------------------------------------------
    # Generación de imágenes
    # ----------------------------------------------------------
    def _generar_imagenes(self):
        if not self.proyecto_actual:
            messagebox.showinfo("ℹ️", "Crea un proyecto primero."); return
        # Asegurar guion parseado
        self._guardar_guion()
        if not self.escenas:
            messagebox.showwarning("⚠️",
                "No hay escenas. Genera primero el guión."); return
        if self.procesando:
            messagebox.showinfo("ℹ️", "Espera, ya hay una tarea en proceso."); return

        self.procesando = True
        ruta = self._ruta_proyecto()
        estilo_prompt = ESTILOS_VISUALES.get(self.estilo, "")
        n = len(self.escenas)

        self.status.config(
            text=f"🎨 Generando {n} imágenes con Pollinations.ai...",
            fg=C["accent"])
        self.notebook.select(1)  # ir a pestaña Storyboard

        def tarea():
            seed_base = int(time.time()) % 100000
            for i, esc in enumerate(self.escenas):
                self.root.after(0, lambda i=i, n=n: self.status.config(
                    text=f"🎨 Generando imagen {i+1}/{n}... (~15s cada una)",
                    fg=C["accent"]))
                prompt = f"{esc['prompt_img']}, {estilo_prompt}"
                ruta_img = os.path.join(ruta, f"escena_{i+1:02d}.png")
                try:
                    generar_imagen_pollinations(prompt, ruta_img,
                        width=1024, height=1024, seed=seed_base + i)
                    esc["ruta_img"] = ruta_img
                    self.root.after(0, self._actualizar_storyboard)
                except Exception as e:
                    print(f"Error escena {i+1}: {e}")
                    self.root.after(0, lambda e=e: self.status.config(
                        text=f"⚠️ Error en una escena: {str(e)[:60]}",
                        fg=C["warn"]))
                time.sleep(1)  # respetar Pollinations
            self._guardar_manifest()
            self.root.after(0, lambda: self.status.config(
                text=f"✅ {n} imágenes generadas en el storyboard",
                fg=C["ok"]))
            self.procesando = False

        threading.Thread(target=tarea, daemon=True).start()

    # ----------------------------------------------------------
    # Storyboard visual
    # ----------------------------------------------------------
    def _actualizar_storyboard(self):
        for w in self.story_frame.winfo_children():
            w.destroy()
        self.miniaturas = []

        if not self.escenas:
            tk.Label(self.story_frame,
                text="📭 Aún no hay escenas.\n\nGenera el guión y las imágenes desde la pestaña 📝 Guión.",
                bg=C["bg"], fg=C["fg2"], font=("Segoe UI", 11),
                justify="center").pack(pady=50)
            return

        for i, esc in enumerate(self.escenas):
            card = tk.Frame(self.story_frame, bg=C["bg3"], bd=0,
                             highlightthickness=1,
                             highlightbackground=C["bg2"])
            card.pack(fill="x", padx=4, pady=6)

            # Imagen miniatura
            left = tk.Frame(card, bg=C["bg3"])
            left.pack(side="left", padx=8, pady=8)

            if esc.get("ruta_img") and os.path.exists(esc["ruta_img"]) and PIL_OK:
                try:
                    img = Image.open(esc["ruta_img"])
                    img.thumbnail((180, 180))
                    photo = ImageTk.PhotoImage(img)
                    self.miniaturas.append(photo)  # evitar GC
                    img_lbl = tk.Label(left, image=photo, bg=C["bg3"],
                                        cursor="hand2")
                    img_lbl.pack()
                    img_lbl.bind("<Button-1>",
                        lambda e, r=esc["ruta_img"]: self._abrir_imagen(r))
                except Exception as e:
                    tk.Label(left, text=f"⚠️\n{str(e)[:30]}",
                             bg=C["bg3"], fg=C["err"],
                             width=20, height=10).pack()
            else:
                placeholder = tk.Label(left,
                    text="🖼️\n(sin imagen)",
                    bg=C["bg2"], fg=C["fg2"],
                    width=20, height=10, font=("Segoe UI", 10))
                placeholder.pack()

            # Info de la escena
            right = tk.Frame(card, bg=C["bg3"])
            right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

            tk.Label(right, text=f"🎬 ESCENA {i+1}",
                     bg=C["bg3"], fg=C["accent"],
                     font=("Segoe UI", 11, "bold"),
                     anchor="w").pack(fill="x")

            tk.Label(right, text="🗣️ NARRACIÓN:",
                     bg=C["bg3"], fg=C["accent2"],
                     font=("Segoe UI", 9, "bold"),
                     anchor="w").pack(fill="x", pady=(4, 0))
            tk.Label(right, text=esc["narracion"][:300],
                     bg=C["bg3"], fg=C["fg"],
                     font=("Segoe UI", 9), wraplength=600,
                     justify="left", anchor="w").pack(fill="x")

            tk.Label(right, text="🎨 VISUAL (prompt):",
                     bg=C["bg3"], fg=C["accent2"],
                     font=("Segoe UI", 9, "bold"),
                     anchor="w").pack(fill="x", pady=(6, 0))
            tk.Label(right, text=esc["prompt_img"][:200] + "...",
                     bg=C["bg3"], fg=C["fg2"],
                     font=("Consolas", 8, "italic"), wraplength=600,
                     justify="left", anchor="w").pack(fill="x")

            # Botón regenerar imagen
            tk.Button(right, text="🔄 Regenerar esta imagen",
                command=lambda i=i: self._regenerar_imagen(i),
                bg=C["bg2"], fg=C["fg"], relief="flat",
                font=("Segoe UI", 8), cursor="hand2",
                padx=8, pady=2).pack(anchor="w", pady=(8, 0))

    def _abrir_imagen(self, ruta):
        try: os.startfile(ruta)
        except AttributeError:
            import subprocess; subprocess.Popen(["xdg-open", ruta])

    def _regenerar_imagen(self, idx):
        if self.procesando:
            messagebox.showinfo("ℹ️", "Espera, ya hay tarea en curso."); return
        if idx >= len(self.escenas): return
        self.procesando = True
        esc = self.escenas[idx]
        ruta = self._ruta_proyecto()
        estilo_prompt = ESTILOS_VISUALES.get(self.estilo, "")
        ruta_img = os.path.join(ruta, f"escena_{idx+1:02d}.png")
        prompt = f"{esc['prompt_img']}, {estilo_prompt}"
        self.status.config(text=f"🔄 Regenerando imagen {idx+1}...",
                            fg=C["accent"])

        def tarea():
            try:
                generar_imagen_pollinations(prompt, ruta_img,
                    seed=int(time.time()) % 100000)
                esc["ruta_img"] = ruta_img
                self._guardar_manifest()
                self.root.after(0, self._actualizar_storyboard)
                self.root.after(0, lambda: self.status.config(
                    text=f"✅ Imagen {idx+1} regenerada", fg=C["ok"]))
            except Exception as e:
                self.root.after(0, lambda: self.status.config(
                    text=f"❌ {e}", fg=C["err"]))
            self.procesando = False

        threading.Thread(target=tarea, daemon=True).start()

    # ----------------------------------------------------------
    # Audio TTS
    # ----------------------------------------------------------
    def _generar_audio(self):
        if not self.proyecto_actual:
            messagebox.showinfo("ℹ️", "Crea un proyecto primero."); return
        self._guardar_guion()
        if not self.escenas:
            messagebox.showwarning("⚠️", "No hay escenas."); return
        if not EDGE_OK and not GTTS_OK:
            messagebox.showerror("❌",
                "Instala edge-tts:\n  pip install edge-tts\n\n"
                "O alternativamente:\n  pip install gtts"); return
        if self.procesando:
            messagebox.showinfo("ℹ️", "Espera, ya hay tarea en curso."); return

        self.procesando = True
        ruta = self._ruta_proyecto()
        n = len(self.escenas)
        self.status.config(text=f"🎤 Generando {n} audios...", fg=C["accent"])

        def tarea():
            for i, esc in enumerate(self.escenas):
                self.root.after(0, lambda i=i, n=n: self.status.config(
                    text=f"🎤 Generando audio {i+1}/{n}...", fg=C["accent"]))
                texto = esc["narracion"]
                ruta_audio = os.path.join(ruta, f"escena_{i+1:02d}.mp3")
                ok = False
                if EDGE_OK:
                    ok = generar_audio_edge(texto, ruta_audio, voz=self.voz)
                if not ok and GTTS_OK:
                    ok = generar_audio_gtts(texto, ruta_audio)
                if ok:
                    esc["ruta_audio"] = ruta_audio
                else:
                    print(f"Fallo audio escena {i+1}")
            self._guardar_manifest()
            self.root.after(0, self._actualizar_lista_audio)
            self.root.after(0, lambda: self.status.config(
                text=f"✅ {n} audios generados", fg=C["ok"]))
            self.procesando = False

        threading.Thread(target=tarea, daemon=True).start()

    def _actualizar_lista_audio(self):
        self.lista_audio.delete(0, "end")
        for i, esc in enumerate(self.escenas):
            ruta = esc.get("ruta_audio", "")
            estado = "✅" if (ruta and os.path.exists(ruta)) else "⏳"
            self.lista_audio.insert("end",
                f"  {estado}  Escena {i+1}: {esc['narracion'][:60]}...")

    def _reproducir_audio_seleccionado(self):
        if not PYGAME_OK:
            messagebox.showinfo("ℹ️",
                "Instala pygame para reproducir audio aquí:\n"
                "  pip install pygame\n\n"
                "O abre los archivos .mp3 manualmente."); return
        sel = self.lista_audio.curselection()
        if not sel: return
        idx = sel[0]
        if idx >= len(self.escenas): return
        ruta = self.escenas[idx].get("ruta_audio", "")
        if not ruta or not os.path.exists(ruta):
            messagebox.showinfo("ℹ️", "Esa escena no tiene audio aún."); return
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(ruta)
            pygame.mixer.music.play()
            self.status.config(text=f"▶ Reproduciendo escena {idx+1}",
                                fg=C["accent"])
        except Exception as e:
            messagebox.showerror("❌", str(e))

    def _parar_audio(self):
        if PYGAME_OK:
            try: pygame.mixer.music.stop()
            except Exception: pass

    # ----------------------------------------------------------
    # Exportar
    # ----------------------------------------------------------
    def _exportar_html(self):
        if not self.proyecto_actual or not self.escenas:
            messagebox.showinfo("ℹ️",
                "Necesitas un proyecto con escenas generadas."); return
        ruta = self._ruta_proyecto()
        idea = self.entry_idea.get() or self.proyecto_actual

        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>🎬 {self.proyecto_actual} — NOVA Studio</title>
<style>
  body {{
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: linear-gradient(135deg, #0c0a1f, #1a1438);
    color: #e9d5ff; padding: 32px; margin: 0;
  }}
  h1 {{ color: #ec4899; font-size: 2.4em; margin-bottom: 4px; }}
  h2 {{ color: #a78bfa; margin-top: 0; font-weight: normal; }}
  .meta {{ color: #f59e0b; margin-bottom: 24px; }}
  .escena {{
    background: rgba(37, 27, 80, 0.6); border-radius: 16px;
    padding: 20px; margin: 18px 0; display: flex; gap: 20px;
    align-items: flex-start; box-shadow: 0 4px 16px rgba(0,0,0,0.4);
  }}
  .escena img {{
    width: 320px; height: 320px; object-fit: cover;
    border-radius: 12px; box-shadow: 0 4px 16px rgba(236,72,153,0.3);
  }}
  .contenido {{ flex: 1; }}
  .num {{ color: #ec4899; font-weight: bold; font-size: 1.2em;
          margin-bottom: 6px; }}
  .narr {{ font-size: 1.05em; line-height: 1.6; margin: 10px 0; }}
  .visual {{ color: #a78bfa; font-size: 0.85em; font-style: italic;
              font-family: monospace; }}
  audio {{ width: 100%; margin-top: 12px; }}
  .footer {{ text-align: center; margin-top: 40px; color: #6b7280;
              font-size: 0.85em; }}
</style>
</head>
<body>
<h1>🎬 {self.proyecto_actual}</h1>
<h2>{idea}</h2>
<div class="meta">
  📅 {datetime.now().strftime('%d/%m/%Y %H:%M')} |
  🎨 {self.estilo} |
  🎙️ {self.voz} |
  📐 {self.tipo_var.get()}
</div>
"""

        for i, esc in enumerate(self.escenas):
            img_rel = f"escena_{i+1:02d}.png" if esc.get("ruta_img") else ""
            aud_rel = f"escena_{i+1:02d}.mp3" if esc.get("ruta_audio") else ""
            html += f'<div class="escena">\n'
            if img_rel:
                html += f'  <img src="{img_rel}" alt="Escena {i+1}">\n'
            else:
                html += '  <div style="width:320px;height:320px;background:#1a1438;border-radius:12px;display:flex;align-items:center;justify-content:center;color:#6b7280;">Sin imagen</div>\n'
            html += f'  <div class="contenido">\n'
            html += f'    <div class="num">🎬 Escena {i+1}</div>\n'
            html += f'    <div class="narr">{esc["narracion"]}</div>\n'
            html += f'    <div class="visual">🎨 {esc["prompt_img"]}</div>\n'
            if aud_rel:
                html += f'    <audio controls src="{aud_rel}"></audio>\n'
            html += '  </div>\n</div>\n'

        html += """
<div class="footer">
  Generado con 🎬 <strong>NOVA Studio</strong> — parte del ecosistema NOVA AI
</div>
</body></html>"""

        out = os.path.join(ruta, "storyboard.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        self.status.config(text=f"✅ HTML generado: storyboard.html",
                            fg=C["ok"])
        if messagebox.askyesno("✅ Listo",
            "Storyboard HTML generado.\n\n¿Abrirlo en el navegador?"):
            import webbrowser
            webbrowser.open("file://" + os.path.abspath(out))

    def _generar_ffmpeg(self):
        if not self.proyecto_actual or not self.escenas:
            messagebox.showinfo("ℹ️", "Necesitas un proyecto con escenas."); return
        ruta = self._ruta_proyecto()

        script = "@echo off\nREM === Script generado por NOVA Studio ===\n"
        script += "REM Requiere FFmpeg instalado: https://ffmpeg.org/download.html\n\n"
        script += "echo 🎬 Generando video con FFmpeg...\n\n"

        # Generar una lista de concat
        # Para cada escena: vídeo de 3-5s con la imagen + audio
        partes = []
        for i, esc in enumerate(self.escenas):
            num = f"{i+1:02d}"
            partes.append(f"escena_{num}_video.mp4")
            script += (f"echo [Escena {i+1}] Combinando imagen + audio...\n"
                f'ffmpeg -y -loop 1 -i "escena_{num}.png" -i "escena_{num}.mp3" '
                f'-c:v libx264 -tune stillimage -c:a aac -b:a 192k -pix_fmt yuv420p '
                f'-shortest "escena_{num}_video.mp4"\n\n')

        # Concat
        script += "echo Concatenando todas las escenas...\n"
        script += "( for %%i in (" + " ".join(partes) + ") do @echo file '%%i' ) > lista.txt\n"
        script += 'ffmpeg -y -f concat -safe 0 -i lista.txt -c copy "video_final.mp4"\n\n'
        script += 'del lista.txt\n'
        script += "echo.\necho ✅ ¡VIDEO LISTO! Mira: video_final.mp4\npause\n"

        out = os.path.join(ruta, "generar_video.bat")
        with open(out, "w", encoding="utf-8") as f:
            f.write(script)
        self.status.config(text="✅ Script FFmpeg generado: generar_video.bat",
                            fg=C["ok"])
        messagebox.showinfo("✅ Script generado",
            f"He creado:\n  generar_video.bat\n\n"
            f"Para usarlo:\n"
            f"1) Instala FFmpeg (https://ffmpeg.org)\n"
            f"2) Doble click en generar_video.bat\n"
            f"3) Obtendrás video_final.mp4")

    # ----------------------------------------------------------
    # Configuración
    # ----------------------------------------------------------
    def _config_ia(self):
        cfg_actual = {
            "proveedor": self.proveedor,
            "modelo": self.modelo,
            "api_key": self.api_key,
            "api_keys": self.cfg.get("api_keys", {}),
        }
        colores = {"bg": C["bg"], "bg2": C["bg3"], "fg": C["fg"],
                   "accent": C["accent"], "warn": C["warn"], "ok": C["ok"]}
        def on_save(nuevo):
            self.proveedor = nuevo["proveedor"]
            self.modelo = nuevo["modelo"]
            self.api_key = nuevo["api_key"]
            self.cfg["studio_proveedor"] = self.proveedor
            self.cfg["studio_modelo"] = self.modelo
            self.cfg["api_keys"] = nuevo["api_keys"]
            self._guardar_config()
        dialogo_config(self.root, cfg_actual, on_save,
            titulo="⚙ Configuración IA — Studio", colores=colores)

    def _config_voz(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("🎙️ Voz TTS")
        dlg.geometry("420x320")
        dlg.configure(bg=C["bg"])
        dlg.transient(self.root)

        tk.Label(dlg, text="🎙️ Elige la voz para narrar",
            bg=C["bg"], fg=C["accent"],
            font=("Segoe UI", 13, "bold")).pack(pady=12)

        voz_var = tk.StringVar()
        # encontrar nombre amigable de la voz actual
        for label, codigo in VOCES_TTS.items():
            if codigo == self.voz:
                voz_var.set(label); break
        else:
            voz_var.set(list(VOCES_TTS.keys())[0])

        for label in VOCES_TTS:
            tk.Radiobutton(dlg, text=label, variable=voz_var, value=label,
                bg=C["bg"], fg=C["fg"], selectcolor=C["bg3"],
                activebackground=C["bg"], activeforeground=C["accent"],
                font=("Segoe UI", 10), anchor="w").pack(fill="x", padx=40, pady=2)

        def guardar():
            self.voz = VOCES_TTS[voz_var.get()]
            self.cfg["studio_voz"] = self.voz
            self._guardar_config()
            self.lbl_voz.config(text=f"🎙️ Voz actual: {self.voz}")
            self.status.config(text=f"✅ Voz: {voz_var.get()}", fg=C["ok"])
            dlg.destroy()

        tk.Button(dlg, text="💾 Guardar", command=guardar,
            bg=C["ok"], fg="white", relief="flat",
            font=("Segoe UI", 11, "bold"), padx=20, pady=6,
            cursor="hand2").pack(pady=14)

    def _config_estilo(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("🎨 Estilo visual")
        dlg.geometry("440x460")
        dlg.configure(bg=C["bg"])
        dlg.transient(self.root)

        tk.Label(dlg, text="🎨 Elige estilo visual para las imágenes",
            bg=C["bg"], fg=C["accent"],
            font=("Segoe UI", 13, "bold")).pack(pady=12)

        est_var = tk.StringVar(value=self.estilo)
        for label in ESTILOS_VISUALES:
            tk.Radiobutton(dlg, text=label, variable=est_var, value=label,
                bg=C["bg"], fg=C["fg"], selectcolor=C["bg3"],
                activebackground=C["bg"], activeforeground=C["accent"],
                font=("Segoe UI", 10), anchor="w").pack(fill="x", padx=40, pady=2)

        def guardar():
            self.estilo = est_var.get()
            self.cfg["studio_estilo"] = self.estilo
            self._guardar_config()
            self.status.config(text=f"✅ Estilo: {self.estilo}", fg=C["ok"])
            dlg.destroy()

        tk.Button(dlg, text="💾 Guardar", command=guardar,
            bg=C["ok"], fg="white", relief="flat",
            font=("Segoe UI", 11, "bold"), padx=20, pady=6,
            cursor="hand2").pack(pady=14)

    def _mostrar_ayuda(self):
        ayuda = """🎬 NOVA STUDIO — Guía rápida

📝 PASO 1: Crear proyecto
   • Pulsa ➕ Nuevo proyecto y dale un nombre

📝 PASO 2: Generar guión
   • Escribe tu idea (ej: "viaje a Marte de 3 amigos")
   • Elige tipo (TikTok, cuento, anuncio...)
   • Pulsa ✨ Generar guión con IA
   • Edita el texto si quieres

🎨 PASO 3: Generar imágenes
   • Pulsa 🎨 Generar IMÁGENES (botón derecha del guión)
   • Cada imagen tarda ~15 segundos
   • Usa Pollinations.ai (100% gratis, sin API key)
   • Pestaña 🎨 Storyboard muestra las miniaturas

🔊 PASO 4: Generar audio (TTS)
   • Pestaña 🔊 Audio → 🎤 Generar AUDIO de todas las escenas
   • Usa edge-tts (voces españolas naturales gratis)
   • Doble click en la lista para reproducir

📦 PASO 5: Exportar
   • Pestaña 📦 Exportar → 🌐 Storyboard HTML (todo en uno)
   • O genera script FFmpeg para hacer un vídeo MP4 real

⚙ CONFIGURACIÓN
   • ⚙ Config IA: proveedor LLM (Gemini, Groq, OpenAI, Ollama)
   • 🎙️ Voz TTS: 7 voces españolas
   • 🎨 Estilo: 10 estilos visuales para las imágenes

💡 TRUCO: el botón 🔄 Refrescar modelos detecta los modelos
   disponibles AHORA de tu proveedor.

📂 Tus proyectos se guardan en:
   {dir}
""".format(dir=PROYECTOS_DIR)

        dlg = tk.Toplevel(self.root)
        dlg.title("📖 Ayuda — NOVA Studio")
        dlg.geometry("640x600")
        dlg.configure(bg=C["bg"])
        dlg.transient(self.root)

        txt = scrolledtext.ScrolledText(dlg,
            bg=C["bg3"], fg=C["fg"], font=("Consolas", 10),
            wrap="word", relief="flat", padx=12, pady=12)
        txt.pack(fill="both", expand=True, padx=12, pady=12)
        txt.insert("1.0", ayuda)
        txt.config(state="disabled")

        tk.Button(dlg, text="OK", command=dlg.destroy,
            bg=C["accent"], fg="white", relief="flat",
            font=("Segoe UI", 10, "bold"), padx=30, pady=6,
            cursor="hand2").pack(pady=10)


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    try:
        from nova_ui import splash_screen, Theme
        splash_screen("NOVA Studio",
                       subtitulo="Genera guion + imagenes + voz con IA",
                       color_acento=Theme.accent3,
                       tareas=[
                           ("Cargando plantillas...", None),
                           ("Conectando con Pollinations...", None),
                           ("Preparando estudio...", None),
                       ],
                       duracion_min=1.3)
    except Exception as e:
        print(f"Splash: {e}")

    root = tk.Tk()
    app = NovaStudio(root)
    root.mainloop()
