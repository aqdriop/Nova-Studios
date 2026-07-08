"""
nova_ui.py - Sistema de disenio unificado para el ecosistema NOVA AI
======================================================================
Colores, fuentes, widgets y patrones consistentes en todos los modulos.

Uso:
    from nova_ui import THEME, NovaButton, NovaEntry, NovaCard, splash_screen
    THEME.aplicar(root)
    btn = NovaButton(parent, text="Hola", variante="primary")
"""
import tkinter as tk
from tkinter import ttk
import time, threading

# ============================================================
# TEMA: Paleta unificada NOVA
# ============================================================
class Theme:
    # Fondos (de mas oscuro a mas claro)
    bg      = "#050714"     # fondo raiz
    bg2     = "#0d1729"     # fondo secundario / tarjetas
    bg3     = "#1e293b"     # inputs, hover
    bg4     = "#334155"     # separadores, bordes

    # Textos
    fg      = "#f1f5f9"     # texto principal
    fg2     = "#94a3b8"     # texto secundario
    fg3     = "#64748b"     # texto tenue

    # Acentos (por proveedor / modulo)
    accent      = "#a78bfa"     # violeta (Jarvis, principal)
    accent2     = "#60a5fa"     # azul (info)
    accent3     = "#ec4899"     # rosa (Studio)
    accent4     = "#f59e0b"     # ambar (Office)
    accent5     = "#22c55e"     # verde (Coach, OK)
    accent6     = "#06b6d4"     # cyan (Orb)
    accent7     = "#fbbf24"     # amarillo (GM, warn)

    # Semanticos
    ok      = "#22c55e"
    warn    = "#fbbf24"
    err     = "#ef4444"
    info    = "#3b82f6"

    # Fuentes (fallback si no existe Segoe UI)
    font_family = "Segoe UI"
    font_family_mono = "Consolas"

    # Tamanios base
    size_h1 = 22
    size_h2 = 16
    size_h3 = 13
    size_body = 10
    size_small = 9

    # Radios / espacios
    padding = 12
    radius = 8

    @classmethod
    def font(cls, size=None, bold=False, italic=False, mono=False):
        family = cls.font_family_mono if mono else cls.font_family
        style = ""
        if bold: style += "bold "
        if italic: style += "italic"
        return (family, size or cls.size_body, style.strip() or "normal")

    @classmethod
    def h1(cls): return cls.font(cls.size_h1, bold=True)
    @classmethod
    def h2(cls): return cls.font(cls.size_h2, bold=True)
    @classmethod
    def h3(cls): return cls.font(cls.size_h3, bold=True)
    @classmethod
    def body(cls): return cls.font(cls.size_body)
    @classmethod
    def small(cls): return cls.font(cls.size_small)

    @classmethod
    def aplicar(cls, root):
        """Aplica el tema global a la ventana root."""
        root.configure(bg=cls.bg)
        # Estilo ttk (Notebook, Combobox, etc.)
        style = ttk.Style(root)
        try: style.theme_use("clam")
        except Exception: pass

        style.configure("TNotebook",
            background=cls.bg, borderwidth=0)
        style.configure("TNotebook.Tab",
            background=cls.bg2, foreground=cls.fg,
            padding=[18, 8], font=cls.font(cls.size_body, bold=True),
            borderwidth=0)
        style.map("TNotebook.Tab",
            background=[("selected", cls.accent)],
            foreground=[("selected", "white")])

        style.configure("TCombobox",
            fieldbackground=cls.bg3, background=cls.bg3,
            foreground=cls.fg, borderwidth=0, arrowcolor=cls.fg)
        style.map("TCombobox",
            fieldbackground=[("readonly", cls.bg3)],
            selectbackground=[("readonly", cls.accent)])

        # Estilo por defecto de scrollbar
        style.configure("Vertical.TScrollbar",
            background=cls.bg2, troughcolor=cls.bg,
            arrowcolor=cls.fg, borderwidth=0)


THEME = Theme  # alias corto


