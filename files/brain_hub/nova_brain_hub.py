"""
🧠 NOVA BRAIN HUB — Dashboard central del ecosistema NOVA AI
=============================================================
Panel de control unificado para los 10+ módulos:
  • Lanza cualquier módulo con un click
  • Detecta cuáles están instalados / corriendo
  • Configuración global de API keys
  • Estadísticas: qué se ha generado, espacio usado
  • Logs unificados
  • Quick actions: chat rápido, generar imagen, TTS

Parte del ecosistema NOVA AI.
"""
import os, sys, json, subprocess, threading, time
import urllib.request, urllib.parse
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from datetime import datetime

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# VERSION (para el sistema de actualizaciones)
# ============================================================
VERSION = "1.0.0"
MODULO_ID = "brain_hub"

PARENT = os.path.dirname(APP_DIR)   # carpeta AsistenteIA/
CONFIG = os.path.join(PARENT, "config.json")

# Importar librería compartida
sys.path.insert(0, APP_DIR)
from nova_ia_lib import llamar_llm, dialogo_config, listar_modelos, URLS_API_KEY

# ============================================================
# DEFINICIÓN DE LOS MÓDULOS DEL ECOSISTEMA
# ============================================================
MODULOS = [
    {"id": "asistente", "nombre": "🤖 Asistente Principal",
     "desc": "Chat multi-IA con control del PC",
     "carpeta": "", "archivo": "asistente.py", "color": "#3b82f6"},
    {"id": "orb", "nombre": "🔵 NOVA Orb",
     "desc": "Esfera flotante con visión de pantalla",
     "carpeta": "Nova Orb", "archivo": "nova_orb.py", "color": "#06b6d4"},
    {"id": "mini", "nombre": "🧠 NOVA Mini Beta",
     "desc": "IA desde cero que aprende de ti",
     "carpeta": "Nova Mini-Beta", "archivo": "nova_mini.py", "color": "#ef4444"},
    {"id": "agent", "nombre": "🤖 Agent Mode",
     "desc": "Genera proyectos con múltiples IAs",
     "carpeta": "Agent Mode", "archivo": "agent_mode.py", "color": "#7c3aed"},
    {"id": "jarvis", "nombre": "🤖 NOVA Jarvis",
     "desc": "Asistente con memoria (estilo Iron Man)",
     "carpeta": "Nova Jarvis", "archivo": "nova_jarvis.py", "color": "#60a5fa"},
    {"id": "reader", "nombre": "📖 NOVA Reader",
     "desc": "Resume PDFs, libros, hace quiz",
     "carpeta": "Nova Reader", "archivo": "nova_reader.py", "color": "#a78bfa"},
    {"id": "telegram", "nombre": "📱 NOVA Telegram",
     "desc": "Bot de Telegram (chat desde móvil)",
     "carpeta": "Nova Telegram", "archivo": "nova_telegram.py", "color": "#0ea5e9"},
    {"id": "search", "nombre": "🔍 NOVA Search",
     "desc": "Busca en TUS archivos con lenguaje natural",
     "carpeta": "Nova Search", "archivo": "nova_search.py", "color": "#10b981"},
    {"id": "gm", "nombre": "🎮 NOVA Game Master",
     "desc": "Master de rol IA con dados y arte",
     "carpeta": "Nova Game Master", "archivo": "nova_game_master.py",
     "color": "#fbbf24"},
    {"id": "studio", "nombre": "🎬 NOVA Studio",
     "desc": "Guión + imágenes + audio TTS",
     "carpeta": "Nova Studio", "archivo": "nova_studio.py", "color": "#ec4899"},
    {"id": "office", "nombre": "💼 NOVA Office",
     "desc": "Genera Word, Excel, PowerPoint",
     "carpeta": "Nova Office", "archivo": "nova_office.py", "color": "#f59e0b"},
    {"id": "coach", "nombre": "🎓 NOVA Coach",
     "desc": "Hábitos, dieta, ejercicio",
     "carpeta": "Nova Coach", "archivo": "nova_coach.py", "color": "#22c55e"},
]

