"""
🎮 NOVA GAME MASTER — Master de Rol con IA
============================================
- Dirige aventuras estilo D&D, sci-fi, terror, fantasía
- Sistema de tirada de dados (1d6, 1d20...)
- Hoja de personaje con stats
- Memoria persistente (recuerda decisiones)
- Genera arte de escenas con Pollinations
"""
import os, sys, json, threading, random, urllib.request, urllib.parse
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# VERSION (para el sistema de actualizaciones)
# ============================================================
VERSION = "1.0.0"
MODULO_ID = "game_master"

PARENT = os.path.dirname(APP_DIR)
CONFIG = os.path.join(PARENT, "config.json")
PARTIDAS_DIR = os.path.join(APP_DIR, "partidas")
ARTE_DIR = os.path.join(APP_DIR, "arte")
os.makedirs(PARTIDAS_DIR, exist_ok=True)
os.makedirs(ARTE_DIR, exist_ok=True)

GENEROS = {
    "🏰 Fantasía épica": "Mundo medieval de fantasía con magos, dragones, elfos y orcos. Tono épico y heroico.",
    "🚀 Ciencia ficción": "Lejano futuro espacial con naves, alienígenas, planetas exóticos y tecnología avanzada.",
    "👻 Terror cósmico": "Horror lovecraftiano, criaturas indescriptibles, locura, atmósfera opresiva.",
    "🤠 Western": "Lejano oeste, vaqueros, forajidos, pueblos polvorientos, duelos al amanecer.",
    "🕵️ Misterio noir": "Años 40, detective duro, ciudad lluviosa, femme fatale, conspiraciones.",
    "🧟 Apocalipsis zombie": "Mundo post-apocalíptico, supervivientes, hordas de zombis, recursos escasos.",
    "⚔️ Samurai feudal": "Japón medieval, samuráis, honor, espíritus yokai, batallas con katana.",
    "🌊 Piratas del Caribe": "Mares tropicales, tesoros enterrados, barcos pirata, leyendas y maldiciones.",
}


# Importar librería compartida de IA
sys.path.insert(0, APP_DIR)
from nova_ia_lib import llamar_llm, dialogo_config, listar_modelos

def cargar_cfg():
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return {}

def generar_arte(prompt, ruta):
    try:
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=768&height=512&nologo=true"
        urllib.request.urlretrieve(url, ruta)
        return True
    except: return False