# ============================================================
# BOTONES
# ============================================================
class NovaButton(tk.Button):
    """Boton con estilo NOVA."""
    VARIANTES = {
        "primary":  (Theme.accent, "white"),
        "secondary":(Theme.bg3, Theme.fg),
        "success":  (Theme.ok, "white"),
        "warning":  (Theme.warn, Theme.bg),
        "danger":   (Theme.err, "white"),
        "info":     (Theme.info, "white"),
        "ghost":    (Theme.bg, Theme.fg),
    }

    def __init__(self, master, text="", command=None,
                 variante="primary", size="md", **kwargs):
        bg, fg = self.VARIANTES.get(variante, self.VARIANTES["primary"])
        # Tamanios
        pad = {"sm": (10, 3), "md": (14, 6), "lg": (20, 10)}.get(size, (14, 6))
        font_size = {"sm": 9, "md": 10, "lg": 11}.get(size, 10)

        super().__init__(master, text=text, command=command,
            bg=bg, fg=fg, activebackground=Theme.accent2,
            activeforeground="white", relief="flat", bd=0,
            cursor="hand2", padx=pad[0], pady=pad[1],
            font=Theme.font(font_size, bold=True), **kwargs)

        # Efecto hover
        self._bg_normal = bg
        self._bg_hover = self._darker(bg, 0.15) if variante != "ghost" else Theme.bg3
        self.bind("<Enter>", lambda e: self.configure(bg=self._bg_hover))
        self.bind("<Leave>", lambda e: self.configure(bg=self._bg_normal))

    @staticmethod
    def _darker(color, factor=0.15):
        """Devuelve una version mas oscura de un color hex."""
        try:
            c = color.lstrip("#")
            r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
            r = max(0, int(r * (1 + factor)))
            g = max(0, int(g * (1 + factor)))
            b = max(0, int(b * (1 + factor)))
            r, g, b = min(255, r), min(255, g), min(255, b)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return color


# ============================================================
# ENTRY (input de texto)
# ============================================================
class NovaEntry(tk.Entry):
    """Input con estilo NOVA."""
    def __init__(self, master, placeholder="", show=None, **kwargs):
        kwargs.setdefault("bg", Theme.bg3)
        kwargs.setdefault("fg", Theme.fg)
        kwargs.setdefault("insertbackground", Theme.fg)
        kwargs.setdefault("relief", "flat")
        kwargs.setdefault("bd", 0)
        kwargs.setdefault("font", Theme.font(Theme.size_body))
        super().__init__(master, show=show, **kwargs)
        self.configure(highlightthickness=1,
            highlightbackground=Theme.bg4,
            highlightcolor=Theme.accent)

        # Placeholder
        self._placeholder = placeholder
        self._show_original = show
        if placeholder:
            self._mostrar_placeholder()
            self.bind("<FocusIn>", self._on_focus_in)
            self.bind("<FocusOut>", self._on_focus_out)

    def _mostrar_placeholder(self):
        self.delete(0, "end")
        self.insert(0, self._placeholder)
        self.configure(fg=Theme.fg3, show="")
        self._con_placeholder = True

    def _on_focus_in(self, e):
        if getattr(self, "_con_placeholder", False):
            self.delete(0, "end")
            self.configure(fg=Theme.fg,
                show=self._show_original if self._show_original else "")
            self._con_placeholder = False

    def _on_focus_out(self, e):
        if not self.get():
            self._mostrar_placeholder()

    def value(self):
        """Devuelve el valor real (ignorando el placeholder)."""
        if getattr(self, "_con_placeholder", False):
            return ""
        return self.get()


# ============================================================
# TARJETA (card)
# ============================================================
class NovaCard(tk.Frame):
    """Tarjeta contenedora con borde de color opcional."""
    def __init__(self, master, titulo=None, color_borde=None, **kwargs):
        kwargs.setdefault("bg", Theme.bg2)
        super().__init__(master, **kwargs)
        if color_borde:
            self.configure(highlightthickness=2,
                highlightbackground=color_borde)
        if titulo:
            tk.Label(self, text=titulo,
                bg=Theme.bg2, fg=color_borde or Theme.accent,
                font=Theme.h3(), anchor="w"
                ).pack(fill="x", padx=14, pady=(12, 4))


