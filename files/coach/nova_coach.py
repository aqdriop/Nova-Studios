"""
🎓 NOVA COACH — Tu entrenador personal con IA
==============================================
Tu coach 360° que te ayuda con:
  💪 Plan de ejercicio personalizado
  🥗 Dieta y nutrición adaptada a tu objetivo
  📈 Seguimiento de hábitos diario
  🧘 Bienestar mental y mindfulness
  🎯 Establecimiento y seguimiento de metas
  📊 Estadísticas semanales y motivación IA

Parte del ecosistema NOVA AI.
"""
import os, sys, json, threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime, timedelta

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# VERSION (para el sistema de actualizaciones)
# ============================================================
VERSION = "1.0.0"
MODULO_ID = "coach"

PARENT = os.path.dirname(APP_DIR)
CONFIG = os.path.join(PARENT, "config.json")
DATOS = os.path.join(APP_DIR, "datos.json")

sys.path.insert(0, APP_DIR)
from nova_ia_lib import llamar_llm, dialogo_config
try:
    from nova_brain import Brain
    BRAIN = Brain()
except Exception:
    BRAIN = None

# ============================================================
# COLORES
# ============================================================
C = {
    "bg":      "#052e16",     # verde muy oscuro
    "bg2":     "#14532d",
    "bg3":     "#166534",
    "bg4":     "#1e293b",
    "fg":      "#f0fdf4",
    "fg2":     "#bbf7d0",
    "accent":  "#22c55e",     # verde principal
    "accent2": "#facc15",     # amarillo logros
    "warn":    "#f97316",
    "err":     "#ef4444",
    "info":    "#3b82f6",
}

HABITOS_DEFAULT = [
    {"emoji": "💧", "nombre": "Beber 2L de agua"},
    {"emoji": "🏃", "nombre": "Ejercicio 30 min"},
    {"emoji": "🥗", "nombre": "Comer saludable"},
    {"emoji": "📚", "nombre": "Leer 15 min"},
    {"emoji": "🧘", "nombre": "Meditar 10 min"},
    {"emoji": "😴", "nombre": "Dormir 8 horas"},
]