class NovaGameMaster:
    def __init__(self):
        self.cfg = cargar_cfg()
        self.proveedor = self.cfg.get("gm_proveedor", "Gemini")
        self.modelo = self.cfg.get("gm_modelo", "gemini-2.5-flash")
        self.api_key = self.cfg.get("api_keys", {}).get(self.proveedor, "")

        self.genero = "🏰 Fantasía épica"
        self.personaje = {"nombre": "Aventurero", "clase": "Guerrero",
                           "raza": "Humano", "vida": 20, "stats": {}}
        self.historial = []  # turnos de la partida
        self.partida_id = None

        self.root = tk.Tk()
        self.root.title("🎮 NOVA Game Master")
        self.root.geometry("900x720")
        self.root.configure(bg="#1a0a2e")
        self._build()
        self._pantalla_inicio()

    def _build(self):
        top = tk.Frame(self.root, bg="#0a0518", height=50)
        top.pack(fill="x"); top.pack_propagate(False)
        tk.Label(top, text="🎮  NOVA Game Master", bg="#0a0518", fg="#fbbf24",
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=14, pady=8)
        tk.Button(top, text="📜 Mis partidas", command=self._listar_partidas,
                  bg="#7c2d12", fg="white", relief="flat", padx=10,
                  cursor="hand2").pack(side="right", padx=4, pady=10)
        tk.Button(top, text="⚙ Config", command=self._config,
                  bg="#374151", fg="white", relief="flat", padx=10,
                  cursor="hand2").pack(side="right", padx=4, pady=10)

        # Frame principal
        self.main = tk.Frame(self.root, bg="#1a0a2e")
        self.main.pack(fill="both", expand=True, padx=14, pady=8)

    def _limpiar(self):
        for w in self.main.winfo_children(): w.destroy()

    def _pantalla_inicio(self):
        self._limpiar()
        tk.Label(self.main, text="🎲 BIENVENIDO A NOVA GAME MASTER 🎲",
                 bg="#1a0a2e", fg="#fbbf24",
                 font=("Segoe UI", 18, "bold")).pack(pady=20)
        tk.Label(self.main, text="Una IA dirigirá una aventura interactiva contigo",
                 bg="#1a0a2e", fg="#e9d5ff",
                 font=("Segoe UI", 11, "italic")).pack(pady=4)

        # Elegir género
        tk.Label(self.main, text="🌍 Elige el género de tu aventura:",
                 bg="#1a0a2e", fg="#fbbf24",
                 font=("Segoe UI", 12, "bold")).pack(pady=(20, 8))

        gf = tk.Frame(self.main, bg="#1a0a2e"); gf.pack()
        self.gen_var = tk.StringVar(value=self.genero)
        for i, (g, desc) in enumerate(GENEROS.items()):
            f = tk.Frame(gf, bg="#2d1b4e", padx=10, pady=8)
            f.grid(row=i//2, column=i%2, padx=6, pady=4, sticky="ew")
            tk.Radiobutton(f, text=g, variable=self.gen_var, value=g,
                           bg="#2d1b4e", fg="#fbbf24", selectcolor="#0a0518",
                           activebackground="#2d1b4e",
                           font=("Segoe UI", 10, "bold"), cursor="hand2"
                           ).pack(anchor="w")
            tk.Label(f, text=desc[:80]+"...", bg="#2d1b4e", fg="#e9d5ff",
                     font=("Segoe UI", 8), wraplength=320,
                     justify="left").pack(anchor="w", padx=14)

        # Personaje
        tk.Label(self.main, text="👤 Tu personaje:",
                 bg="#1a0a2e", fg="#fbbf24",
                 font=("Segoe UI", 12, "bold")).pack(pady=(20, 6))
        pf = tk.Frame(self.main, bg="#1a0a2e"); pf.pack()
        self.pj_nombre = tk.Entry(pf, bg="#2d1b4e", fg="white", relief="flat",
                                   font=("Segoe UI", 11), insertbackground="white")
        self.pj_nombre.insert(0, "Aventurero"); self.pj_nombre.grid(row=0, column=1, padx=4, ipady=4)
        tk.Label(pf, text="Nombre:", bg="#1a0a2e", fg="white").grid(row=0, column=0, padx=4)
        self.pj_clase = tk.Entry(pf, bg="#2d1b4e", fg="white", relief="flat",
                                   font=("Segoe UI", 11), insertbackground="white")
        self.pj_clase.insert(0, "Guerrero"); self.pj_clase.grid(row=1, column=1, padx=4, ipady=4, pady=4)
        tk.Label(pf, text="Clase:", bg="#1a0a2e", fg="white").grid(row=1, column=0, padx=4)

        tk.Button(self.main, text="🎲  ¡EMPEZAR AVENTURA!  🎲",
                  command=self._iniciar_partida,
                  bg="#ef4444", fg="white",
                  font=("Segoe UI", 14, "bold"),
                  relief="flat", padx=30, pady=15, cursor="hand2"
                  ).pack(pady=24)

    def _iniciar_partida(self):
        if not self.api_key and self.proveedor != "Ollama":
            messagebox.showwarning("Sin API", "Configura una IA en ⚙ Config"); return
        self.genero = self.gen_var.get()
        self.personaje["nombre"] = self.pj_nombre.get().strip() or "Aventurero"
        self.personaje["clase"] = self.pj_clase.get().strip() or "Guerrero"
        self.partida_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.historial = []
        self._pantalla_juego()
        self._narrar_inicio()

    def _pantalla_juego(self):
        self._limpiar()
        # Header de partida
        hd = tk.Frame(self.main, bg="#2d1b4e", padx=10, pady=6)
        hd.pack(fill="x", pady=(0, 8))
        tk.Label(hd, text=f"🎲 {self.genero}  |  👤 {self.personaje['nombre']} ({self.personaje['clase']})",
                 bg="#2d1b4e", fg="#fbbf24",
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Button(hd, text="💾 Guardar", command=self._guardar_partida,
                  bg="#22c55e", fg="white", relief="flat", padx=8,
                  cursor="hand2").pack(side="right", padx=2)

        # Narración
        self.narracion = scrolledtext.ScrolledText(self.main, bg="#0a0518",
            fg="#fbbf24", font=("Georgia", 11), padx=14, pady=10,
            relief="flat", state="disabled", wrap="word")
        self.narracion.pack(fill="both", expand=True)
        self.narracion.tag_config("nova", foreground="#fbbf24")
        self.narracion.tag_config("user", foreground="#60a5fa",
                                   font=("Georgia", 11, "bold"))
        self.narracion.tag_config("sys", foreground="#a78bfa",
                                   font=("Georgia", 10, "italic"))
        self.narracion.tag_config("dado", foreground="#ef4444",
                                   font=("Georgia", 12, "bold"))

        # Acciones rápidas
        af = tk.Frame(self.main, bg="#1a0a2e"); af.pack(fill="x", pady=4)
        for txt, cmd in [
            ("🎲 1d6", lambda: self._dado(6)),
            ("🎲 1d20", lambda: self._dado(20)),
            ("🎲 1d100", lambda: self._dado(100)),
            ("🎨 Generar arte", self._generar_arte_escena),
            ("👤 Ver personaje", self._ver_personaje),
        ]:
            tk.Button(af, text=txt, command=cmd,
                      bg="#7c3aed", fg="white", relief="flat",
                      font=("Segoe UI", 9, "bold"), padx=8, pady=4,
                      cursor="hand2").pack(side="left", padx=2)

        # Entrada
        ef = tk.Frame(self.main, bg="#1a0a2e"); ef.pack(fill="x", pady=6)
        self.accion = tk.Entry(ef, bg="#2d1b4e", fg="white", relief="flat",
                                font=("Segoe UI", 12), insertbackground="white")
        self.accion.pack(side="left", fill="x", expand=True, ipady=10, padx=(0,6))
        self.accion.bind("<Return>", lambda e: self._enviar_accion())
        tk.Button(ef, text="🗡️ HACER", command=self._enviar_accion,
                  bg="#ef4444", fg="white", font=("Segoe UI", 11, "bold"),
                  relief="flat", padx=14, cursor="hand2").pack(side="right")

    def _agregar(self, autor, texto, tag):
        self.narracion.config(state="normal")
        self.narracion.insert("end", f"\n{autor}:\n", tag if tag != "nova" else "sys")
        self.narracion.insert("end", f"{texto}\n", tag)
        self.narracion.see("end")
        self.narracion.config(state="disabled")

    def _narrar_inicio(self):
        descripcion = GENEROS[self.genero]
        system = (
            f"Eres un MAESTRO DE ROL EXPERTO dirigiendo una aventura. "
            f"GÉNERO: {self.genero}\n"
            f"AMBIENTACIÓN: {descripcion}\n"
            f"PROTAGONISTA: {self.personaje['nombre']} el {self.personaje['clase']}\n\n"
            f"REGLAS:\n"
            f"1. Narra de forma INMERSIVA, evocadora, en segunda persona ('Tú ves...').\n"
            f"2. Cada escena debe terminar ofreciendo 3-4 opciones de acción al jugador.\n"
            f"3. Sé descriptivo pero CONCISO (4-8 frases por turno).\n"
            f"4. Cuando el jugador haga algo que requiera azar, pídele tirar un dado "
            f"(ej: 'Tira 1d20 para esquivar').\n"
            f"5. Mantén la coherencia con la historia previa.\n"
            f"6. Responde SIEMPRE en español, tono épico/cinematográfico."
        )
        self.system_prompt = system
        msg_inicial = ("Empieza la aventura con una escena inicial impactante. "
                       "Describe dónde está el protagonista, qué ve, oye y siente. "
                       "Termina con 3-4 opciones de acción.")
        self.historial.append({"role":"user","content":msg_inicial})
        self._agregar("📜 EL MASTER", "Narrando el inicio de la aventura...", "sys")
        self._consultar_ia()

    def _enviar_accion(self):
        accion = self.accion.get().strip()
        if not accion: return
        self.accion.delete(0, "end")
        self._agregar(f"⚔️ {self.personaje['nombre']}", accion, "user")
        self.historial.append({"role":"user","content":accion})
        self._consultar_ia()

    def _consultar_ia(self):
        self._agregar("🎲", "(El Master piensa...)", "sys")
        def tarea():
            # Separar último mensaje user del historial previo
            hist = self.historial[-20:]
            if hist and hist[-1]["role"] == "user":
                user_actual = hist[-1]["content"]
                historial_previo = hist[:-1]
            else:
                user_actual = "Continúa la aventura"
                historial_previo = hist
            resp, err = llamar_llm(self.proveedor, self.modelo, self.api_key,
                                    self.system_prompt, user_actual,
                                    historial=historial_previo)
            if err:
                self.root.after(0, self._agregar, "❌", err, "sys")
                return
            self.historial.append({"role":"assistant","content":resp})
            self.root.after(0, self._agregar, "📜 EL MASTER", resp, "nova")
            # Auto-guardado
            self._guardar_partida(silent=True)
        threading.Thread(target=tarea, daemon=True).start()

    def _dado(self, caras):
        resultado = random.randint(1, caras)
        msg = f"🎲 ¡Tiras 1d{caras}!  →  RESULTADO: {resultado}"
        if resultado == caras:
            msg += "  ⭐ ¡CRÍTICO!"
        elif resultado == 1:
            msg += "  💀 ¡PIFIA!"
        self._agregar("DADOS", msg, "dado")
        # Avisar a la IA del resultado
        self.historial.append({"role":"user",
            "content":f"He tirado 1d{caras} y ha salido {resultado}. Continúa la aventura."})
        self._consultar_ia()

    def _generar_arte_escena(self):
        if not self.historial: return
        # Coger última narración del master
        ultima = next((m["content"] for m in reversed(self.historial)
                        if m["role"] == "assistant"), "")
        if not ultima: return
        self._agregar("🎨", "Generando arte de la escena (~15s)...", "sys")
        def tarea():
            # Pedir a la IA un prompt de imagen en inglés
            prompt_resp, _ = llamar_llm(self.proveedor, self.modelo, self.api_key,
                "Convierte esta escena en un prompt de imagen MUY DETALLADO en inglés, "
                "estilo arte digital cinematográfico. SOLO devuelve el prompt, nada más.",
                ultima[:500])
            if not prompt_resp:
                prompt_resp = "epic fantasy scene, cinematic lighting"
            ruta = os.path.join(ARTE_DIR,
                f"escena_{self.partida_id}_{int(datetime.now().timestamp())}.png")
            if generar_arte(prompt_resp[:200], ruta):
                self.root.after(0, self._agregar, "🎨",
                    f"✅ Imagen guardada: {ruta}", "sys")
                try:
                    if sys.platform.startswith("win"): os.startfile(ruta)
                except: pass
            else:
                self.root.after(0, self._agregar, "🎨", "❌ Error generando", "sys")
        threading.Thread(target=tarea, daemon=True).start()

    def _ver_personaje(self):
        info = (f"👤 {self.personaje['nombre']}\n"
                f"⚔️ Clase: {self.personaje['clase']}\n"
                f"❤️ Vida: {self.personaje.get('vida', 20)}\n"
                f"🌍 Aventura: {self.genero}\n"
                f"📜 Turnos jugados: {len(self.historial)//2}")
        messagebox.showinfo(f"Personaje de {self.personaje['nombre']}", info)

    def _guardar_partida(self, silent=False):
        if not self.partida_id: return
        path = os.path.join(PARTIDAS_DIR, f"partida_{self.partida_id}.json")
        data = {"genero": self.genero, "personaje": self.personaje,
                "historial": self.historial, "fecha": self.partida_id,
                "system_prompt": getattr(self, "system_prompt", "")}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        if not silent:
            messagebox.showinfo("💾 Guardado", f"Partida guardada:\n{path}")

    def _listar_partidas(self):
        partidas = []
        for f in sorted(os.listdir(PARTIDAS_DIR), reverse=True):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(PARTIDAS_DIR, f), "r", encoding="utf-8") as fh:
                        d = json.load(fh)
                    partidas.append((f, d))
                except: pass
        if not partidas:
            messagebox.showinfo("Sin partidas", "No hay partidas guardadas todavía")
            return
        v = tk.Toplevel(self.root); v.title("📜 Mis partidas")
        v.geometry("520x420"); v.configure(bg="#1a0a2e")
        tk.Label(v, text="📜 Tus partidas guardadas", bg="#1a0a2e", fg="#fbbf24",
                 font=("Segoe UI", 13, "bold")).pack(pady=10)
        for fname, d in partidas:
            f = tk.Frame(v, bg="#2d1b4e", pady=6, padx=10)
            f.pack(fill="x", padx=10, pady=2)
            tk.Label(f, text=f"{d['genero']} - {d['personaje']['nombre']}",
                     bg="#2d1b4e", fg="#fbbf24",
                     font=("Segoe UI", 10, "bold"), anchor="w"
                     ).pack(fill="x")
            tk.Label(f, text=f"📅 {d['fecha'][:13]} · {len(d['historial'])//2} turnos",
                     bg="#2d1b4e", fg="#e9d5ff", font=("Segoe UI", 8),
                     anchor="w").pack(fill="x")
            def cargar(d=d):
                self.genero = d["genero"]
                self.personaje = d["personaje"]
                self.historial = d["historial"]
                self.system_prompt = d.get("system_prompt", "")
                self.partida_id = d["fecha"]
                v.destroy()
                self._pantalla_juego()
                # Re-pintar historial
                for m in self.historial:
                    if m["role"] == "user":
                        self._agregar(f"⚔️ {self.personaje['nombre']}", m["content"], "user")
                    else:
                        self._agregar("📜 EL MASTER", m["content"], "nova")
            tk.Button(f, text="▶ Continuar", command=cargar,
                      bg="#22c55e", fg="white", relief="flat",
                      cursor="hand2").pack(side="right")

    def _config(self):
        """Diálogo de config con detección automática de modelos."""
        cfg_actual = {
            "proveedor": self.proveedor,
            "modelo": self.modelo,
            "api_key": self.api_key,
            "api_keys": self.cfg.get("api_keys", {}),
        }
        colores = {'bg': '#1a0a2e', 'bg2': '#2d1b4e', 'fg': '#e9d5ff', 'accent': '#fbbf24', 'warn': '#fbbf24', 'ok': '#22c55e'}
        def on_save(nuevo):
            self.proveedor = nuevo["proveedor"]
            self.modelo = nuevo["modelo"]
            self.api_key = nuevo["api_key"]
            self.cfg["gm_proveedor"] = self.proveedor
            self.cfg["gm_modelo"] = self.modelo
            self.cfg["api_keys"] = nuevo["api_keys"]
            with open(CONFIG, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, indent=2)
        dialogo_config(self.root, cfg_actual, on_save,
                       titulo="⚙ Configuración Game Master", colores=colores)

def main(): NovaGameMaster().root.mainloop()
if __name__ == "__main__": main()