# ============================================================
# LABEL H1/H2/H3
# ============================================================
class NovaLabel(tk.Label):
    def __init__(self, master, text="", nivel="body", color=None, **kwargs):
        font_map = {
            "h1": Theme.h1(), "h2": Theme.h2(), "h3": Theme.h3(),
            "body": Theme.body(), "small": Theme.small(),
        }
        kwargs.setdefault("bg", Theme.bg)
        kwargs.setdefault("fg", color or (Theme.accent if nivel in ("h1","h2") else Theme.fg))
        kwargs.setdefault("font", font_map.get(nivel, Theme.body()))
        super().__init__(master, text=text, **kwargs)


# ============================================================
# BADGE (etiqueta de estado)
# ============================================================
def NovaBadge(master, text, variante="info"):
    """Crea una etiqueta pequenia de estado."""
    colores = {
        "success": Theme.ok, "warning": Theme.warn,
        "danger": Theme.err, "info": Theme.info,
        "neutral": Theme.bg3,
    }
    bg = colores.get(variante, Theme.info)
    return tk.Label(master, text=f" {text} ",
        bg=bg, fg="white", font=Theme.font(8, bold=True),
        padx=6, pady=2)


# ============================================================
# VENTANA ESTANDAR NOVA (header + body + status bar)
# ============================================================
class NovaWindow:
    """
    Helper para construir ventanas con estructura NOVA estandar:
    - Header con logo, titulo, subtitulo y botones a la derecha
    - Body (donde metes tu contenido)
    - Status bar abajo con mensajes de estado

    Uso:
        win = NovaWindow(root, "NOVA Reader", "Resume libros con IA",
                         color_acento=Theme.accent3)
        win.add_header_button("Config", callback_config)
        win.add_header_button("Ayuda", callback_ayuda)
        # Anadir contenido al body:
        tk.Label(win.body, text="Hola").pack()
        win.status("Listo")
    """
    def __init__(self, root, titulo="NOVA", subtitulo="", color_acento=None,
                    logo_texto=None):
        self.root = root
        self.color = color_acento or Theme.accent
        Theme.aplicar(root)
        root.configure(bg=Theme.bg)

        # HEADER
        self.header = tk.Frame(root, bg=Theme.bg2, height=64)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)

        # Barra superior de color (identidad del modulo)
        tk.Frame(root, bg=self.color, height=3).pack(fill="x")

        # Logo + titulo a la izquierda
        left = tk.Frame(self.header, bg=Theme.bg2)
        left.pack(side="left", padx=18, pady=8)

        title_row = tk.Frame(left, bg=Theme.bg2)
        title_row.pack(anchor="w")
        if logo_texto:
            tk.Label(title_row, text=logo_texto,
                bg=Theme.bg2, fg=self.color,
                font=(Theme.font_family, 22)).pack(side="left", padx=(0, 8))

        tk.Label(title_row, text=titulo,
            bg=Theme.bg2, fg=self.color,
            font=(Theme.font_family, 16, "bold")
            ).pack(side="left")

        if subtitulo:
            tk.Label(left, text=subtitulo,
                bg=Theme.bg2, fg=Theme.fg2,
                font=(Theme.font_family, 9, "italic"),
                anchor="w").pack(anchor="w", pady=(1, 0))

        # Contenedor de botones a la derecha del header
        self.header_btns = tk.Frame(self.header, bg=Theme.bg2)
        self.header_btns.pack(side="right", padx=12)

        # BODY (el contenedor principal)
        self.body = tk.Frame(root, bg=Theme.bg)
        self.body.pack(fill="both", expand=True)

        # STATUS BAR
        self.status_bar = tk.Frame(root, bg=Theme.bg2, height=28)
        self.status_bar.pack(fill="x", side="bottom")
        self.status_bar.pack_propagate(False)

        self.status_lbl = tk.Label(self.status_bar, text="",
            bg=Theme.bg2, fg=Theme.fg2,
            font=Theme.small(), anchor="w", padx=12)
        self.status_lbl.pack(side="left", fill="x", expand=True)

        # Indicador NOVA a la derecha del status
        tk.Label(self.status_bar, text="NOVA AI",
            bg=Theme.bg2, fg=Theme.fg3,
            font=(Theme.font_family, 8), padx=12
            ).pack(side="right")

    def add_header_button(self, text, command, variante="secondary"):
        btn = NovaButton(self.header_btns, text=text, command=command,
                          variante=variante, size="sm")
        btn.pack(side="right", padx=3, pady=8)
        return btn

    def status(self, texto, tipo="info"):
        """Cambia el mensaje de status. tipo: info/ok/warn/err."""
        colores = {"info": Theme.fg2, "ok": Theme.ok,
                    "warn": Theme.warn, "err": Theme.err}
        self.status_lbl.configure(text=texto, fg=colores.get(tipo, Theme.fg2))
