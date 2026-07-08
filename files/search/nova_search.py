"""
🔍 NOVA SEARCH — Busca en TUS archivos con lenguaje natural
============================================================
- Indexa carpetas de tu PC (textos, PDFs, código...)
- Búsqueda por palabras O por significado (con IA)
- Vista previa del contenido
- Pregunta a la IA sobre los resultados
- Filtros: por tipo, fecha, tamaño
"""
import os, sys, json, re, threading, urllib.request
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# VERSION (para el sistema de actualizaciones)
# ============================================================
VERSION = "1.0.0"
MODULO_ID = "search"

PARENT = os.path.dirname(APP_DIR)
CONFIG = os.path.join(PARENT, "config.json")
INDEX_FILE = os.path.join(APP_DIR, "index.json")

EXTENSIONES_TEXTO = {".txt",".md",".py",".js",".html",".css",".json",".xml",
                       ".csv",".log",".ini",".cfg",".yaml",".yml",".sh",".bat",
                       ".java",".c",".cpp",".cs",".go",".rs",".rb",".php",".sql",
                       ".ts",".tsx",".jsx",".vue",".swift",".kt",".srt"}


# Importar librería compartida de IA
sys.path.insert(0, APP_DIR)
from nova_ia_lib import llamar_llm, dialogo_config, listar_modelos

def cargar_cfg():
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return {}

def cargar_index():
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return {"carpetas": [], "archivos": []}

def guardar_index(idx):
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(idx, f, indent=2)