# ============================================================
# APP
# ============================================================
class NovaCoach:
    def __init__(self, root):
        self.root = root
        self.root.title("🎓 NOVA Coach — Tu entrenador personal con IA")
        self.root.geometry("1200x800")
        self.root.configure(bg=C["bg"])

        self.cfg = self._cargar_cfg()
        self.datos = self._cargar_datos()
        self.proveedor = self.cfg.get("coach_proveedor", "Groq")
        self.modelo = self.cfg.get("coach_modelo", "llama-3.3-70b-versatile")
        self.api_key = self.cfg.get("api_keys", {}).get(self.proveedor, "")
        self.procesando = False

        self._construir_ui()
        self._refrescar_dashboard()

    # ----------------------------------------------------------
    def _cargar_cfg(self):
        try:
            with open(CONFIG, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"api_keys": {}}

    def _guardar_cfg(self):
        try:
            with open(CONFIG, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, indent=2)
        except Exception as e:
            print(e)

    def _cargar_datos(self):
        if os.path.exists(DATOS):
            try:
                with open(DATOS, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        # Perfil inicial - si hay Brain, autocompleta con el perfil global
        perfil_inicial = {
            "nombre": "", "edad": "", "peso": "", "altura": "",
            "objetivo": "", "nivel": "principiante",
            "restricciones": "", "preferencias": "",
        }
        if BRAIN:
            brain_perfil = BRAIN.perfil()
            for k in ("nombre", "edad", "ciudad"):
                if brain_perfil.get(k) and not perfil_inicial.get(k):
                    perfil_inicial[k] = brain_perfil[k]

        return {
            "perfil": perfil_inicial,
            "habitos": HABITOS_DEFAULT.copy(),
            "registro": {},
            "planes": {},
            "metas": [],
            "diario": [],
        }

    def _guardar_datos(self):
        try:
            with open(DATOS, "w", encoding="utf-8") as f:
                json.dump(self.datos, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(e)

    # ----------------------------------------------------------
    def _construir_ui(self):
        # HEADER
        h = tk.Frame(self.root, bg=C["bg2"], height=68)
        h.pack(fill="x"); h.pack_propagate(False)
        tk.Label(h, text="🎓 NOVA Coach",
            bg=C["bg2"], fg=C["accent"],
            font=("Segoe UI", 18, "bold")).pack(side="left", padx=20)
        tk.Label(h, text="Tu entrenador personal con IA",
            bg=C["bg2"], fg=C["fg2"],
            font=("Segoe UI", 10, "italic")).pack(side="left", padx=4)

        for txt, cmd in [
            ("⚙ Config IA", self._config_ia),
            ("👤 Mi perfil", self._editar_perfil),
        ]:
            tk.Button(h, text=txt, command=cmd,
                bg=C["bg3"], fg=C["fg"], relief="flat",
                font=("Segoe UI", 9, "bold"), cursor="hand2",
                padx=12, pady=4).pack(side="right", padx=4, pady=12)

        # Notebook
        style = ttk.Style()
        try: style.theme_use("clam")
        except Exception: pass
        style.configure("TNotebook", background=C["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=C["bg2"], foreground=C["fg"],
                         padding=[20, 10], font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab",
                   background=[("selected", C["accent"])],
                   foreground=[("selected", C["bg"])])

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=12, pady=12)

        self._tab_dashboard(nb)
        self._tab_ejercicio(nb)
        self._tab_dieta(nb)
        self._tab_habitos(nb)
        self._tab_metas(nb)
        self._tab_chat(nb)

        self.status = tk.Label(self.root,
            text="🎓 Bienvenido a tu coach personal. Empieza configurando tu perfil 👤",
            bg=C["bg2"], fg=C["fg2"],
            font=("Segoe UI", 9), anchor="w", padx=14)
        self.status.pack(side="bottom", fill="x")

    # ============================================================
    # 📊 DASHBOARD
    # ============================================================
    def _tab_dashboard(self, parent):
        tab = tk.Frame(parent, bg=C["bg"])
        parent.add(tab, text="📊 Dashboard")
        self.dashboard_tab = tab

    def _refrescar_dashboard(self):
        for w in self.dashboard_tab.winfo_children():
            w.destroy()

        # Saludo
        nombre = self.datos["perfil"].get("nombre", "")
        saludo = f"¡Hola{', ' + nombre if nombre else ''}! 👋"
        hoy = datetime.now().strftime("%A, %d de %B de %Y")
        tk.Label(self.dashboard_tab, text=saludo,
            bg=C["bg"], fg=C["accent"],
            font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=20, pady=(16, 0))
        tk.Label(self.dashboard_tab, text=hoy.capitalize(),
            bg=C["bg"], fg=C["fg2"],
            font=("Segoe UI", 11, "italic")).pack(anchor="w", padx=20)

        # Hábitos de HOY
        hoy_key = datetime.now().strftime("%Y-%m-%d")
        registro_hoy = self.datos["registro"].get(hoy_key, {})
        habitos = self.datos["habitos"]
        completados = sum(1 for h in habitos
                           if registro_hoy.get(h["nombre"], False))
        total = len(habitos)
        pct = int(100 * completados / total) if total else 0

        card1 = tk.Frame(self.dashboard_tab, bg=C["bg3"])
        card1.pack(fill="x", padx=20, pady=(20, 8))

        tk.Label(card1, text=f"✅ Hábitos de hoy: {completados}/{total} ({pct}%)",
            bg=C["bg3"], fg=C["accent2"],
            font=("Segoe UI", 13, "bold"),
            anchor="w").pack(fill="x", padx=14, pady=(10, 6))

        # Barra de progreso
        bar_bg = tk.Frame(card1, bg=C["bg2"], height=18)
        bar_bg.pack(fill="x", padx=14, pady=(0, 12))
        bar_bg.pack_propagate(False)
        if pct > 0:
            bar_fill = tk.Frame(bar_bg, bg=C["accent"], height=18,
                                  width=int(800 * pct / 100))
            bar_fill.place(x=0, y=0, relheight=1, relwidth=pct / 100)

        # Quick check de hábitos
        habits_grid = tk.Frame(card1, bg=C["bg3"])
        habits_grid.pack(fill="x", padx=14, pady=(0, 12))
        for i, h in enumerate(habitos):
            done = registro_hoy.get(h["nombre"], False)
            var = tk.BooleanVar(value=done)
            def toggle(hn=h["nombre"], v=var):
                self.datos["registro"].setdefault(hoy_key, {})[hn] = v.get()
                self._guardar_datos()
                self.root.after(50, self._refrescar_dashboard)
            cb = tk.Checkbutton(habits_grid,
                text=f"{h['emoji']} {h['nombre']}",
                variable=var, command=toggle,
                bg=C["bg3"], fg=C["fg"],
                selectcolor=C["bg2"],
                activebackground=C["bg3"],
                activeforeground=C["accent"],
                font=("Segoe UI", 10), anchor="w")
            cb.grid(row=i // 2, column=i % 2, sticky="w",
                     padx=10, pady=3)

        # Racha
        racha = self._calcular_racha()
        card2 = tk.Frame(self.dashboard_tab, bg=C["bg3"])
        card2.pack(fill="x", padx=20, pady=8)
        tk.Label(card2,
            text=f"🔥 Racha actual: {racha} día{'s' if racha != 1 else ''} consecutivos",
            bg=C["bg3"], fg=C["warn"] if racha > 0 else C["fg2"],
            font=("Segoe UI", 13, "bold"),
            anchor="w").pack(fill="x", padx=14, pady=12)

        # Metas activas
        metas_activas = [m for m in self.datos["metas"] if not m.get("completada")]
        card3 = tk.Frame(self.dashboard_tab, bg=C["bg3"])
        card3.pack(fill="x", padx=20, pady=8)
        tk.Label(card3,
            text=f"🎯 Metas activas: {len(metas_activas)}",
            bg=C["bg3"], fg=C["accent2"],
            font=("Segoe UI", 12, "bold"),
            anchor="w").pack(fill="x", padx=14, pady=(10, 4))
        for m in metas_activas[:3]:
            tk.Label(card3, text=f"  • {m['texto']}",
                bg=C["bg3"], fg=C["fg"],
                font=("Segoe UI", 10),
                anchor="w").pack(fill="x", padx=14)
        if not metas_activas:
            tk.Label(card3, text="  (sin metas activas — ve a la pestaña 🎯 Metas)",
                bg=C["bg3"], fg=C["fg2"],
                font=("Segoe UI", 9, "italic"),
                anchor="w").pack(fill="x", padx=14, pady=(0, 8))
        else:
            tk.Frame(card3, bg=C["bg3"], height=8).pack()

        # Motivación IA del día
        card4 = tk.Frame(self.dashboard_tab, bg=C["bg2"])
        card4.pack(fill="both", expand=True, padx=20, pady=8)
        tk.Label(card4, text="✨ Motivación del día (IA)",
            bg=C["bg2"], fg=C["accent"],
            font=("Segoe UI", 12, "bold"),
            anchor="w").pack(fill="x", padx=14, pady=(10, 4))

        self.motivacion_lbl = tk.Label(card4,
            text="Pulsa 'Generar motivación' para una frase personalizada por la IA",
            bg=C["bg2"], fg=C["fg"],
            font=("Segoe UI", 11, "italic"),
            wraplength=1000, justify="left",
            anchor="w")
        self.motivacion_lbl.pack(fill="both", expand=True, padx=14, pady=8)

        tk.Button(card4, text="🌟 Generar motivación con IA",
            command=self._generar_motivacion,
            bg=C["accent"], fg="white", relief="flat",
            font=("Segoe UI", 10, "bold"), cursor="hand2",
            padx=14, pady=6).pack(anchor="w", padx=14, pady=(0, 10))

    def _calcular_racha(self):
        """Cuenta días consecutivos con al menos 50% de hábitos hechos."""
        racha = 0
        d = datetime.now().date()
        min_fecha = datetime(2020, 1, 1).date()   # límite razonable
        # Máximo 365 días hacia atrás
        for _ in range(365):
            if d < min_fecha:
                break
            k = d.strftime("%Y-%m-%d")
            reg = self.datos["registro"].get(k, {})
            if not reg:
                # Si es hoy y no hay registro, sigue buscando ayer
                if racha == 0:
                    d -= timedelta(days=1)
                    continue
                break
            n = sum(1 for v in reg.values() if v)
            total = len(self.datos["habitos"])
            if total > 0 and n >= total / 2:
                racha += 1
                d -= timedelta(days=1)
            else:
                break
        return racha

    def _generar_motivacion(self):
        if not self._check_api(): return
        if self.procesando: return
        self.procesando = True
        self.motivacion_lbl.config(text="⏳ Pensando una frase para ti...",
                                     fg=C["fg2"])

        def tarea():
            perfil = self.datos["perfil"]
            racha = self._calcular_racha()
            system = ("Eres un coach motivacional cálido y enérgico. "
                       "Hablas en español de forma personal y directa, "
                       "como un amigo que cree en mí.")
            user = (f"Dame UNA frase motivacional personalizada (max 30 palabras) "
                    f"para empezar mi día.\n"
                    f"Mi objetivo: {perfil.get('objetivo', 'sentirme mejor')}\n"
                    f"Mi nombre: {perfil.get('nombre', '')}\n"
                    f"Llevo {racha} días de racha.\n"
                    "SOLO la frase, sin comillas ni explicación extra.")
            resp, err = llamar_llm(self.proveedor, self.modelo, self.api_key,
                                    system, user)
            self.procesando = False
            if err:
                self.root.after(0, lambda: self.motivacion_lbl.config(
                    text=f"❌ {err}", fg=C["err"]))
            else:
                self.root.after(0, lambda: self.motivacion_lbl.config(
                    text=f'"{resp.strip()}"', fg=C["accent2"]))
        threading.Thread(target=tarea, daemon=True).start()

    # ============================================================
    # 💪 EJERCICIO
    # ============================================================
    def _tab_ejercicio(self, parent):
        tab = tk.Frame(parent, bg=C["bg"])
        parent.add(tab, text="💪 Ejercicio")

        tk.Label(tab, text="💪 Plan de ejercicio personalizado",
            bg=C["bg"], fg=C["accent"],
            font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=14, pady=12)

        # Opciones
        opt = tk.Frame(tab, bg=C["bg"])
        opt.pack(fill="x", padx=14)

        tk.Label(opt, text="Tipo de plan:",
            bg=C["bg"], fg=C["fg"],
            font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", pady=4)
        self.ej_tipo = tk.StringVar(value="Rutina semanal completa")
        ttk.Combobox(opt, textvariable=self.ej_tipo,
            values=["Rutina semanal completa", "Sesión rápida HIIT (20 min)",
                    "Rutina full body sin material", "Cardio progresivo",
                    "Yoga y flexibilidad", "Fuerza con pesas",
                    "Calistenia para principiantes",
                    "Plan running 5K", "Rehabilitación suave"],
            state="readonly", width=40, font=("Segoe UI", 10)
            ).grid(row=0, column=1, padx=10, pady=4, sticky="w")

        tk.Label(opt, text="Días por semana:",
            bg=C["bg"], fg=C["fg"],
            font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", pady=4)
        self.ej_dias = tk.IntVar(value=3)
        tk.Spinbox(opt, from_=1, to=7, textvariable=self.ej_dias,
            bg=C["bg2"], fg=C["fg"], font=("Segoe UI", 10),
            width=5).grid(row=1, column=1, padx=10, pady=4, sticky="w")

        tk.Label(opt, text="Minutos por sesión:",
            bg=C["bg"], fg=C["fg"],
            font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", pady=4)
        self.ej_min = tk.IntVar(value=30)
        tk.Spinbox(opt, from_=10, to=120, increment=5, textvariable=self.ej_min,
            bg=C["bg2"], fg=C["fg"], font=("Segoe UI", 10),
            width=5).grid(row=2, column=1, padx=10, pady=4, sticky="w")

        tk.Button(tab, text="✨ Generar mi plan de ejercicio",
            command=self._generar_ejercicio,
            bg=C["accent"], fg="white", relief="flat",
            font=("Segoe UI", 11, "bold"), cursor="hand2",
            pady=10).pack(fill="x", padx=14, pady=14)

        self.ej_out = scrolledtext.ScrolledText(tab,
            bg=C["bg2"], fg=C["fg"], font=("Segoe UI", 10),
            wrap="word", relief="flat", padx=14, pady=14)
        self.ej_out.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        # Botón guardar
        tk.Button(tab, text="💾 Guardar este plan",
            command=lambda: self._guardar_plan("ejercicio", self.ej_out.get("1.0", "end")),
            bg=C["bg3"], fg=C["fg"], relief="flat",
            font=("Segoe UI", 10), cursor="hand2",
            padx=14, pady=6).pack(anchor="e", padx=14, pady=(0, 14))

    def _generar_ejercicio(self):
        if not self._check_api(): return
        if self.procesando: return
        self.procesando = True
        self.ej_out.delete("1.0", "end")
        self.ej_out.insert("1.0", "⏳ Diseñando tu plan de ejercicio...\n")
        self.status.config(text="⏳ Generando plan de ejercicio...", fg=C["accent"])

        perfil = self.datos["perfil"]
        def tarea():
            system = ("Eres un entrenador personal certificado. Diseñas planes "
                       "seguros, progresivos y adaptados. Respondes en español "
                       "con formato claro y emojis para hacerlo amigable.")
            user = f"""Diseña un plan de ejercicio personalizado:

Datos del usuario:
- Nombre: {perfil.get('nombre', 'usuario')}
- Edad: {perfil.get('edad', 'no especificada')}
- Peso: {perfil.get('peso', 'no especificado')}
- Altura: {perfil.get('altura', 'no especificada')}
- Objetivo: {perfil.get('objetivo', 'sentirse mejor')}
- Nivel: {perfil.get('nivel', 'principiante')}
- Restricciones físicas: {perfil.get('restricciones', 'ninguna conocida')}

Configuración del plan:
- Tipo: {self.ej_tipo.get()}
- Días por semana: {self.ej_dias.get()}
- Minutos por sesión: {self.ej_min.get()}

Estructura:
🎯 Objetivo del plan
📅 Distribución semanal
💪 Detalle de cada sesión (calentamiento + ejercicios + enfriamiento)
⚠️ Precauciones según el perfil
📈 Cómo progresar en 4 semanas

IMPORTANTE: si la persona tiene restricciones, adapta los ejercicios."""
            resp, err = llamar_llm(self.proveedor, self.modelo, self.api_key,
                                    system, user)
            self.procesando = False
            if err:
                self.root.after(0, lambda: self.ej_out.delete("1.0", "end"))
                self.root.after(0, lambda: self.ej_out.insert("1.0",
                    f"❌ Error: {err}"))
                self.root.after(0, lambda: self.status.config(
                    text=f"❌ {err}", fg=C["err"]))
            else:
                self.root.after(0, lambda: self.ej_out.delete("1.0", "end"))
                self.root.after(0, lambda: self.ej_out.insert("1.0", resp))
                self.root.after(0, lambda: self.status.config(
                    text="✅ Plan de ejercicio listo", fg=C["ok"]))
        threading.Thread(target=tarea, daemon=True).start()

    # ============================================================
    # 🥗 DIETA
    # ============================================================
    def _tab_dieta(self, parent):
        tab = tk.Frame(parent, bg=C["bg"])
        parent.add(tab, text="🥗 Dieta")

        tk.Label(tab, text="🥗 Plan de alimentación personalizado",
            bg=C["bg"], fg=C["accent"],
            font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=14, pady=12)

        opt = tk.Frame(tab, bg=C["bg"])
        opt.pack(fill="x", padx=14)

        tk.Label(opt, text="Tipo de dieta:",
            bg=C["bg"], fg=C["fg"],
            font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", pady=4)
        self.dieta_tipo = tk.StringVar(value="Equilibrada mediterránea")
        ttk.Combobox(opt, textvariable=self.dieta_tipo,
            values=["Equilibrada mediterránea", "Definición/pérdida de peso",
                    "Volumen/ganancia muscular", "Vegana", "Vegetariana",
                    "Sin gluten", "Low carb / Keto", "Diabetes-friendly",
                    "Antiinflamatoria", "Económica y rápida"],
            state="readonly", width=40, font=("Segoe UI", 10)
            ).grid(row=0, column=1, padx=10, pady=4, sticky="w")

        tk.Label(opt, text="Calorías objetivo/día:",
            bg=C["bg"], fg=C["fg"],
            font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", pady=4)
        self.dieta_cal = tk.IntVar(value=2000)
        tk.Spinbox(opt, from_=1200, to=4000, increment=100,
            textvariable=self.dieta_cal,
            bg=C["bg2"], fg=C["fg"], font=("Segoe UI", 10),
            width=8).grid(row=1, column=1, padx=10, pady=4, sticky="w")

        tk.Label(opt, text="Duración:",
            bg=C["bg"], fg=C["fg"],
            font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", pady=4)
        self.dieta_dur = tk.StringVar(value="1 día (menú)")
        ttk.Combobox(opt, textvariable=self.dieta_dur,
            values=["1 día (menú)", "3 días", "1 semana completa", "Lista compra semanal"],
            state="readonly", width=25, font=("Segoe UI", 10)
            ).grid(row=2, column=1, padx=10, pady=4, sticky="w")

        tk.Button(tab, text="✨ Generar mi plan de alimentación",
            command=self._generar_dieta,
            bg=C["accent"], fg="white", relief="flat",
            font=("Segoe UI", 11, "bold"), cursor="hand2",
            pady=10).pack(fill="x", padx=14, pady=14)

        self.dieta_out = scrolledtext.ScrolledText(tab,
            bg=C["bg2"], fg=C["fg"], font=("Segoe UI", 10),
            wrap="word", relief="flat", padx=14, pady=14)
        self.dieta_out.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        tk.Button(tab, text="💾 Guardar este plan",
            command=lambda: self._guardar_plan("dieta", self.dieta_out.get("1.0", "end")),
            bg=C["bg3"], fg=C["fg"], relief="flat",
            font=("Segoe UI", 10), cursor="hand2",
            padx=14, pady=6).pack(anchor="e", padx=14, pady=(0, 14))

    def _generar_dieta(self):
        if not self._check_api(): return
        if self.procesando: return
        self.procesando = True
        self.dieta_out.delete("1.0", "end")
        self.dieta_out.insert("1.0", "⏳ Diseñando tu plan nutricional...\n")
        self.status.config(text="⏳ Generando dieta...", fg=C["accent"])

        perfil = self.datos["perfil"]
        def tarea():
            system = ("Eres un nutricionista profesional. Diseñas menús "
                       "equilibrados, realistas y sabrosos. Indicas cantidades "
                       "y kcal aproximadas. Respondes en español con emojis.")
            user = f"""Diseña un plan nutricional:

Datos:
- Nombre: {perfil.get('nombre', 'usuario')}
- Edad: {perfil.get('edad', 'no especificada')}
- Peso: {perfil.get('peso', 'no especificado')}
- Altura: {perfil.get('altura', 'no especificada')}
- Objetivo: {perfil.get('objetivo', 'sentirse mejor')}
- Restricciones/alergias: {perfil.get('restricciones', 'ninguna')}
- Preferencias: {perfil.get('preferencias', 'sin preferencias especiales')}

Configuración:
- Tipo: {self.dieta_tipo.get()}
- Calorías objetivo/día: {self.dieta_cal.get()} kcal
- Duración: {self.dieta_dur.get()}

Estructura:
🎯 Objetivo nutricional
🍽️ Menú detallado (Desayuno/Media mañana/Comida/Merienda/Cena)
    Para cada comida: ingredientes + kcal aproximadas
💡 Consejos clave de hidratación y suplementación
🛒 Lista de la compra (si se pidió semanal)
⚠️ Notas importantes según restricciones

IMPORTANTE: SI la persona menciona alergias, EVÍTALAS al 100%."""
            resp, err = llamar_llm(self.proveedor, self.modelo, self.api_key,
                                    system, user)
            self.procesando = False
            if err:
                self.root.after(0, lambda: self.dieta_out.delete("1.0", "end"))
                self.root.after(0, lambda: self.dieta_out.insert("1.0",
                    f"❌ Error: {err}"))
            else:
                self.root.after(0, lambda: self.dieta_out.delete("1.0", "end"))
                self.root.after(0, lambda: self.dieta_out.insert("1.0", resp))
                self.root.after(0, lambda: self.status.config(
                    text="✅ Plan de dieta listo", fg=C["ok"]))
        threading.Thread(target=tarea, daemon=True).start()

    # ============================================================
    # ✅ HÁBITOS
    # ============================================================
    def _tab_habitos(self, parent):
        tab = tk.Frame(parent, bg=C["bg"])
        parent.add(tab, text="✅ Hábitos")
        self.habitos_tab = tab
        self._refrescar_habitos()

    def _refrescar_habitos(self):
        for w in self.habitos_tab.winfo_children():
            w.destroy()

        tk.Label(self.habitos_tab, text="✅ Gestiona tus hábitos diarios",
            bg=C["bg"], fg=C["accent"],
            font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=14, pady=12)

        # Lista de hábitos con poder editar
        lista_frame = tk.Frame(self.habitos_tab, bg=C["bg2"])
        lista_frame.pack(fill="x", padx=14, pady=8)

        tk.Label(lista_frame, text="Mis hábitos actuales:",
            bg=C["bg2"], fg=C["accent2"],
            font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(10, 4))

        for i, h in enumerate(self.datos["habitos"]):
            fila = tk.Frame(lista_frame, bg=C["bg2"])
            fila.pack(fill="x", padx=12, pady=2)
            tk.Label(fila, text=f"{h['emoji']} {h['nombre']}",
                bg=C["bg2"], fg=C["fg"],
                font=("Segoe UI", 10), anchor="w").pack(side="left", fill="x", expand=True)
            tk.Button(fila, text="🗑", command=lambda i=i: self._borrar_habito(i),
                bg=C["err"], fg="white", relief="flat",
                font=("Segoe UI", 9), cursor="hand2",
                padx=8).pack(side="right", padx=2)

        tk.Label(lista_frame, text="", bg=C["bg2"]).pack(pady=4)

        # Añadir
        add_frame = tk.Frame(self.habitos_tab, bg=C["bg3"])
        add_frame.pack(fill="x", padx=14, pady=8)
        tk.Label(add_frame, text="➕ Añadir hábito nuevo",
            bg=C["bg3"], fg=C["accent2"],
            font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(10, 4))

        sub = tk.Frame(add_frame, bg=C["bg3"])
        sub.pack(fill="x", padx=12, pady=8)
        tk.Label(sub, text="Emoji:", bg=C["bg3"], fg=C["fg"],
            font=("Segoe UI", 10)).pack(side="left")
        emoji_entry = tk.Entry(sub, bg=C["bg2"], fg=C["fg"],
            insertbackground=C["fg"], relief="flat",
            font=("Segoe UI", 12), width=4)
        emoji_entry.insert(0, "⭐")
        emoji_entry.pack(side="left", padx=6, ipady=4)

        tk.Label(sub, text="Hábito:", bg=C["bg3"], fg=C["fg"],
            font=("Segoe UI", 10)).pack(side="left", padx=(10, 0))
        nombre_entry = tk.Entry(sub, bg=C["bg2"], fg=C["fg"],
            insertbackground=C["fg"], relief="flat",
            font=("Segoe UI", 11))
        nombre_entry.pack(side="left", padx=6, ipady=4, fill="x", expand=True)

        def add():
            n = nombre_entry.get().strip()
            e = emoji_entry.get().strip() or "⭐"
            if n:
                self.datos["habitos"].append({"emoji": e, "nombre": n})
                self._guardar_datos()
                self._refrescar_habitos()
                self._refrescar_dashboard()
        tk.Button(sub, text="Añadir", command=add,
            bg=C["accent"], fg="white", relief="flat",
            font=("Segoe UI", 10, "bold"), cursor="hand2",
            padx=14).pack(side="left", padx=6)

        # Estadística semanal
        stats_frame = tk.Frame(self.habitos_tab, bg=C["bg2"])
        stats_frame.pack(fill="both", expand=True, padx=14, pady=8)
        tk.Label(stats_frame, text="📈 Últimos 7 días",
            bg=C["bg2"], fg=C["accent"],
            font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(10, 4))

        # Mini-tabla últimos 7 días
        for d in range(7):
            dia = datetime.now().date() - timedelta(days=6 - d)
            key = dia.strftime("%Y-%m-%d")
            reg = self.datos["registro"].get(key, {})
            done = sum(1 for v in reg.values() if v)
            total = len(self.datos["habitos"])
            pct = int(100 * done / total) if total else 0

            fila = tk.Frame(stats_frame, bg=C["bg2"])
            fila.pack(fill="x", padx=12, pady=2)
            tk.Label(fila, text=dia.strftime("%a %d/%m"),
                bg=C["bg2"], fg=C["fg2"],
                font=("Consolas", 10), width=14, anchor="w"
                ).pack(side="left")
            tk.Label(fila, text=f"{done}/{total}",
                bg=C["bg2"], fg=C["fg"],
                font=("Consolas", 10), width=8, anchor="w"
                ).pack(side="left")
            # mini barra
            bar_bg = tk.Frame(fila, bg=C["bg3"], height=12, width=300)
            bar_bg.pack(side="left", padx=8)
            bar_bg.pack_propagate(False)
            color = C["accent"] if pct >= 70 else (C["accent2"] if pct >= 40 else C["warn"])
            if pct > 0:
                tk.Frame(bar_bg, bg=color).place(x=0, y=0,
                    relwidth=pct / 100, relheight=1)

    def _borrar_habito(self, idx):
        if messagebox.askyesno("Borrar",
            f"¿Borrar '{self.datos['habitos'][idx]['nombre']}'?"):
            del self.datos["habitos"][idx]
            self._guardar_datos()
            self._refrescar_habitos()
            self._refrescar_dashboard()

    # ============================================================
    # 🎯 METAS
    # ============================================================
    def _tab_metas(self, parent):
        tab = tk.Frame(parent, bg=C["bg"])
        parent.add(tab, text="🎯 Metas")
        self.metas_tab = tab
        self._refrescar_metas()

    def _refrescar_metas(self):
        for w in self.metas_tab.winfo_children():
            w.destroy()

        tk.Label(self.metas_tab, text="🎯 Mis metas",
            bg=C["bg"], fg=C["accent"],
            font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=14, pady=12)

        # Nueva meta
        add = tk.Frame(self.metas_tab, bg=C["bg3"])
        add.pack(fill="x", padx=14, pady=8)
        tk.Label(add, text="➕ Añadir meta nueva",
            bg=C["bg3"], fg=C["accent2"],
            font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(10, 4))

        entry = tk.Entry(add, bg=C["bg2"], fg=C["fg"],
            insertbackground=C["fg"], relief="flat",
            font=("Segoe UI", 11))
        entry.pack(fill="x", padx=12, ipady=6)

        def add_meta(e=None):
            t = entry.get().strip()
            if t:
                self.datos["metas"].append({
                    "texto": t,
                    "fecha_creacion": datetime.now().isoformat(),
                    "completada": False,
                })
                self._guardar_datos()
                entry.delete(0, "end")
                self._refrescar_metas()
                self._refrescar_dashboard()
        entry.bind("<Return>", add_meta)

        bf = tk.Frame(add, bg=C["bg3"])
        bf.pack(fill="x", padx=12, pady=8)
        tk.Button(bf, text="➕ Añadir", command=add_meta,
            bg=C["accent"], fg="white", relief="flat",
            font=("Segoe UI", 10, "bold"), cursor="hand2",
            padx=14, pady=4).pack(side="left", padx=2)
        tk.Button(bf, text="💡 Sugerir metas SMART con IA",
            command=self._sugerir_metas,
            bg=C["info"], fg="white", relief="flat",
            font=("Segoe UI", 10, "bold"), cursor="hand2",
            padx=14, pady=4).pack(side="left", padx=2)

        # Activas
        activas = [(i, m) for i, m in enumerate(self.datos["metas"])
                    if not m.get("completada")]
        comp = [(i, m) for i, m in enumerate(self.datos["metas"])
                 if m.get("completada")]

        tk.Label(self.metas_tab, text=f"🔥 Activas ({len(activas)})",
            bg=C["bg"], fg=C["accent2"],
            font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(12, 4))

        for i, m in activas:
            fila = tk.Frame(self.metas_tab, bg=C["bg3"])
            fila.pack(fill="x", padx=14, pady=2)
            tk.Label(fila, text=f"  🎯 {m['texto']}",
                bg=C["bg3"], fg=C["fg"],
                font=("Segoe UI", 10), anchor="w"
                ).pack(side="left", fill="x", expand=True, padx=4, pady=6)
            tk.Button(fila, text="✅ Completar",
                command=lambda i=i: self._completar_meta(i),
                bg=C["accent"], fg="white", relief="flat",
                font=("Segoe UI", 9, "bold"), cursor="hand2",
                padx=10).pack(side="right", padx=2)
            tk.Button(fila, text="🗑", command=lambda i=i: self._borrar_meta(i),
                bg=C["err"], fg="white", relief="flat",
                font=("Segoe UI", 9), cursor="hand2",
                padx=6).pack(side="right", padx=2)

        if comp:
            tk.Label(self.metas_tab, text=f"✅ Completadas ({len(comp)})",
                bg=C["bg"], fg=C["fg2"],
                font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(12, 4))
            for i, m in comp:
                fila = tk.Frame(self.metas_tab, bg=C["bg2"])
                fila.pack(fill="x", padx=14, pady=1)
                tk.Label(fila, text=f"  ✓ {m['texto']}",
                    bg=C["bg2"], fg=C["fg2"],
                    font=("Segoe UI", 9, "overstrike"),
                    anchor="w").pack(side="left", fill="x", expand=True, padx=4, pady=4)

    def _completar_meta(self, idx):
        self.datos["metas"][idx]["completada"] = True
        self.datos["metas"][idx]["fecha_completada"] = datetime.now().isoformat()
        self._guardar_datos()
        self._refrescar_metas()
        self._refrescar_dashboard()
        messagebox.showinfo("🎉 ¡Felicidades!",
            "¡Has completado una meta! 🌟\nSigue así.")

    def _borrar_meta(self, idx):
        del self.datos["metas"][idx]
        self._guardar_datos()
        self._refrescar_metas()
        self._refrescar_dashboard()

    def _sugerir_metas(self):
        if not self._check_api(): return
        if self.procesando: return
        self.procesando = True
        self.status.config(text="⏳ Pidiendo metas a la IA...", fg=C["accent"])

        perfil = self.datos["perfil"]
        def tarea():
            system = ("Eres un coach que aplica el método SMART (específico, medible, "
                       "alcanzable, relevante, temporal). Respondes solo con la lista, "
                       "una meta por línea.")
            user = (f"Sugiere 5 metas SMART concretas y alcanzables para una persona "
                    f"con este perfil:\n"
                    f"- Objetivo general: {perfil.get('objetivo', 'mejorar bienestar')}\n"
                    f"- Nivel: {perfil.get('nivel', 'principiante')}\n\n"
                    "Formato: una meta por línea, sin numerar, sin viñetas, "
                    "sólo el texto de cada meta.")
            resp, err = llamar_llm(self.proveedor, self.modelo, self.api_key,
                                    system, user)
            self.procesando = False
            if err:
                self.root.after(0, lambda: self.status.config(
                    text=f"❌ {err}", fg=C["err"]))
                return
            metas_sugeridas = [l.strip().lstrip("-•*123456789. ")
                                 for l in resp.split("\n")
                                 if l.strip() and len(l.strip()) > 10]
            self.root.after(0, lambda: self._dialogo_metas_sugeridas(metas_sugeridas))
        threading.Thread(target=tarea, daemon=True).start()

    def _dialogo_metas_sugeridas(self, metas):
        dlg = tk.Toplevel(self.root)
        dlg.title("💡 Metas sugeridas por la IA")
        dlg.geometry("640x460")
        dlg.configure(bg=C["bg"])

        tk.Label(dlg, text="💡 Marca las metas que quieras añadir",
            bg=C["bg"], fg=C["accent"],
            font=("Segoe UI", 12, "bold")).pack(pady=12)

        vars_ = []
        for m in metas:
            var = tk.BooleanVar(value=True)
            vars_.append((var, m))
            tk.Checkbutton(dlg, text=m, variable=var,
                bg=C["bg"], fg=C["fg"], selectcolor=C["bg2"],
                activebackground=C["bg"], activeforeground=C["accent"],
                font=("Segoe UI", 10), wraplength=560,
                justify="left", anchor="w").pack(fill="x", padx=20, pady=4)

        def añadir():
            for var, m in vars_:
                if var.get():
                    self.datos["metas"].append({
                        "texto": m,
                        "fecha_creacion": datetime.now().isoformat(),
                        "completada": False,
                    })
            self._guardar_datos()
            self._refrescar_metas()
            self._refrescar_dashboard()
            self.status.config(text="✅ Metas añadidas", fg=C["ok"])
            dlg.destroy()

        tk.Button(dlg, text="➕ Añadir seleccionadas", command=añadir,
            bg=C["accent"], fg="white", relief="flat",
            font=("Segoe UI", 11, "bold"), cursor="hand2",
            padx=16, pady=6).pack(pady=14)

    # ============================================================
    # 💬 CHAT CON EL COACH
    # ============================================================
    def _tab_chat(self, parent):
        tab = tk.Frame(parent, bg=C["bg"])
        parent.add(tab, text="💬 Chat coach")

        tk.Label(tab, text="💬 Habla con tu coach personal",
            bg=C["bg"], fg=C["accent"],
            font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=14, pady=12)
        tk.Label(tab, text="Pregúntale lo que quieras: dudas, motivación, consejos...",
            bg=C["bg"], fg=C["fg2"],
            font=("Segoe UI", 9, "italic")).pack(anchor="w", padx=14)

        self.chat_out = scrolledtext.ScrolledText(tab,
            bg=C["bg2"], fg=C["fg"], font=("Segoe UI", 10),
            wrap="word", relief="flat", padx=14, pady=14)
        self.chat_out.pack(fill="both", expand=True, padx=14, pady=10)
        self.chat_out.tag_config("user", foreground=C["accent2"],
                                  font=("Segoe UI", 10, "bold"))
        self.chat_out.tag_config("coach", foreground=C["accent"],
                                  font=("Segoe UI", 10))

        self.chat_out.insert("end",
            "🎓 Coach: ¡Hola! Soy tu coach personal. ¿En qué puedo ayudarte hoy?\n\n",
            "coach")

        bottom = tk.Frame(tab, bg=C["bg"])
        bottom.pack(fill="x", padx=14, pady=10)
        self.chat_entry = tk.Entry(bottom, bg=C["bg2"], fg=C["fg"],
            insertbackground=C["fg"], relief="flat",
            font=("Segoe UI", 11))
        self.chat_entry.pack(side="left", fill="x", expand=True, ipady=8)
        self.chat_entry.bind("<Return>", lambda e: self._chat_send())

        tk.Button(bottom, text="🚀 Enviar", command=self._chat_send,
            bg=C["accent"], fg="white", relief="flat",
            font=("Segoe UI", 10, "bold"), cursor="hand2",
            padx=16, pady=6).pack(side="left", padx=6)

        self.historial_chat = []

    def _chat_send(self):
        msg = self.chat_entry.get().strip()
        if not msg: return
        if not self._check_api(): return
        if self.procesando: return

        self.chat_out.insert("end", f"Tú: {msg}\n\n", "user")
        self.chat_entry.delete(0, "end")
        self.chat_out.insert("end", "🎓 Coach: ⏳ pensando...\n", "coach")
        self.chat_out.see("end")
        self.procesando = True

        def tarea():
            perfil = self.datos["perfil"]
            system = (f"Eres un coach personal cálido y motivador. "
                       f"Hablas en español, eres empático, das consejos prácticos. "
                       f"Conoces estos datos del usuario:\n"
                       f"- Nombre: {perfil.get('nombre', 'usuario')}\n"
                       f"- Objetivo: {perfil.get('objetivo', 'mejorar')}\n"
                       f"- Nivel: {perfil.get('nivel', 'principiante')}\n"
                       f"- Restricciones: {perfil.get('restricciones', 'ninguna')}\n"
                       f"- Racha actual: {self._calcular_racha()} días\n"
                       f"Sé conciso pero cálido.")
            resp, err = llamar_llm(self.proveedor, self.modelo, self.api_key,
                                    system, msg,
                                    historial=self.historial_chat[-10:])
            self.procesando = False
            # Eliminar el "pensando..."
            self.root.after(0, lambda: self.chat_out.delete("end-2l", "end-1l"))
            if err:
                self.root.after(0, lambda: self.chat_out.insert("end",
                    f"🎓 Coach: ❌ Error: {err}\n\n", "coach"))
            else:
                self.historial_chat.append({"role": "user", "content": msg})
                self.historial_chat.append({"role": "assistant", "content": resp})
                self.root.after(0, lambda: self.chat_out.insert("end",
                    f"🎓 Coach: {resp}\n\n", "coach"))
            self.root.after(0, lambda: self.chat_out.see("end"))
        threading.Thread(target=tarea, daemon=True).start()

    # ============================================================
    # PERFIL
    # ============================================================
    def _editar_perfil(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("👤 Mi perfil")
        dlg.geometry("520x620")
        dlg.configure(bg=C["bg"])

        tk.Label(dlg, text="👤 Cuéntame sobre ti",
            bg=C["bg"], fg=C["accent"],
            font=("Segoe UI", 14, "bold")).pack(pady=12)

        entries = {}
        campos = [
            ("nombre", "Nombre"),
            ("edad", "Edad"),
            ("peso", "Peso (kg)"),
            ("altura", "Altura (cm)"),
            ("objetivo", "Objetivo principal"),
            ("nivel", "Nivel (principiante/medio/avanzado)"),
        ]
        for k, label in campos:
            row = tk.Frame(dlg, bg=C["bg"])
            row.pack(fill="x", padx=20, pady=4)
            tk.Label(row, text=f"{label}:", bg=C["bg"], fg=C["fg2"],
                font=("Segoe UI", 10), width=22, anchor="w").pack(side="left")
            e = tk.Entry(row, bg=C["bg2"], fg=C["fg"],
                insertbackground=C["fg"], relief="flat",
                font=("Segoe UI", 10))
            e.insert(0, self.datos["perfil"].get(k, ""))
            e.pack(side="left", fill="x", expand=True, ipady=4)
            entries[k] = e

        # Texto multilínea
        for k, label in [("restricciones", "Restricciones / Alergias"),
                          ("preferencias", "Preferencias / Gustos")]:
            tk.Label(dlg, text=f"{label}:",
                bg=C["bg"], fg=C["accent"],
                font=("Segoe UI", 10, "bold"),
                anchor="w").pack(fill="x", padx=20, pady=(10, 2))
            t = tk.Text(dlg, bg=C["bg2"], fg=C["fg"],
                insertbackground=C["fg"], relief="flat",
                font=("Segoe UI", 10), height=3, wrap="word")
            t.insert("1.0", self.datos["perfil"].get(k, ""))
            t.pack(fill="x", padx=20, pady=2)
            entries[k] = t

        def guardar():
            for k, w in entries.items():
                if isinstance(w, tk.Text):
                    self.datos["perfil"][k] = w.get("1.0", "end").strip()
                else:
                    self.datos["perfil"][k] = w.get().strip()
            self._guardar_datos()
            # Sincronizar campos clave con el Brain global
            if BRAIN:
                for k in ("nombre", "edad"):
                    if self.datos["perfil"].get(k):
                        BRAIN.perfil(k, self.datos["perfil"][k])
                BRAIN.stat("coach", "perfiles_guardados", incrementar=1)
            self._refrescar_dashboard()
            self.status.config(text="✅ Perfil actualizado (sincronizado con Brain)",
                                fg=C["ok"])
            dlg.destroy()

        tk.Button(dlg, text="💾 Guardar perfil", command=guardar,
            bg=C["accent"], fg="white", relief="flat",
            font=("Segoe UI", 11, "bold"), cursor="hand2",
            padx=20, pady=8).pack(pady=18)

    # ============================================================
    # UTILS
    # ============================================================
    def _check_api(self):
        if not self.api_key and self.proveedor != "Ollama":
            messagebox.showwarning("⚠️",
                "Configura tu API Key en ⚙ Config IA primero.")
            return False
        return True

    def _guardar_plan(self, tipo, contenido):
        self.datos.setdefault("planes", {})[tipo] = {
            "fecha": datetime.now().isoformat(),
            "contenido": contenido,
        }
        self._guardar_datos()
        self.status.config(text=f"✅ Plan de {tipo} guardado", fg=C["ok"])

    def _config_ia(self):
        cfg = {"proveedor": self.proveedor, "modelo": self.modelo,
               "api_key": self.api_key, "api_keys": self.cfg.get("api_keys", {})}
        col = {"bg": C["bg"], "bg2": C["bg2"], "fg": C["fg"],
               "accent": C["accent"], "warn": C["warn"], "ok": C["ok"]}
        def on_save(n):
            self.proveedor = n["proveedor"]; self.modelo = n["modelo"]
            self.api_key = n["api_key"]
            self.cfg["coach_proveedor"] = self.proveedor
            self.cfg["coach_modelo"] = self.modelo
            self.cfg["api_keys"] = n["api_keys"]
            self._guardar_cfg()
        dialogo_config(self.root, cfg, on_save,
            titulo="⚙ Configuración IA — Coach", colores=col)


if __name__ == "__main__":
    try:
        from nova_ui import splash_screen, Theme
        splash_screen("NOVA Coach",
                       subtitulo="Tu entrenador personal con IA",
                       color_acento=Theme.accent5,
                       tareas=[
                           ("Cargando tu perfil...", None),
                           ("Preparando planes...", None),
                           ("Motor de habitos activo...", None),
                       ],
                       duracion_min=1.3)
    except Exception as e:
        print(f"Splash: {e}")

    root = tk.Tk()
    app = NovaCoach(root)
    root.mainloop()