# ============================================================
# PALETA DE COLORES
# ============================================================
C = {
    "bg":      "#050714",     # casi negro azulado
    "bg2":     "#0f172a",     # navy oscuro
    "bg3":     "#1e293b",     # tarjetas
    "bg_hover": "#334155",
    "fg":      "#f1f5f9",     # blanco hueso
    "fg2":     "#94a3b8",     # gris claro
    "accent":  "#3b82f6",     # azul
    "accent2": "#a78bfa",     # violeta
    "ok":      "#22c55e",
    "warn":    "#fbbf24",
    "err":     "#ef4444",
}

# ============================================================
# APP PRINCIPAL
# ============================================================
class BrainHub:
    def __init__(self, root):
        self.root = root
        self.root.title("🧠 NOVA Brain Hub — Dashboard central")
        self.root.geometry("1280x800")
        self.root.configure(bg=C["bg"])

        self.cfg = self._cargar_config()
        self.procesos = {}   # módulo_id -> subprocess.Popen
        self.proveedor = self.cfg.get("hub_proveedor", "Groq")
        self.modelo = self.cfg.get("hub_modelo", "llama-3.3-70b-versatile")
        self.api_key = self.cfg.get("api_keys", {}).get(self.proveedor, "")

        self._construir_ui()
        self._refrescar_dashboard()

        # Auto-refresh cada 4 segundos para detectar procesos vivos/muertos
        self._tick()

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

    # --------------------------------------------------------
    # UI principal
    # --------------------------------------------------------
    def _construir_ui(self):
        # ===== HEADER =====
        header = tk.Frame(self.root, bg=C["bg2"], height=72)
        header.pack(fill="x"); header.pack_propagate(False)

        title_frame = tk.Frame(header, bg=C["bg2"])
        title_frame.pack(side="left", padx=24)
        tk.Label(title_frame, text="🧠 NOVA Brain Hub",
                 bg=C["bg2"], fg=C["accent2"],
                 font=("Segoe UI", 20, "bold")).pack(anchor="w")
        tk.Label(title_frame,
                 text="Centro de control de tu ecosistema de IA",
                 bg=C["bg2"], fg=C["fg2"],
                 font=("Segoe UI", 9, "italic")).pack(anchor="w")

        btns_top = tk.Frame(header, bg=C["bg2"])
        btns_top.pack(side="right", padx=18)
        for txt, cmd, color in [
            ("⚙ Config IA", self._config_ia, C["bg3"]),
            ("🔑 API Keys", self._gestionar_api_keys, C["bg3"]),
            ("🔄 Refrescar", self._refrescar_dashboard, C["accent"]),
        ]:
            tk.Button(btns_top, text=txt, command=cmd,
                      bg=color, fg=C["fg"], relief="flat",
                      font=("Segoe UI", 9, "bold"), cursor="hand2",
                      padx=12, pady=6).pack(side="left", padx=4)

        # ===== Notebook con pestañas =====
        style = ttk.Style()
        try: style.theme_use("clam")
        except Exception: pass
        style.configure("TNotebook", background=C["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=C["bg2"], foreground=C["fg"],
                         padding=[20, 10], font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab",
                   background=[("selected", C["accent"])],
                   foreground=[("selected", "white")])

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=12)

        self._tab_modulos()
        self._tab_quick()
        self._tab_estadisticas()
        self._tab_logs()

        # ===== STATUS =====
        self.status = tk.Label(self.root,
            text=f"🧠 Brain Hub listo · IA: {self.proveedor}/{self.modelo}",
            bg=C["bg2"], fg=C["fg2"],
            font=("Segoe UI", 9), anchor="w", padx=14)
        self.status.pack(side="bottom", fill="x")

    # --------------------------------------------------------
    # Pestaña 1: módulos con tarjetas
    # --------------------------------------------------------
    def _tab_modulos(self):
        tab = tk.Frame(self.notebook, bg=C["bg"])
        self.notebook.add(tab, text="🧩 Módulos")

        tk.Label(tab,
                 text="🚀 Tus módulos NOVA AI — pulsa para abrir",
                 bg=C["bg"], fg=C["accent2"],
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(12, 8))

        # Canvas con scroll para grid de tarjetas
        canvas_frame = tk.Frame(tab, bg=C["bg"])
        canvas_frame.pack(fill="both", expand=True, padx=12, pady=6)

        canvas = tk.Canvas(canvas_frame, bg=C["bg"], highlightthickness=0)
        sb = tk.Scrollbar(canvas_frame, orient="vertical",
                           command=canvas.yview, bg=C["bg2"])
        self.cards_frame = tk.Frame(canvas, bg=C["bg"])

        self.cards_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(-int(e.delta / 60), "units"))

        # Las tarjetas se rellenarán en _refrescar_dashboard

    def _refrescar_dashboard(self):
        # Limpiar tarjetas anteriores
        for w in self.cards_frame.winfo_children():
            w.destroy()

        # Grid 3 columnas
        COLS = 3
        for i, mod in enumerate(MODULOS):
            r, c = divmod(i, COLS)
            card = self._crear_tarjeta(self.cards_frame, mod)
            card.grid(row=r, column=c, padx=10, pady=10, sticky="nsew")
            self.cards_frame.grid_columnconfigure(c, weight=1, uniform="cards")

        self.status.config(
            text=f"✅ {len(MODULOS)} módulos · {len(self.procesos)} corriendo",
            fg=C["ok"])

    def _crear_tarjeta(self, parent, mod):
        ruta = self._ruta_modulo(mod)
        instalado = os.path.exists(ruta)
        corriendo = (mod["id"] in self.procesos and
                      self.procesos[mod["id"]].poll() is None)

        card = tk.Frame(parent, bg=C["bg3"], bd=0,
                         highlightthickness=2,
                         highlightbackground=mod["color"] if instalado else C["bg2"])

        # Título con color
        title_bar = tk.Frame(card, bg=mod["color"] if instalado else C["bg2"], height=4)
        title_bar.pack(fill="x")

        contenido = tk.Frame(card, bg=C["bg3"])
        contenido.pack(fill="both", expand=True, padx=14, pady=12)

        tk.Label(contenido, text=mod["nombre"],
                 bg=C["bg3"], fg=mod["color"] if instalado else C["fg2"],
                 font=("Segoe UI", 12, "bold"),
                 anchor="w").pack(fill="x")

        tk.Label(contenido, text=mod["desc"],
                 bg=C["bg3"], fg=C["fg"],
                 font=("Segoe UI", 9),
                 wraplength=270, justify="left",
                 anchor="w").pack(fill="x", pady=(2, 8))

        # Estado
        if not instalado:
            estado_txt, estado_color = "❌ No encontrado", C["err"]
        elif corriendo:
            estado_txt, estado_color = "🟢 Corriendo", C["ok"]
        else:
            estado_txt, estado_color = "⚪ Inactivo", C["fg2"]
        tk.Label(contenido, text=estado_txt,
                 bg=C["bg3"], fg=estado_color,
                 font=("Segoe UI", 8, "bold"),
                 anchor="w").pack(fill="x", pady=(0, 8))

        # Botones acción
        btn_frame = tk.Frame(contenido, bg=C["bg3"])
        btn_frame.pack(fill="x")

        if instalado:
            if corriendo:
                tk.Button(btn_frame, text="🛑 Parar",
                    command=lambda m=mod: self._parar_modulo(m),
                    bg=C["err"], fg="white", relief="flat",
                    font=("Segoe UI", 9, "bold"), cursor="hand2",
                    padx=10, pady=4).pack(side="left", padx=2)
            else:
                tk.Button(btn_frame, text="▶ Abrir",
                    command=lambda m=mod: self._lanzar_modulo(m),
                    bg=mod["color"], fg="white", relief="flat",
                    font=("Segoe UI", 9, "bold"), cursor="hand2",
                    padx=14, pady=4).pack(side="left", padx=2)

            tk.Button(btn_frame, text="📂",
                command=lambda m=mod: self._abrir_carpeta_mod(m),
                bg=C["bg2"], fg=C["fg"], relief="flat",
                font=("Segoe UI", 9), cursor="hand2",
                padx=8, pady=4).pack(side="left", padx=2)
        else:
            tk.Label(btn_frame, text="(módulo no instalado)",
                     bg=C["bg3"], fg=C["fg2"],
                     font=("Segoe UI", 8, "italic")).pack(side="left")

        return card

    # --------------------------------------------------------
    # Pestaña 2: Quick Actions
    # --------------------------------------------------------
    def _tab_quick(self):
        tab = tk.Frame(self.notebook, bg=C["bg"])
        self.notebook.add(tab, text="⚡ Acciones rápidas")

        tk.Label(tab, text="⚡ Acciones rápidas sin abrir un módulo entero",
                 bg=C["bg"], fg=C["accent2"],
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(12, 8))

        # === Chat rápido con IA ===
        chat_card = tk.Frame(tab, bg=C["bg3"])
        chat_card.pack(fill="x", padx=14, pady=8)

        tk.Label(chat_card, text="💬 Pregunta rápida a la IA",
                 bg=C["bg3"], fg=C["accent"],
                 font=("Segoe UI", 11, "bold"),
                 anchor="w").pack(fill="x", padx=14, pady=(10, 4))

        self.quick_entry = tk.Entry(chat_card,
            bg=C["bg2"], fg=C["fg"], insertbackground=C["fg"],
            relief="flat", font=("Segoe UI", 10))
        self.quick_entry.pack(fill="x", padx=14, ipady=6)
        self.quick_entry.bind("<Return>", lambda e: self._quick_chat())

        btn_chat = tk.Frame(chat_card, bg=C["bg3"])
        btn_chat.pack(fill="x", padx=14, pady=8)
        tk.Button(btn_chat, text="🚀 Enviar", command=self._quick_chat,
                  bg=C["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2",
                  padx=14, pady=4).pack(side="left")
        tk.Button(btn_chat, text="🧹 Limpiar",
            command=lambda: self.quick_out.delete("1.0", "end"),
            bg=C["bg2"], fg=C["fg"], relief="flat",
            font=("Segoe UI", 9), cursor="hand2",
            padx=14, pady=4).pack(side="left", padx=4)

        self.quick_out = scrolledtext.ScrolledText(chat_card,
            bg=C["bg2"], fg=C["fg"], font=("Consolas", 10),
            height=10, wrap="word", relief="flat",
            padx=10, pady=10)
        self.quick_out.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        # === Generador rápido de imagen ===
        img_card = tk.Frame(tab, bg=C["bg3"])
        img_card.pack(fill="x", padx=14, pady=8)

        tk.Label(img_card, text="🎨 Generar imagen rápida (Pollinations · gratis)",
                 bg=C["bg3"], fg=C["accent2"],
                 font=("Segoe UI", 11, "bold"),
                 anchor="w").pack(fill="x", padx=14, pady=(10, 4))

        self.img_entry = tk.Entry(img_card,
            bg=C["bg2"], fg=C["fg"], insertbackground=C["fg"],
            relief="flat", font=("Segoe UI", 10))
        self.img_entry.pack(fill="x", padx=14, ipady=6)

        tk.Button(img_card, text="🎨 Generar y guardar PNG",
            command=self._quick_imagen,
            bg=C["accent2"], fg="white", relief="flat",
            font=("Segoe UI", 10, "bold"), cursor="hand2",
            padx=14, pady=6).pack(anchor="w", padx=14, pady=8)

    def _quick_chat(self):
        pregunta = self.quick_entry.get().strip()
        if not pregunta: return
        if not self.api_key and self.proveedor != "Ollama":
            self.quick_out.insert("end",
                "⚠️ Configura primero tu API Key (⚙ Config IA arriba).\n\n")
            return
        self.quick_out.insert("end", f"❓ {pregunta}\n", "user")
        self.quick_out.insert("end", "⏳ Pensando...\n\n")
        self.quick_out.see("end")
        self.quick_entry.delete(0, "end")

        def tarea():
            resp, err = llamar_llm(self.proveedor, self.modelo, self.api_key,
                "Eres un asistente útil, conciso y amigable. Respondes en español.",
                pregunta)
            # Eliminar el "⏳ Pensando..."
            self.root.after(0, lambda: self.quick_out.delete("end-3l", "end-1l"))
            if err:
                self.root.after(0, lambda: self.quick_out.insert("end",
                    f"❌ Error: {err}\n\n"))
            else:
                self.root.after(0, lambda: self.quick_out.insert("end",
                    f"🤖 {resp}\n\n"))
            self.root.after(0, lambda: self.quick_out.see("end"))
        threading.Thread(target=tarea, daemon=True).start()

    def _quick_imagen(self):
        prompt = self.img_entry.get().strip()
        if not prompt:
            messagebox.showinfo("ℹ️", "Escribe primero qué quieres generar.")
            return
        ruta = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png")],
            initialfile=f"img_{int(time.time())}.png",
            title="Guardar imagen como…")
        if not ruta: return
        self.status.config(text="🎨 Generando imagen (~15s)...", fg=C["accent2"])

        def tarea():
            try:
                slug = urllib.parse.quote(prompt)
                url = (f"https://image.pollinations.ai/prompt/{slug}"
                       f"?width=1024&height=1024&nologo=true")
                req = urllib.request.Request(url,
                    headers={"User-Agent": "NovaBrainHub/1.0"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    with open(ruta, "wb") as f:
                        f.write(r.read())
                self.root.after(0, lambda: self.status.config(
                    text=f"✅ Imagen guardada: {os.path.basename(ruta)}", fg=C["ok"]))
                self.root.after(0, lambda: messagebox.showinfo("✅ Listo",
                    f"Imagen guardada en:\n{ruta}"))
            except Exception as e:
                self.root.after(0, lambda: self.status.config(
                    text=f"❌ {e}", fg=C["err"]))
        threading.Thread(target=tarea, daemon=True).start()

    # --------------------------------------------------------
    # Pestaña 3: estadísticas
    # --------------------------------------------------------
    def _tab_estadisticas(self):
        tab = tk.Frame(self.notebook, bg=C["bg"])
        self.notebook.add(tab, text="📊 Estadísticas")

        tk.Label(tab, text="📊 Lo que NOVA AI ha hecho por ti",
                 bg=C["bg"], fg=C["accent2"],
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=14, pady=12)

        self.stats_text = scrolledtext.ScrolledText(tab,
            bg=C["bg3"], fg=C["fg"], font=("Consolas", 10),
            wrap="word", relief="flat", padx=14, pady=14)
        self.stats_text.pack(fill="both", expand=True, padx=14, pady=10)

        tk.Button(tab, text="🔄 Calcular estadísticas",
            command=self._calcular_stats,
            bg=C["accent"], fg="white", relief="flat",
            font=("Segoe UI", 10, "bold"), cursor="hand2",
            padx=14, pady=6).pack(pady=8)

        # Calcular al iniciar
        self.root.after(500, self._calcular_stats)

    def _calcular_stats(self):
        self.stats_text.delete("1.0", "end")
        lineas = ["📊 ESTADÍSTICAS DEL ECOSISTEMA NOVA AI", "=" * 50, ""]

        total_archivos = 0
        total_tamano = 0

        # Por módulo
        for mod in MODULOS:
            if not mod["carpeta"]: continue
            carpeta = os.path.join(PARENT, mod["carpeta"])
            if not os.path.exists(carpeta): continue
            archivos_mod = 0
            tam_mod = 0
            for raiz, _, files in os.walk(carpeta):
                for f in files:
                    p = os.path.join(raiz, f)
                    try:
                        tam_mod += os.path.getsize(p)
                        archivos_mod += 1
                    except Exception:
                        pass
            total_archivos += archivos_mod
            total_tamano += tam_mod
            tam_mb = tam_mod / (1024 * 1024)
            lineas.append(f"  {mod['nombre']}")
            lineas.append(f"    📁 {archivos_mod} archivos · 💾 {tam_mb:.2f} MB")

        lineas.append("")
        lineas.append("=" * 50)
        lineas.append(f"📦 TOTAL: {total_archivos} archivos · "
                       f"💾 {total_tamano / (1024 * 1024):.2f} MB")
        lineas.append("")

        # Contenido generado por módulo
        contadores = [
            ("Nova Jarvis", "jarvis_memoria.json", "💭 Memoria de Jarvis"),
            ("Nova Reader", "apuntes", "📝 Apuntes generados"),
            ("Nova Game Master", "partidas", "🎮 Partidas guardadas"),
            ("Nova Game Master", "arte", "🎨 Arte de partidas"),
            ("Nova Studio", "proyectos", "🎬 Proyectos multimedia"),
            ("Agent Mode", "proyectos", "🤖 Proyectos de Agent Mode"),
            ("Nova Office", "documentos", "💼 Documentos generados"),
            ("Nova Coach", "datos.json", "🎓 Historial Coach"),
        ]
        lineas.append("📈 CONTENIDO GENERADO:")
        for cm, sub, nombre in contadores:
            ruta = os.path.join(PARENT, cm, sub)
            if os.path.isdir(ruta):
                n = len([x for x in os.listdir(ruta)
                          if not x.startswith(".")])
                lineas.append(f"  {nombre}: {n} elementos")
            elif os.path.isfile(ruta):
                kb = os.path.getsize(ruta) / 1024
                lineas.append(f"  {nombre}: {kb:.1f} KB")

        # API keys configuradas
        api_keys = self.cfg.get("api_keys", {})
        lineas.append("")
        lineas.append("🔑 API KEYS CONFIGURADAS:")
        for prov in ["Gemini", "Groq", "OpenAI", "Claude"]:
            k = api_keys.get(prov, "")
            estado = "✅" if k else "❌"
            mask = f"({k[:6]}...{k[-4:]})" if len(k) > 10 else ""
            lineas.append(f"  {estado} {prov} {mask}")

        self.stats_text.insert("1.0", "\n".join(lineas))

    # --------------------------------------------------------
    # Pestaña 4: logs
    # --------------------------------------------------------
    def _tab_logs(self):
        tab = tk.Frame(self.notebook, bg=C["bg"])
        self.notebook.add(tab, text="📜 Logs")

        tk.Label(tab, text="📜 Actividad reciente del Brain Hub",
                 bg=C["bg"], fg=C["accent2"],
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=12)

        self.logs_text = scrolledtext.ScrolledText(tab,
            bg="#000000", fg="#22c55e", font=("Consolas", 9),
            wrap="word", relief="flat", padx=10, pady=10,
            insertbackground=C["fg"])
        self.logs_text.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        bf = tk.Frame(tab, bg=C["bg"])
        bf.pack(fill="x", padx=14, pady=(0, 14))
        tk.Button(bf, text="🧹 Limpiar logs",
            command=lambda: self.logs_text.delete("1.0", "end"),
            bg=C["bg3"], fg=C["fg"], relief="flat",
            font=("Segoe UI", 9), cursor="hand2",
            padx=10, pady=4).pack(side="left")

        self._log(f"🧠 Brain Hub iniciado a las {datetime.now().strftime('%H:%M:%S')}")

    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        try:
            self.logs_text.insert("end", f"[{ts}] {msg}\n")
            self.logs_text.see("end")
        except Exception:
            pass

    # --------------------------------------------------------
    # Lanzar/parar módulos
    # --------------------------------------------------------
    def _ruta_modulo(self, mod):
        if mod["carpeta"]:
            return os.path.join(PARENT, mod["carpeta"], mod["archivo"])
        return os.path.join(PARENT, mod["archivo"])

    def _lanzar_modulo(self, mod):
        ruta = self._ruta_modulo(mod)
        if not os.path.exists(ruta):
            messagebox.showerror("❌", f"No se encuentra:\n{ruta}")
            return
        cwd = os.path.dirname(ruta)
        try:
            p = subprocess.Popen([sys.executable, ruta], cwd=cwd)
            self.procesos[mod["id"]] = p
            self._log(f"▶ Lanzado: {mod['nombre']} (PID {p.pid})")
            self.status.config(text=f"▶ {mod['nombre']} lanzado",
                                fg=mod["color"])
            self.root.after(800, self._refrescar_dashboard)
        except Exception as e:
            messagebox.showerror("❌", str(e))
            self._log(f"❌ Error al lanzar {mod['nombre']}: {e}")

    def _parar_modulo(self, mod):
        p = self.procesos.get(mod["id"])
        if not p: return
        try:
            p.terminate()
            self._log(f"🛑 Parado: {mod['nombre']}")
        except Exception as e:
            self._log(f"❌ Error al parar {mod['nombre']}: {e}")
        finally:
            self.procesos.pop(mod["id"], None)
            self.status.config(text=f"🛑 {mod['nombre']} parado", fg=C["warn"])
            self.root.after(400, self._refrescar_dashboard)

    def _abrir_carpeta_mod(self, mod):
        ruta = self._ruta_modulo(mod)
        carpeta = os.path.dirname(ruta)
        try:
            os.startfile(carpeta)
        except AttributeError:
            subprocess.Popen(["xdg-open", carpeta])

    def _tick(self):
        # Limpiar procesos muertos
        muertos = [k for k, p in self.procesos.items() if p.poll() is not None]
        if muertos:
            for k in muertos:
                self.procesos.pop(k, None)
                nombre = next((m["nombre"] for m in MODULOS
                                if m["id"] == k), k)
                self._log(f"⚪ Cerrado: {nombre}")
            self._refrescar_dashboard()
        self.root.after(4000, self._tick)

    # --------------------------------------------------------
    # Configuración
    # --------------------------------------------------------
    def _config_ia(self):
        cfg = {
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
            self.cfg["hub_proveedor"] = self.proveedor
            self.cfg["hub_modelo"] = self.modelo
            self.cfg["api_keys"] = nuevo["api_keys"]
            self._guardar_config()
            self.status.config(
                text=f"✅ Config: {self.proveedor} / {self.modelo}", fg=C["ok"])
        dialogo_config(self.root, cfg, on_save,
            titulo="⚙ Configuración IA — Brain Hub", colores=colores)

    def _gestionar_api_keys(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("🔑 Gestionar API Keys")
        dlg.geometry("560x440")
        dlg.configure(bg=C["bg"])
        dlg.transient(self.root)

        tk.Label(dlg, text="🔑 API Keys de todos los proveedores",
            bg=C["bg"], fg=C["accent2"],
            font=("Segoe UI", 13, "bold")).pack(pady=12)

        tk.Label(dlg, text="(Compartidas entre TODOS los módulos NOVA)",
            bg=C["bg"], fg=C["fg2"],
            font=("Segoe UI", 9, "italic")).pack()

        keys = self.cfg.setdefault("api_keys", {})
        entries = {}
        for prov in ["Gemini", "Groq", "OpenAI", "Claude"]:
            row = tk.Frame(dlg, bg=C["bg"])
            row.pack(fill="x", padx=20, pady=6)
            tk.Label(row, text=f"{prov}:", bg=C["bg"], fg=C["accent"],
                     font=("Segoe UI", 10, "bold"),
                     width=10, anchor="w").pack(side="left")
            ent = tk.Entry(row, bg=C["bg3"], fg=C["fg"],
                           insertbackground=C["fg"], relief="flat",
                           show="*", font=("Segoe UI", 10))
            ent.insert(0, keys.get(prov, ""))
            ent.pack(side="left", fill="x", expand=True, ipady=4, padx=4)
            entries[prov] = ent

            url = URLS_API_KEY.get(prov, "")
            tk.Button(row, text="🌐", bg=C["bg3"], fg=C["fg"],
                relief="flat", cursor="hand2",
                command=lambda u=url: __import__("webbrowser").open(u)
                ).pack(side="left")

        def guardar():
            for prov, ent in entries.items():
                k = ent.get().strip()
                if k: keys[prov] = k
                elif prov in keys: del keys[prov]
            self.cfg["api_keys"] = keys
            self._guardar_config()
            self.status.config(text="✅ API Keys guardadas", fg=C["ok"])
            self._log(f"🔑 API Keys actualizadas: {list(keys.keys())}")
            dlg.destroy()
            # Refrescar la api_key actual
            self.api_key = keys.get(self.proveedor, "")

        tk.Button(dlg, text="💾 Guardar todas", command=guardar,
            bg=C["ok"], fg="white", relief="flat",
            font=("Segoe UI", 11, "bold"), padx=22, pady=8,
            cursor="hand2").pack(pady=18)


if __name__ == "__main__":
    try:
        from nova_ui import splash_screen, Theme
        splash_screen("NOVA Brain Hub",
                       subtitulo="Dashboard central del ecosistema",
                       color_acento=Theme.accent2,
                       tareas=[
                           ("Escaneando modulos...", None),
                           ("Cargando estadisticas...", None),
                           ("Iniciando dashboard...", None),
                       ],
                       duracion_min=1.3)
    except Exception as e:
        print(f"Splash: {e}")

    root = tk.Tk()
    app = BrainHub(root)
    root.mainloop()