def splash_screen(nombre_modulo, subtitulo="", color_acento=None,
                    duracion_min=1.2, tareas=None):
    """
    Muestra una splash screen mientras se cargan cosas.
    Uso:
        def cargar():
            # tareas lentas...
        splash_screen("NOVA Jarvis", "Asistente todopoderoso",
                      tareas=[("Cargando memoria", cargar), ...])
    """
    color = color_acento or Theme.accent

    splash = tk.Tk()
    splash.overrideredirect(True)  # Sin borde
    W, H = 460, 260
    x = (splash.winfo_screenwidth() - W) // 2
    y = (splash.winfo_screenheight() - H) // 2
    splash.geometry(f"{W}x{H}+{x}+{y}")
    splash.configure(bg=Theme.bg)
    splash.attributes("-topmost", True)

    # Borde de color
    borde = tk.Frame(splash, bg=color, height=4)
    borde.pack(fill="x")

    # Logo grande
    canvas = tk.Canvas(splash, bg=Theme.bg, highlightthickness=0,
                        width=W, height=100)
    canvas.pack(pady=(20, 10))

    # Circulo animado
    circle = canvas.create_oval(W//2 - 30, 20, W//2 + 30, 80,
        fill=color, outline="")
    inner = canvas.create_oval(W//2 - 15, 35, W//2 + 15, 65,
        fill="white", outline="")

    # Titulo
    tk.Label(splash, text=nombre_modulo,
        bg=Theme.bg, fg=color,
        font=(Theme.font_family, 20, "bold")
        ).pack()

    if subtitulo:
        tk.Label(splash, text=subtitulo,
            bg=Theme.bg, fg=Theme.fg2,
            font=(Theme.font_family, 10, "italic")).pack(pady=2)

    # Barra de progreso
    prog_bg = tk.Frame(splash, bg=Theme.bg3, height=4)
    prog_bg.pack(fill="x", padx=40, pady=(20, 8))
    prog_fill = tk.Frame(prog_bg, bg=color, height=4)
    prog_fill.place(x=0, y=0, relheight=1, relwidth=0)

    # Label estado
    lbl_estado = tk.Label(splash, text="Iniciando...",
        bg=Theme.bg, fg=Theme.fg2,
        font=(Theme.font_family, 9))
    lbl_estado.pack()

    tk.Label(splash, text="Parte del ecosistema NOVA AI",
        bg=Theme.bg, fg=Theme.fg3,
        font=(Theme.font_family, 8)).pack(side="bottom", pady=6)

    # Animacion del circulo
    fase = [0]
    def animar():
        fase[0] += 1
        r = 30 + int(4 * abs((fase[0] % 30) - 15) / 15)
        canvas.coords(circle, W//2 - r, 50 - r, W//2 + r, 50 + r)
        r2 = 15 + int(2 * abs((fase[0] % 30) - 15) / 15)
        canvas.coords(inner, W//2 - r2, 50 - r2, W//2 + r2, 50 + r2)
        splash.after(40, animar)
    animar()

    # Ejecutar tareas
    def ejecutar():
        tiempo_ini = time.time()
        total = max(1, len(tareas) if tareas else 1)
        for i, (nombre, fn) in enumerate(tareas or []):
            splash.after(0, lambda n=nombre: lbl_estado.configure(text=n))
            pct = (i + 1) / total
            splash.after(0, lambda p=pct: prog_fill.place(
                x=0, y=0, relheight=1, relwidth=p))
            try:
                if fn: fn()
            except Exception as e:
                print(f"Error en tarea '{nombre}': {e}")
            time.sleep(0.15)
        # Duracion minima para que se vea el splash
        elapsed = time.time() - tiempo_ini
        if elapsed < duracion_min:
            time.sleep(duracion_min - elapsed)
        splash.after(0, splash.destroy)

    threading.Thread(target=ejecutar, daemon=True).start()
    splash.mainloop()


# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    def demo():
        root = tk.Tk()
        root.title("NOVA UI - Demo componentes")
        root.geometry("800x600")
        THEME.aplicar(root)

        # Header
        header = tk.Frame(root, bg=Theme.bg2, height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        NovaLabel(header, "NOVA UI Kit", nivel="h1",
                   ).configure(bg=Theme.bg2)
        NovaLabel(header, "Componentes reutilizables", nivel="small",
                   color=Theme.fg2).configure(bg=Theme.bg2)

        for w in header.winfo_children():
            w.pack(side="left", padx=14, pady=10)

        # Body
        body = tk.Frame(root, bg=Theme.bg)
        body.pack(fill="both", expand=True, padx=20, pady=20)

        # Botones
        NovaLabel(body, "Botones:", nivel="h3").pack(anchor="w", pady=(0, 6))
        btns = tk.Frame(body, bg=Theme.bg)
        btns.pack(fill="x", pady=(0, 20))
        for v in ["primary", "secondary", "success", "warning", "danger", "info"]:
            NovaButton(btns, text=v, variante=v).pack(side="left", padx=4)

        # Entry
        NovaLabel(body, "Entry con placeholder:", nivel="h3").pack(anchor="w", pady=(0, 6))
        NovaEntry(body, placeholder="Escribe algo aqui...").pack(
            fill="x", ipady=8, pady=(0, 20))

        # Cards
        NovaLabel(body, "Tarjetas:", nivel="h3").pack(anchor="w", pady=(0, 6))
        cards_frame = tk.Frame(body, bg=Theme.bg)
        cards_frame.pack(fill="x", pady=(0, 20))

        for i, (t, c) in enumerate([
            ("Jarvis", Theme.accent), ("Studio", Theme.accent3),
            ("Coach", Theme.accent5), ("Office", Theme.accent4),
        ]):
            card = NovaCard(cards_frame, titulo=t, color_borde=c)
            card.pack(side="left", padx=6, fill="both", expand=True)
            tk.Label(card, text=f"Modulo {t}",
                bg=Theme.bg2, fg=Theme.fg,
                font=Theme.body()).pack(pady=12)

        # Badges
        NovaLabel(body, "Badges:", nivel="h3").pack(anchor="w", pady=(0, 6))
        bf = tk.Frame(body, bg=Theme.bg)
        bf.pack(fill="x")
        for t, v in [("ACTIVO", "success"), ("WARNING", "warning"),
                       ("ERROR", "danger"), ("INFO", "info"),
                       ("BETA", "neutral")]:
            NovaBadge(bf, t, v).pack(side="left", padx=4)

        root.mainloop()

    # Descomentar para ver splash
    # splash_screen("NOVA Jarvis", "Cargando poderes...",
    #                tareas=[("Cargando IA", lambda: time.sleep(0.5)),
    #                        ("Cargando memoria", lambda: time.sleep(0.3)),
    #                        ("Listo!", None)])
    demo()