class NovaSearch:
    def __init__(self):
        self.cfg = cargar_cfg()
        self.index = cargar_index()
        self.proveedor = self.cfg.get("search_proveedor", "Gemini")
        self.modelo = self.cfg.get("search_modelo", "gemini-2.5-flash")
        self.api_key = self.cfg.get("api_keys", {}).get(self.proveedor, "")
        self.resultados_actuales = []

        self.root = tk.Tk()
        self.root.title("🔍 NOVA Search")
        self.root.geometry("1000x720")
        self.root.configure(bg="#0f172a")
        self._build()

    def _build(self):
        top = tk.Frame(self.root, bg="#020617", height=50)
        top.pack(fill="x"); top.pack_propagate(False)
        tk.Label(top, text="🔍  NOVA Search", bg="#020617", fg="#60a5fa",
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=14, pady=8)
        tk.Button(top, text="📁 Indexar carpeta", command=self._indexar_carpeta,
                  bg="#1e40af", fg="white", relief="flat", padx=12, pady=4,
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="right", padx=4, pady=10)
        tk.Button(top, text="⚙ Config", command=self._config,
                  bg="#334155", fg="white", relief="flat", padx=10, pady=4,
                  cursor="hand2").pack(side="right", padx=4, pady=10)

        # Estado
        self.lbl_estado = tk.Label(self.root, text="",
                                    bg="#0f172a", fg="#94a3b8",
                                    font=("Segoe UI", 9, "italic"))
        self.lbl_estado.pack(pady=4)
        self._actualizar_estado()

        # Búsqueda
        sf = tk.Frame(self.root, bg="#0f172a"); sf.pack(fill="x", padx=14, pady=8)
        self.entrada = tk.Entry(sf, bg="#1e293b", fg="white", relief="flat",
                                 font=("Segoe UI", 12), insertbackground="white")
        self.entrada.pack(side="left", fill="x", expand=True, ipady=10, padx=(0,6))
        self.entrada.bind("<Return>", lambda e: self._buscar())
        tk.Button(sf, text="🔍 Buscar", command=self._buscar,
                  bg="#3b82f6", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=18, cursor="hand2").pack(side="left")

        # Opciones
        of = tk.Frame(self.root, bg="#0f172a"); of.pack(fill="x", padx=14)
        self.modo_var = tk.StringVar(value="texto")
        tk.Radiobutton(of, text="📝 Búsqueda exacta (rápida)",
                       variable=self.modo_var, value="texto",
                       bg="#0f172a", fg="white", selectcolor="#1e293b",
                       activebackground="#0f172a", font=("Segoe UI", 9),
                       cursor="hand2").pack(side="left", padx=4)
        tk.Radiobutton(of, text="🧠 Búsqueda con IA (semántica)",
                       variable=self.modo_var, value="ia",
                       bg="#0f172a", fg="white", selectcolor="#1e293b",
                       activebackground="#0f172a", font=("Segoe UI", 9),
                       cursor="hand2").pack(side="left", padx=4)

        # Resultados
        rf = tk.Frame(self.root, bg="#0f172a")
        rf.pack(fill="both", expand=True, padx=14, pady=8)
        # Lista izq
        lf = tk.Frame(rf, bg="#1e293b", width=350)
        lf.pack(side="left", fill="y", padx=(0,4))
        lf.pack_propagate(False)
        tk.Label(lf, text="📋 Resultados", bg="#1e293b", fg="#60a5fa",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8, pady=4)
        self.lista = tk.Listbox(lf, bg="#0f172a", fg="white",
                                 selectbackground="#3b82f6", relief="flat",
                                 font=("Segoe UI", 9))
        self.lista.pack(fill="both", expand=True, padx=4, pady=4)
        self.lista.bind("<<ListboxSelect>>", self._mostrar_resultado)

        # Vista previa der
        rf2 = tk.Frame(rf, bg="#1e293b")
        rf2.pack(side="left", fill="both", expand=True, padx=(4,0))
        tk.Label(rf2, text="📄 Vista previa", bg="#1e293b", fg="#60a5fa",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8, pady=4)
        self.preview = scrolledtext.ScrolledText(rf2, bg="#0f172a", fg="#e2e8f0",
            font=("Consolas", 9), relief="flat", state="disabled", wrap="word")
        self.preview.pack(fill="both", expand=True, padx=4, pady=4)
        self.preview.tag_config("match", background="#fbbf24", foreground="black")
        self.preview.tag_config("info", foreground="#60a5fa")

        bf = tk.Frame(rf2, bg="#1e293b"); bf.pack(fill="x", padx=4, pady=4)
        tk.Button(bf, text="📂 Abrir archivo", command=self._abrir_archivo,
                  bg="#22c55e", fg="white", relief="flat", padx=10, pady=4,
                  cursor="hand2").pack(side="left", padx=2)
        tk.Button(bf, text="🧠 Preguntar a la IA",
                  command=self._preguntar_ia, bg="#a855f7", fg="white",
                  relief="flat", padx=10, pady=4, cursor="hand2"
                  ).pack(side="left", padx=2)

    def _actualizar_estado(self):
        c = len(self.index.get("carpetas", []))
        a = len(self.index.get("archivos", []))
        self.lbl_estado.config(text=f"📚 {c} carpetas indexadas · {a} archivos en el índice")

    def _indexar_carpeta(self):
        carpeta = filedialog.askdirectory(title="Selecciona una carpeta a indexar")
        if not carpeta: return
        if carpeta in self.index["carpetas"]:
            if not messagebox.askyesno("Ya indexada",
                "Esta carpeta ya está indexada. ¿Re-indexar?"):
                return
        else:
            self.index["carpetas"].append(carpeta)

        # Borrar archivos anteriores de esa carpeta
        self.index["archivos"] = [a for a in self.index["archivos"]
                                    if not a["ruta"].startswith(carpeta)]

        self._actualizar_estado()
        self.lbl_estado.config(text="⏳ Indexando, espera...", fg="#fbbf24")

        def tarea():
            contador = 0
            for root, dirs, files in os.walk(carpeta):
                # Saltar carpetas ocultas y de sistema
                dirs[:] = [d for d in dirs if not d.startswith(".")
                            and d not in {"node_modules", "__pycache__", ".git", "venv"}]
                for f in files:
                    ruta = os.path.join(root, f)
                    ext = os.path.splitext(f)[1].lower()
                    if ext not in EXTENSIONES_TEXTO: continue
                    try:
                        size = os.path.getsize(ruta)
                        if size > 2_000_000: continue  # >2MB skip
                        with open(ruta, "r", encoding="utf-8", errors="ignore") as fh:
                            contenido = fh.read()
                        self.index["archivos"].append({
                            "ruta": ruta,
                            "nombre": f,
                            "ext": ext,
                            "size": size,
                            "fecha": os.path.getmtime(ruta),
                            "contenido": contenido[:30000],  # primer 30k chars
                        })
                        contador += 1
                        if contador % 100 == 0:
                            self.root.after(0, lambda c=contador:
                                self.lbl_estado.config(
                                    text=f"⏳ Indexando... {c} archivos", fg="#fbbf24"))
                    except Exception:
                        continue
            guardar_index(self.index)
            self.root.after(0, lambda: self.lbl_estado.config(
                text=f"✅ Indexado: {contador} archivos nuevos. Total: {len(self.index['archivos'])}",
                fg="#22c55e"))
            self.root.after(0, self._actualizar_estado)
        threading.Thread(target=tarea, daemon=True).start()

    def _buscar(self):
        q = self.entrada.get().strip()
        if not q: return
        if not self.index["archivos"]:
            messagebox.showwarning("Sin índice", "Indexa una carpeta primero")
            return
        self.lista.delete(0, "end")
        self.resultados_actuales = []

        if self.modo_var.get() == "texto":
            self._buscar_texto(q)
        else:
            self._buscar_ia(q)

    def _buscar_texto(self, q):
        q_low = q.lower()
        palabras = q_low.split()
        resultados = []
        for archivo in self.index["archivos"]:
            score = 0
            content_low = archivo["contenido"].lower()
            name_low = archivo["nombre"].lower()
            # Score por nombre (peso alto)
            for p in palabras:
                if p in name_low: score += 10
                score += content_low.count(p)
            if score > 0:
                resultados.append((score, archivo))
        resultados.sort(reverse=True, key=lambda x: x[0])
        for score, a in resultados[:100]:
            self.resultados_actuales.append(a)
            preview = f"[{score}] {a['nombre']}  ({a['ruta'][-50:]})"
            self.lista.insert("end", preview)
        if not resultados:
            self.lista.insert("end", "(sin resultados)")

    def _buscar_ia(self, q):
        if not self.api_key and self.proveedor != "Ollama":
            messagebox.showwarning("Sin API", "Configura una IA en ⚙ Config")
            return
        # Primero filtro por texto, luego IA puntúa
        self._buscar_texto(q)
        if not self.resultados_actuales: return
        top20 = self.resultados_actuales[:20]
        self.lbl_estado.config(text=f"🧠 Re-clasificando con IA...", fg="#a855f7")

        def tarea():
            # Pedir a la IA que ordene
            archivos_info = []
            for i, a in enumerate(top20):
                archivos_info.append(f"[{i}] {a['nombre']}: {a['contenido'][:200]}")
            prompt = (f"Búsqueda del usuario: {q}\n\n"
                      f"Archivos candidatos:\n" + "\n\n".join(archivos_info) +
                      f"\n\nDevuelve SOLO una lista de números (de los más relevantes a los menos), "
                      f"separados por coma. Ejemplo: 3,7,1,12")
            resp = self._llamar_llm("Eres un buscador inteligente.", prompt)
            if resp:
                try:
                    nums = [int(n.strip()) for n in re.findall(r"\d+", resp)
                            if int(n.strip()) < len(top20)]
                    nuevos = [top20[n] for n in nums]
                    # Re-poblar lista
                    self.root.after(0, lambda: self.lista.delete(0, "end"))
                    self.resultados_actuales = nuevos
                    for a in nuevos:
                        self.root.after(0, lambda x=a: self.lista.insert("end",
                            f"🧠 {x['nombre']}  ({x['ruta'][-50:]})"))
                    self.root.after(0, lambda: self.lbl_estado.config(
                        text=f"✅ {len(nuevos)} resultados ordenados por IA", fg="#22c55e"))
                except: pass
        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_resultado(self, e):
        sel = self.lista.curselection()
        if not sel: return
        idx = sel[0]
        if idx >= len(self.resultados_actuales): return
        a = self.resultados_actuales[idx]
        self.preview.config(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("end", f"📄 {a['nombre']}\n", "info")
        self.preview.insert("end", f"📂 {a['ruta']}\n", "info")
        size_kb = a['size'] / 1024
        fecha = datetime.fromtimestamp(a['fecha']).strftime("%Y-%m-%d %H:%M")
        self.preview.insert("end", f"💾 {size_kb:.1f} KB · 📅 {fecha}\n\n", "info")
        self.preview.insert("end", "─" * 60 + "\n\n")
        self.preview.insert("end", a["contenido"][:5000])
        # Resaltar coincidencias
        q = self.entrada.get().lower()
        for palabra in q.split():
            if len(palabra) < 2: continue
            start = "1.0"
            while True:
                pos = self.preview.search(palabra, start, "end", nocase=True)
                if not pos: break
                end = f"{pos}+{len(palabra)}c"
                self.preview.tag_add("match", pos, end)
                start = end
        self.preview.config(state="disabled")

    def _abrir_archivo(self):
        sel = self.lista.curselection()
        if not sel: return
        a = self.resultados_actuales[sel[0]]
        try:
            if sys.platform.startswith("win"): os.startfile(a["ruta"])
        except Exception as e: messagebox.showerror("Error", str(e))

    def _preguntar_ia(self):
        sel = self.lista.curselection()
        if not sel:
            messagebox.showwarning("Selecciona", "Elige un resultado primero"); return
        a = self.resultados_actuales[sel[0]]
        pregunta = simpledialog.askstring("Pregunta a la IA",
            f"Pregunta sobre {a['nombre']}:", parent=self.root)
        if not pregunta: return
        def tarea():
            resp = self._llamar_llm(
                "Eres asistente experto. Responde basándote en el archivo.",
                f"ARCHIVO {a['nombre']}:\n{a['contenido'][:10000]}\n\nPREGUNTA: {pregunta}")
            self.root.after(0, lambda: self._mostrar_respuesta_ia(resp))
        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_respuesta_ia(self, resp):
        v = tk.Toplevel(self.root); v.title("🧠 Respuesta IA")
        v.geometry("600x400"); v.configure(bg="#0f172a")
        scrolledtext.ScrolledText(v, bg="#1e293b", fg="white",
            font=("Segoe UI", 10), wrap="word").pack(fill="both", expand=True,
            padx=10, pady=10)
        v.winfo_children()[0].insert("1.0", resp or "(sin respuesta)")

    def _llamar_llm(self, system, user):
        resp, err = llamar_llm(self.proveedor, self.modelo, self.api_key,
                                system, user)
        return resp if resp else f"❌ {err}"

    def _config(self):
        """Diálogo de config con detección automática de modelos."""
        cfg_actual = {
            "proveedor": self.proveedor,
            "modelo": self.modelo,
            "api_key": self.api_key,
            "api_keys": self.cfg.get("api_keys", {}),
        }
        colores = {'bg': '#0f172a', 'bg2': '#1e293b', 'fg': '#e2e8f0', 'accent': '#60a5fa', 'warn': '#fbbf24', 'ok': '#22c55e'}
        def on_save(nuevo):
            self.proveedor = nuevo["proveedor"]
            self.modelo = nuevo["modelo"]
            self.api_key = nuevo["api_key"]
            self.cfg["search_proveedor"] = self.proveedor
            self.cfg["search_modelo"] = self.modelo
            self.cfg["api_keys"] = nuevo["api_keys"]
            with open(CONFIG, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, indent=2)
        dialogo_config(self.root, cfg_actual, on_save,
                       titulo="⚙ Configuración Search", colores=colores)

def main(): NovaSearch().root.mainloop()
if __name__ == "__main__": main()
