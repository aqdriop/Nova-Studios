"""
NOVA TRANSLATOR - Traductor en tiempo real de la pantalla
==========================================================
Al abrirlo, detecta texto en tu pantalla (OCR) y lo traduce en vivo.

Dos modos:
  * OVERLAY AR: ventana transparente encima de todo, traducciones
    aparecen SOBRE el texto original (tipo Google Lens)
  * PANEL: ventana lateral con Original -> Traduccion

Motores:
  - OCR: Tesseract (via pytesseract) o EasyOCR (opcional)
  - Traduccion: IA (Groq/Gemini/OpenAI...) o Google Translate gratis

Hotkeys:
  F8      : traducir ahora (captura + OCR + traduccion)
  F9      : modo automatico ON/OFF (cada N segundos)
  F10     : cambiar modo (overlay <-> panel)
  ESC     : salir
"""
import os, sys, json, threading, time, re
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# VERSION (para el sistema de actualizaciones)
# ============================================================
VERSION = "1.0.0"
MODULO_ID = "translator"

PARENT = os.path.dirname(APP_DIR)
CONFIG = os.path.join(PARENT, "config.json")

# Importar libreria compartida
sys.path.insert(0, APP_DIR)
from nova_ia_lib import llamar_llm, dialogo_config

# ============================================================
# DEPENDENCIAS OPCIONALES
# ============================================================
try:
    from PIL import Image, ImageGrab, ImageEnhance, ImageFilter
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import pytesseract
    # En Windows a menudo hay que decirle donde esta tesseract
    if sys.platform == "win32":
        # Rutas comunes de instalacion Tesseract en Windows
        _rutas_tesseract = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
            os.path.expanduser(r"~\AppData\Local\Tesseract-OCR\tesseract.exe"),
            r"C:\Users\Public\Tesseract-OCR\tesseract.exe",
            r"D:\Program Files\Tesseract-OCR\tesseract.exe",
            r"E:\Program Files\Tesseract-OCR\tesseract.exe",
        ]
        # Tambien buscar en PATH
        import shutil
        tess_en_path = shutil.which("tesseract")
        if tess_en_path:
            _rutas_tesseract.insert(0, tess_en_path)

        for _ruta in _rutas_tesseract:
            if _ruta and os.path.exists(_ruta):
                pytesseract.pytesseract.tesseract_cmd = _ruta
                print(f"[Tesseract] Encontrado en: {_ruta}")
                break
        else:
            print("[Tesseract] NO encontrado en rutas comunes. Buscando en registro...")
    TESS_OK = True
    # Test rapido
    try:
        _tess_ver = pytesseract.get_tesseract_version()
        print(f"[Tesseract] Version: {_tess_ver}")
        TESS_OK = True
    except Exception as _e:
        print(f"[Tesseract] Error al detectar: {_e}")
        TESS_OK = False
except ImportError:
    TESS_OK = False
    print("[Tesseract] pytesseract no instalado")

try:
    import urllib.request, urllib.parse
    URL_OK = True
except ImportError:
    URL_OK = False

# ============================================================
# COLORES
# ============================================================
C = {
    "bg":      "#0d0d1a",
    "bg2":     "#1a1a2e",
    "bg3":     "#16213e",
    "fg":      "#eaeaea",
    "fg2":     "#94a3b8",
    "accent":  "#0f9ff3",   # cyan
    "accent2": "#00d4ff",
    "warn":    "#fbbf24",
    "err":     "#ef4444",
    "ok":      "#22c55e",
    "highlight": "#facc15",  # amarillo para las traducciones en overlay
}

# Idiomas soportados (codigo Tesseract + nombre)
IDIOMAS = {
    "es": "Espanol",
    "en": "Ingles",
    "fr": "Frances",
    "de": "Aleman",
    "it": "Italiano",
    "pt": "Portugues",
    "ja": "Japones",
    "ko": "Coreano",
    "zh-CN": "Chino",
    "ar": "Arabe",
    "ru": "Ruso",
    "hi": "Hindi",
    "nl": "Holandes",
    "sv": "Sueco",
    "pl": "Polaco",
    "tr": "Turco",
    "auto": "Auto-detectar",
}

# Mapping idioma nuestro -> codigo Tesseract OCR
TESS_LANG = {
    "es": "spa", "en": "eng", "fr": "fra", "de": "deu",
    "it": "ita", "pt": "por", "ja": "jpn", "ko": "kor",
    "zh-CN": "chi_sim", "ar": "ara", "ru": "rus", "hi": "hin",
    "nl": "nld", "sv": "swe", "pl": "pol", "tr": "tur",
    "auto": "eng+spa",  # combo por defecto
}

# Cache de traducciones persistente (entre sesiones)
CACHE_FILE = os.path.join(APP_DIR, "cache_traducciones.json")

# ============================================================
# TRADUCTOR VISIÓN - IA MULTIMODAL (¡infalible!)
# ============================================================
def traducir_por_vision(imagen_pil, proveedor, modelo, api_key,
                          idioma_destino_nombre="espanol",
                          idioma_origen="auto"):
    """
    Envía la captura de pantalla DIRECTAMENTE a la IA multimodal.
    La IA ve la imagen y devuelve el texto ya traducido.
    NO NECESITA OCR. Es mucho más fiable.

    Devuelve: (texto_completo_traducido, error)
    """
    if not api_key and proveedor != "Ollama":
        return "", "Sin API Key configurada"

    # Guardar temporalmente la imagen
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        # Reducir un poco para no gastar tokens de mas
        img = imagen_pil
        w, h = img.size
        if max(w, h) > 1920:
            ratio = 1920 / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)),
                              Image.LANCZOS)
        img.save(f.name, "PNG", optimize=True)
        ruta_temp = f.name

    origen_txt = ""
    if idioma_origen and idioma_origen != "auto":
        origen_txt = f"desde {idioma_origen} "

    system = (
        f"Eres un experto en traducir texto de imagenes.\n"
        f"Tu tarea:\n"
        f"1. Mira la captura de pantalla que te doy\n"
        f"2. Detecta TODO el texto legible que veas\n"
        f"3. Traduce cada linea {origen_txt}al {idioma_destino_nombre}\n\n"
        f"REGLAS ESTRICTAS:\n"
        f"- Devuelve el texto ORIGINAL y su TRADUCCION\n"
        f"- Formato: 'ORIGINAL → TRADUCCION' una linea por texto detectado\n"
        f"- NO expliques nada, NO uses markdown, NO anadas comentarios\n"
        f"- Si un texto ya esta en {idioma_destino_nombre}, ponlo igual: 'texto → texto'\n"
        f"- Nombres propios (marcas, ciudades) NO se traducen\n"
        f"- Ordena de arriba abajo, izquierda a derecha\n"
        f"- Si NO ves texto, devuelve: 'SIN TEXTO'"
    )
    user = "Detecta y traduce todos los textos que veas en esta imagen."

    try:
        resp, err = llamar_llm(proveedor, modelo, api_key,
                                system, user, timeout=60, imagen=ruta_temp)
        # Limpiar temp
        try: os.unlink(ruta_temp)
        except: pass

        if err:
            return "", err
        if "SIN TEXTO" in resp.upper()[:100]:
            return "", "La IA no vio texto en la pantalla"
        return resp, None
    except Exception as e:
        try: os.unlink(ruta_temp)
        except: pass
        return "", f"Error: {e}"


def parsear_traducciones_vision(respuesta):
    """
    Parsea la respuesta de la IA en formato 'ORIGINAL → TRADUCCION'.
    Devuelve lista de dicts: [{"original": ..., "traduccion": ...}, ...]
    """
    resultado = []
    # Separadores posibles: → -> => : - |
    for linea in respuesta.split("\n"):
        linea = linea.strip()
        if not linea:
            continue
        # Quitar viñetas, números iniciales
        linea = re.sub(r"^[\d\-\*•\.\)]+\s*", "", linea)

        # Probar separadores en orden de prioridad
        for sep in [" → ", " -> ", " => ", " | ", " :: "]:
            if sep in linea:
                partes = linea.split(sep, 1)
                if len(partes) == 2:
                    orig = partes[0].strip().strip('"\'')
                    trad = partes[1].strip().strip('"\'')
                    if orig and trad:
                        resultado.append({"original": orig, "traduccion": trad})
                        break
        else:
            # No hay separador claro: quizas la IA solo devolvio la traduccion
            if len(linea) > 3:
                resultado.append({"original": "", "traduccion": linea})
    return resultado


# Modelos IA con VISION (multimodales)
MODELOS_CON_VISION = {
    "Gemini": [
        "gemini-2.5-flash",       # ⚡ el mejor equilibrio (GRATIS)
        "gemini-2.5-pro",         # 🧠 el mas potente (GRATIS con limites)
        "gemini-2.0-flash",
        "gemini-flash-latest",
    ],
    "OpenAI": [
        "gpt-4o-mini",            # 💰 barato con vision
        "gpt-4o",                 # 🧠 mejor calidad
        "gpt-4.1-mini",
        "gpt-4.1",
    ],
    "Claude": [
        "claude-3-5-haiku-latest",  # ⚡ rapido con vision
        "claude-3-5-sonnet-latest",
        "claude-sonnet-4-5",
    ],
    "NVIDIA": [
        # NVIDIA tiene algunos modelos con vision, hay que buscar
        "meta/llama-3.2-90b-vision-instruct",
        "meta/llama-3.2-11b-vision-instruct",
    ],
    # Groq NO tiene modelos con vision actualmente
    # Ollama depende de los modelos instalados (llava, bakllava)
    "Ollama": [
        "llava", "llava:13b", "bakllava",
    ],
}


# ============================================================
# TRADUCTOR GOOGLE (gratis, sin API key)
# ============================================================
def traducir_google(texto, origen="auto", destino="es"):
    """Usa el endpoint publico gratuito de Google Translate."""
    try:
        url = ("https://translate.googleapis.com/translate_a/single"
               f"?client=gtx&sl={origen}&tl={destino}&dt=t"
               f"&q={urllib.parse.quote(texto)}")
        req = urllib.request.Request(url,
            headers={"User-Agent": "Mozilla/5.0 NovaTranslator/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        # data[0] contiene la lista de segmentos traducidos
        if data and data[0]:
            return " ".join(seg[0] for seg in data[0] if seg[0]), None
        return "", "Sin resultado"
    except Exception as e:
        return "", f"Error: {e}"


# ============================================================
# TRADUCTOR IA - BATCH OPTIMIZADO
# ============================================================
def traducir_ia_batch(textos, proveedor, modelo, api_key,
                        idioma_destino_nombre="espanol",
                        idioma_origen="auto"):
    """
    Traduce muchas frases en UNA sola llamada al LLM.
    Devuelve lista de traducciones en el mismo orden.
    """
    if not textos:
        return []
    if not api_key and proveedor != "Ollama":
        return [f"[Sin API key] {t}" for t in textos]

    # Filtrar vacios y numerar para no perder el orden
    indexados = [(i, t.strip()) for i, t in enumerate(textos) if t.strip()]
    if not indexados:
        return textos[:]

    # Construir prompt con numeracion
    bloque = "\n".join(f"[{i+1}] {t}" for i, (idx, t) in enumerate(indexados))

    origen_txt = ""
    if idioma_origen and idioma_origen != "auto":
        origen_txt = f"desde {idioma_origen} "

    system = (
        f"Eres un traductor experto. Traduce cada linea {origen_txt}al "
        f"{idioma_destino_nombre}. NO expliques nada, NO anadas notas.\n\n"
        f"Formato de respuesta OBLIGATORIO (mantener numeracion y saltos de linea):\n"
        f"[1] traduccion de la linea 1\n"
        f"[2] traduccion de la linea 2\n"
        f"...\n\n"
        f"Reglas:\n"
        f"- Manten el sentido natural, no traduzcas palabra por palabra\n"
        f"- Si una linea ya esta en {idioma_destino_nombre}, dejala IGUAL\n"
        f"- Si una linea es un nombre propio (marca, ciudad, persona), NO la traduzcas\n"
        f"- No repitas el texto original, SOLO la traduccion"
    )

    resp, err = llamar_llm(proveedor, modelo, api_key, system, bloque,
                            timeout=60, reintentos=2)
    if err:
        return [f"[Err: {err[:40]}] {t}" for t in textos]

    # Parsear respuesta linea por linea [N] traduccion
    traducciones_por_indice = {}
    for linea in resp.split("\n"):
        m = re.match(r"^\s*\[(\d+)\]\s*(.+)", linea.strip())
        if m:
            num = int(m.group(1)) - 1  # 1-indexed -> 0-indexed
            trad = m.group(2).strip()
            if 0 <= num < len(indexados):
                idx_original = indexados[num][0]
                traducciones_por_indice[idx_original] = trad

    # Construir salida en el orden original
    salida = []
    for i, t in enumerate(textos):
        if i in traducciones_por_indice:
            salida.append(traducciones_por_indice[i])
        elif not t.strip():
            salida.append(t)
        else:
            # Fallback si la IA no devolvio esa linea
            salida.append(f"[?] {t}")
    return salida


# ============================================================
# OCR con Tesseract (mejorado con multiples pasadas)
# ============================================================
def _preprocesar_variantes(img_pil, escala):
    """Devuelve varias versiones preprocesadas para probar OCR."""
    variantes = []

    # Escala de grises base
    gris = img_pil.convert("L")

    # V1: contraste fuerte
    v1 = ImageEnhance.Contrast(gris).enhance(2.0)
    v1 = ImageEnhance.Sharpness(v1).enhance(2.0)
    variantes.append(("normal", v1))

    # V2: invertida (para texto claro sobre fondo oscuro/color)
    from PIL import ImageOps
    v2 = ImageOps.invert(gris)
    v2 = ImageEnhance.Contrast(v2).enhance(2.0)
    variantes.append(("invertida", v2))

    # V3: binarizada (threshold) - mejor para texto sobre fondos color
    umbral = 128
    v3 = gris.point(lambda p: 255 if p > umbral else 0)
    variantes.append(("binaria", v3))

    # V4: binarizada invertida
    v4 = gris.point(lambda p: 0 if p > umbral else 255)
    variantes.append(("binaria_inv", v4))

    return variantes


def hacer_ocr(imagen_pil, idioma_ocr="eng+spa", con_boxes=True):
    """Devuelve texto detectado y (opcionalmente) posiciones.
    Prueba MULTIPLES variantes de preprocesado y se queda con la mejor."""
    if not TESS_OK:
        return "", []
    try:
        img = imagen_pil

        # 1) Aumentar resolucion si es pequenia (upscale 2x)
        w, h = img.size
        escala = 1.0
        if max(w, h) < 1400:
            img = img.resize((w * 2, h * 2), Image.LANCZOS)
            escala = 2.0

        # Probar 4 variantes de preprocesado
        variantes = _preprocesar_variantes(img, escala)

        mejores_boxes = []
        mejor_texto = ""
        mejor_nombre = "?"

        # Configs a probar (PSM 6 = bloque, PSM 11 = texto disperso)
        configs = [
            r'--oem 3 --psm 6',
            r'--oem 3 --psm 11',
        ]

        # Buscar la variante que produzca MAS texto valido
        for nombre, img_var in variantes:
            for config in configs:
                try:
                    boxes_variante = _extraer_boxes(img_var, idioma_ocr,
                                                       config, escala)
                    if len(boxes_variante) > len(mejores_boxes):
                        mejores_boxes = boxes_variante
                        mejor_texto = "\n".join(b["texto"] for b in boxes_variante)
                        mejor_nombre = f"{nombre}/{config[-6:]}"
                except Exception as e:
                    print(f"[OCR] Variante {nombre} fallo: {e}")

        print(f"[OCR] Mejor: {mejor_nombre} → {len(mejores_boxes)} lineas")

        # === DEDUPLICAR boxes que se solapan ===
        # Puede que diferentes preprocesados detecten el mismo texto
        # (ya no aplica porque nos quedamos con UNA sola variante)

        return mejor_texto, mejores_boxes
    except Exception as e:
        print(f"[OCR] Error: {e}")
        import traceback; traceback.print_exc()
        return "", []


def _extraer_boxes(img, idioma_ocr, config, escala):
    """Extrae boxes de una imagen ya preprocesada."""
    data = pytesseract.image_to_data(img, lang=idioma_ocr,
        config=config, output_type=pytesseract.Output.DICT)
    n = len(data["text"])

    # Agrupar por linea
    lineas = {}
    for i in range(n):
        txt = data["text"][i].strip()
        try:
            conf = int(float(data["conf"][i]))
        except (ValueError, TypeError):
            conf = 0
        # Confianza minima MENOS AGRESIVA (era 60, ahora 40)
        # Para no perder textos con fondos raros
        if not txt or conf < 40:
            continue
        # Filtrar strings claramente basura (solo simbolos)
        if len(re.sub(r'[^\w]', '', txt)) < 1:
            continue
        clave = (data["block_num"][i], data["par_num"][i],
                  data["line_num"][i])
        if clave not in lineas:
            lineas[clave] = {"palabras": [], "coords": []}
        lineas[clave]["palabras"].append(txt)
        lineas[clave]["coords"].append((
            int(data["left"][i] / escala),
            int(data["top"][i] / escala),
            int(data["width"][i] / escala),
            int(data["height"][i] / escala)))

    boxes = []
    for clave, info in lineas.items():
        if not info["coords"]:
            continue
        texto_linea = " ".join(info["palabras"])
        # Filtro final: eliminar lineas con demasiados caracteres raros
        total = len(texto_linea)
        alfanum = len(re.sub(r'[^\w\s]', '', texto_linea))
        # Ratio mas permisivo: >30% caracteres validos (antes 50%)
        if total > 0 and alfanum / total < 0.3:
            continue
        # Aceptar palabras de al menos 2 caracteres (antes 3)
        if len(texto_linea.strip()) < 2:
            continue
        xs = [c[0] for c in info["coords"]]
        ys = [c[1] for c in info["coords"]]
        x2s = [c[0] + c[2] for c in info["coords"]]
        y2s = [c[1] + c[3] for c in info["coords"]]
        boxes.append({
            "texto": texto_linea,
            "x": min(xs),
            "y": min(ys),
            "w": max(x2s) - min(xs),
            "h": max(y2s) - min(ys),
        })
    return boxes


def detectar_idiomas_disponibles_tesseract():
    """Devuelve la lista de codigos de idioma que Tesseract tiene instalados."""
    if not TESS_OK:
        return []
    try:
        return pytesseract.get_languages(config="")
    except Exception:
        return []


# ============================================================
# APP PRINCIPAL
# ============================================================
class NovaTranslator:
    MODOS = ("overlay", "panel")

    def __init__(self, root):
        self.root = root
        self.root.title("NOVA Translator")
        self.root.configure(bg=C["bg"])

        # Config
        self.cfg = self._cargar_cfg()
        self.proveedor = self.cfg.get("trans_proveedor", "Groq")
        self.modelo = self.cfg.get("trans_modelo", "llama-3.1-8b-instant")
        self.api_key = self.cfg.get("api_keys", {}).get(self.proveedor, "")
        self.motor_trad = self.cfg.get("trans_motor", "vision")  # "vision" | "google" | "ia"
        self.idioma_origen = self.cfg.get("trans_origen", "auto")
        self.idioma_destino = self.cfg.get("trans_destino", "es")
        self.modo = self.cfg.get("trans_modo", "overlay")
        self.intervalo = int(self.cfg.get("trans_intervalo", 3))
        self.transparencia = float(self.cfg.get("trans_alpha", 0.85))

        # Cargar ruta de Tesseract guardada por el usuario si la configuro manualmente
        tess_path_cfg = self.cfg.get("tesseract_path", "")
        if tess_path_cfg and os.path.exists(tess_path_cfg):
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = tess_path_cfg
                pytesseract.get_tesseract_version()  # test
                global TESS_OK
                TESS_OK = True
                print(f"[Tesseract] Usando ruta guardada: {tess_path_cfg}")
            except Exception as e:
                print(f"[Tesseract] Ruta guardada no funciona: {e}")

        self.automatico = False
        self.procesando = False
        self.overlay_window = None
        self.panel_window = None
        self.overlays_texto = []  # widgets creados en el overlay
        # Cache persistente entre sesiones
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                self.cache_traducciones = json.load(f)
                print(f"Cache cargada: {len(self.cache_traducciones)} traducciones")
        except Exception:
            self.cache_traducciones = {}
        self.ultima_captura = None

        self._build_control_panel()

        # Hotkeys globales (a nivel de la ventana; a nivel sistema requiere lib extra)
        self.root.bind_all("<F8>", lambda e: self.traducir_ahora())
        self.root.bind_all("<F9>", lambda e: self.toggle_automatico())
        self.root.bind_all("<F10>", lambda e: self.cambiar_modo())
        self.root.bind_all("<Escape>", lambda e: self.salir())

        # Abrir el modo por defecto
        self.root.after(500, self.aplicar_modo)

    # ---------- config ----------
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
            print(f"Config: {e}")

    def _actualizar_cfg(self):
        self.cfg["trans_proveedor"] = self.proveedor
        self.cfg["trans_modelo"] = self.modelo
        self.cfg["trans_motor"] = self.motor_trad
        self.cfg["trans_origen"] = self.idioma_origen
        self.cfg["trans_destino"] = self.idioma_destino
        self.cfg["trans_modo"] = self.modo
        self.cfg["trans_intervalo"] = self.intervalo
        self.cfg["trans_alpha"] = self.transparencia
        self._guardar_cfg()

    # ============================================================
    # PANEL DE CONTROL (ventana principal)
    # ============================================================
    def _build_control_panel(self):
        w, h = 420, 560
        sw = self.root.winfo_screenwidth()
        self.root.geometry(f"{w}x{h}+{sw - w - 20}+20")
        self.root.attributes("-topmost", True)

        # Header
        header = tk.Frame(self.root, bg=C["bg2"], height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="◆ NOVA Translator",
            bg=C["bg2"], fg=C["accent"],
            font=("Segoe UI", 16, "bold")).pack(side="left", padx=16, pady=14)
        tk.Label(header, text="Traduce tu pantalla",
            bg=C["bg2"], fg=C["fg2"],
            font=("Segoe UI", 9, "italic")).pack(side="left", pady=18)

        # Status principal
        self.status = tk.Label(self.root,
            text="Listo. Pulsa 'Traducir ahora' o F8",
            bg=C["bg"], fg=C["fg"],
            font=("Segoe UI", 10),
            wraplength=380, justify="center")
        self.status.pack(pady=(12, 6), fill="x", padx=16)

        # Info dependencias
        deps_frame = tk.Frame(self.root, bg=C["bg2"])
        deps_frame.pack(fill="x", padx=16, pady=6)
        self._deps_label = tk.Label(deps_frame, text=self._resumen_dependencias(),
            bg=C["bg2"], fg=C["fg2"],
            font=("Consolas", 9), justify="left",
            wraplength=380)
        self._deps_label.pack(anchor="w", padx=10, pady=(8, 4))

        # Botones de gestion Tesseract
        tess_btns = tk.Frame(deps_frame, bg=C["bg2"])
        tess_btns.pack(fill="x", padx=10, pady=(0, 8))
        tk.Button(tess_btns, text="🔧 Config Tesseract",
            command=self._configurar_tesseract_manual,
            bg=C["bg3"], fg=C["accent"], relief="flat",
            font=("Segoe UI", 8), cursor="hand2",
            padx=8, pady=3).pack(side="left", padx=2, fill="x", expand=True)
        tk.Button(tess_btns, text="🌐 Idiomas OCR",
            command=self._mostrar_idiomas_ocr,
            bg=C["bg3"], fg=C["accent"], relief="flat",
            font=("Segoe UI", 8), cursor="hand2",
            padx=8, pady=3).pack(side="left", padx=2, fill="x", expand=True)
        tk.Button(tess_btns, text="🔍 Test OCR",
            command=self._test_ocr,
            bg=C["bg3"], fg=C["accent"], relief="flat",
            font=("Segoe UI", 8), cursor="hand2",
            padx=8, pady=3).pack(side="left", padx=2, fill="x", expand=True)

        # --- Idiomas ---
        idiomas_frame = tk.Frame(self.root, bg=C["bg"])
        idiomas_frame.pack(fill="x", padx=16, pady=6)

        tk.Label(idiomas_frame, text="De:", bg=C["bg"], fg=C["fg2"],
            font=("Segoe UI", 10)).grid(row=0, column=0, padx=4, pady=4, sticky="w")
        self.origen_var = tk.StringVar(value=self.idioma_origen)
        origen_combo = ttk.Combobox(idiomas_frame, textvariable=self.origen_var,
            values=list(IDIOMAS.keys()), state="readonly", width=10,
            font=("Segoe UI", 9))
        origen_combo.grid(row=0, column=1, padx=4, pady=4)
        origen_combo.bind("<<ComboboxSelected>>",
            lambda e: setattr(self, "idioma_origen", self.origen_var.get()))

        tk.Label(idiomas_frame, text="→ A:",
            bg=C["bg"], fg=C["accent"],
            font=("Segoe UI", 11, "bold")).grid(row=0, column=2, padx=8)
        self.destino_var = tk.StringVar(value=self.idioma_destino)
        destino_combo = ttk.Combobox(idiomas_frame, textvariable=self.destino_var,
            values=[k for k in IDIOMAS.keys() if k != "auto"],
            state="readonly", width=10, font=("Segoe UI", 9))
        destino_combo.grid(row=0, column=3, padx=4, pady=4)
        destino_combo.bind("<<ComboboxSelected>>",
            lambda e: setattr(self, "idioma_destino", self.destino_var.get()))

        tk.Label(idiomas_frame, text="Cada:",
            bg=C["bg"], fg=C["fg2"],
            font=("Segoe UI", 10)).grid(row=1, column=0, padx=4, pady=4, sticky="w")
        self.intervalo_var = tk.IntVar(value=self.intervalo)
        tk.Spinbox(idiomas_frame, from_=1, to=30, textvariable=self.intervalo_var,
            width=4, bg=C["bg2"], fg=C["fg"], font=("Segoe UI", 10)
            ).grid(row=1, column=1, padx=4, pady=4, sticky="w")
        tk.Label(idiomas_frame, text="s (auto)",
            bg=C["bg"], fg=C["fg2"],
            font=("Segoe UI", 10)).grid(row=1, column=2, sticky="w")

        # --- Motor de traduccion (radios grandes) ---
        motor_box = tk.Frame(self.root, bg=C["bg2"], bd=2, relief="flat",
            highlightthickness=1, highlightbackground=C["bg3"])
        motor_box.pack(fill="x", padx=16, pady=6)

        tk.Label(motor_box, text="MOTOR DE TRADUCCION",
            bg=C["bg2"], fg=C["accent"],
            font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(8, 4))

        self.motor_var = tk.StringVar(value=self.motor_trad)
        motor_radios = tk.Frame(motor_box, bg=C["bg2"])
        motor_radios.pack(fill="x", padx=10, pady=(0, 4))

        tk.Radiobutton(motor_radios,
            text="👁️ VISION IA (¡infalible! IA ve la pantalla directamente)",
            variable=self.motor_var, value="vision",
            bg=C["bg2"], fg=C["accent"], selectcolor=C["bg3"],
            activebackground=C["bg2"], activeforeground=C["accent"],
            font=("Segoe UI", 9, "bold"),
            command=self._on_motor_change).pack(anchor="w", pady=1)

        tk.Radiobutton(motor_radios,
            text="🌐 Google Translate (rapido, gratis, requiere OCR)",
            variable=self.motor_var, value="google",
            bg=C["bg2"], fg=C["fg"], selectcolor=C["bg3"],
            activebackground=C["bg2"], activeforeground=C["accent"],
            font=("Segoe UI", 9),
            command=self._on_motor_change).pack(anchor="w", pady=1)

        tk.Radiobutton(motor_radios,
            text="🤖 IA + OCR (traduccion IA texto detectado por OCR)",
            variable=self.motor_var, value="ia",
            bg=C["bg2"], fg=C["fg"], selectcolor=C["bg3"],
            activebackground=C["bg2"], activeforeground=C["accent"],
            font=("Segoe UI", 9),
            command=self._on_motor_change).pack(anchor="w", pady=1)

        # Panel de IA (solo se muestra si se elige IA)
        self.ia_frame = tk.Frame(motor_box, bg=C["bg2"])
        self.ia_frame.pack(fill="x", padx=10, pady=(2, 8))

        ia_row = tk.Frame(self.ia_frame, bg=C["bg2"])
        ia_row.pack(fill="x")
        tk.Label(ia_row, text="Proveedor:",
            bg=C["bg2"], fg=C["fg2"],
            font=("Segoe UI", 9)).pack(side="left")
        self.prov_var = tk.StringVar(value=self.proveedor)
        prov_combo = ttk.Combobox(ia_row, textvariable=self.prov_var,
            values=["Gemini", "OpenAI", "Claude", "NVIDIA", "Groq", "Ollama"],
            state="readonly", width=10, font=("Segoe UI", 9))
        prov_combo.pack(side="left", padx=4)
        prov_combo.bind("<<ComboboxSelected>>", self._on_proveedor_change)

        tk.Button(ia_row, text="Config API Key",
            command=self._dialog_config,
            bg=C["bg3"], fg=C["fg"], relief="flat",
            font=("Segoe UI", 8), cursor="hand2",
            padx=8, pady=2).pack(side="left", padx=4)

        modelo_row = tk.Frame(self.ia_frame, bg=C["bg2"])
        modelo_row.pack(fill="x", pady=(4, 0))
        tk.Label(modelo_row, text="Modelo:",
            bg=C["bg2"], fg=C["fg2"],
            font=("Segoe UI", 9)).pack(side="left")
        self.modelo_var = tk.StringVar(value=self.modelo)
        self.modelo_combo = ttk.Combobox(modelo_row, textvariable=self.modelo_var,
            values=self._modelos_para(self.proveedor),
            state="normal", width=32, font=("Segoe UI", 9))
        self.modelo_combo.pack(side="left", padx=4, fill="x", expand=True)
        self.modelo_combo.bind("<<ComboboxSelected>>",
            lambda e: setattr(self, "modelo", self.modelo_var.get()))
        self.modelo_combo.bind("<FocusOut>",
            lambda e: setattr(self, "modelo", self.modelo_var.get()))

        # Info de estado del motor IA
        self.ia_status = tk.Label(self.ia_frame,
            text=self._info_ia_status(),
            bg=C["bg2"], fg=C["fg2"],
            font=("Segoe UI", 8, "italic"), justify="left", anchor="w",
            wraplength=360)
        self.ia_status.pack(fill="x", pady=(4, 0), anchor="w")

        # Ocultar frame IA si motor es google
        self._on_motor_change()

        # --- Modo ---
        modo_frame = tk.Frame(self.root, bg=C["bg"])
        modo_frame.pack(fill="x", padx=16, pady=4)
        tk.Label(modo_frame, text="Modo:",
            bg=C["bg"], fg=C["fg2"],
            font=("Segoe UI", 10)).pack(side="left", padx=4)
        self.modo_var = tk.StringVar(value=self.modo)
        tk.Radiobutton(modo_frame, text="OVERLAY (encima)",
            variable=self.modo_var, value="overlay",
            bg=C["bg"], fg=C["fg"], selectcolor=C["bg2"],
            activebackground=C["bg"], font=("Segoe UI", 9),
            command=self.aplicar_modo).pack(side="left", padx=6)
        tk.Radiobutton(modo_frame, text="PANEL (lateral)",
            variable=self.modo_var, value="panel",
            bg=C["bg"], fg=C["fg"], selectcolor=C["bg2"],
            activebackground=C["bg"], font=("Segoe UI", 9),
            command=self.aplicar_modo).pack(side="left", padx=6)

        # --- Transparencia ---
        alpha_frame = tk.Frame(self.root, bg=C["bg"])
        alpha_frame.pack(fill="x", padx=16, pady=4)
        tk.Label(alpha_frame, text="Transparencia overlay:",
            bg=C["bg"], fg=C["fg2"],
            font=("Segoe UI", 9)).pack(side="left", padx=4)
        self.alpha_var = tk.DoubleVar(value=self.transparencia)
        tk.Scale(alpha_frame, from_=0.5, to=1.0, resolution=0.05,
            orient="horizontal", variable=self.alpha_var,
            bg=C["bg2"], fg=C["fg"], troughcolor=C["bg3"],
            highlightthickness=0, sliderrelief="flat",
            command=self._cambiar_alpha).pack(side="left",
            fill="x", expand=True, padx=6)

        # --- Botones ---
        btns_frame = tk.Frame(self.root, bg=C["bg"])
        btns_frame.pack(fill="x", padx=16, pady=10)

        self.btn_traducir = tk.Button(btns_frame,
            text="TRADUCIR AHORA (F8)",
            command=self.traducir_ahora,
            bg=C["accent"], fg="white", relief="flat",
            font=("Segoe UI", 11, "bold"), cursor="hand2",
            pady=10)
        self.btn_traducir.pack(fill="x", pady=3)

        self.btn_auto = tk.Button(btns_frame,
            text="AUTOMATICO OFF (F9)",
            command=self.toggle_automatico,
            bg=C["bg3"], fg=C["fg"], relief="flat",
            font=("Segoe UI", 10, "bold"), cursor="hand2",
            pady=8)
        self.btn_auto.pack(fill="x", pady=3)

        tk.Button(btns_frame, text="Config IA (para motor 'ia')",
            command=self._dialog_config,
            bg=C["bg3"], fg=C["fg"], relief="flat",
            font=("Segoe UI", 9), cursor="hand2",
            pady=6).pack(fill="x", pady=3)

        tk.Button(btns_frame, text="SALIR (ESC)",
            command=self.salir,
            bg=C["err"], fg="white", relief="flat",
            font=("Segoe UI", 9), cursor="hand2",
            pady=6).pack(fill="x", pady=3)

        # --- Historial ---
        tk.Label(self.root, text="Traducciones recientes:",
            bg=C["bg"], fg=C["accent"],
            font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16, pady=(8, 2))
        self.hist_text = scrolledtext.ScrolledText(self.root,
            bg=C["bg2"], fg=C["fg"], font=("Segoe UI", 9),
            wrap="word", relief="flat", padx=8, pady=8, height=8)
        self.hist_text.pack(fill="both", expand=True, padx=16, pady=(0, 12))

    def _resumen_dependencias(self):
        s = "Estado:\n"
        s += f"  Pillow (captura): {'OK' if PIL_OK else 'FALTA (pip install Pillow)'}\n"
        # Verificar tesseract dinamicamente
        tess_estado = "OK"
        idiomas_tess = []
        try:
            import pytesseract
            v = pytesseract.get_tesseract_version()
            tess_estado = f"OK v{v}"
            idiomas_tess = detectar_idiomas_disponibles_tesseract()
        except Exception as e:
            tess_estado = f"NO DETECTADO ({type(e).__name__})"
        s += f"  Tesseract (OCR): {tess_estado}\n"
        if "OK" not in tess_estado:
            s += "    Pulsa 'Configurar Tesseract' abajo"
        else:
            # Mostrar idiomas instalados
            idiomas_utiles = [x for x in idiomas_tess if x != "osd"]
            if idiomas_utiles:
                s += f"  Idiomas OCR: {', '.join(idiomas_utiles[:8])}"
                if len(idiomas_utiles) > 8:
                    s += f" (+{len(idiomas_utiles)-8})"
                # Verificar si esta el idioma que necesita
                tess_lang_actual = TESS_LANG.get(self.idioma_origen, "eng")
                # Puede tener + (ej: eng+spa)
                idiomas_necesarios = tess_lang_actual.split("+")
                faltan = [l for l in idiomas_necesarios
                            if l not in idiomas_tess]
                if faltan:
                    s += f"\n  ⚠ FALTA: {', '.join(faltan)}"
                    s += f"\n    (necesario para OCR de {self.idioma_origen})"
        return s

    def _configurar_tesseract_manual(self):
        """Permite al usuario apuntar manualmente al tesseract.exe."""
        from tkinter import filedialog
        ruta = filedialog.askopenfilename(
            title="Selecciona tesseract.exe",
            initialdir=r"C:\Program Files\Tesseract-OCR",
            filetypes=[("Tesseract executable", "tesseract.exe"), ("Todo", "*.*")])
        if not ruta:
            return
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = ruta
            v = pytesseract.get_tesseract_version()
            # Actualizar la variable global
            global TESS_OK
            TESS_OK = True
            # Guardar en config para siguiente arranque
            self.cfg["tesseract_path"] = ruta
            self._guardar_cfg()
            messagebox.showinfo("Tesseract OK",
                f"Tesseract configurado correctamente:\n{ruta}\nVersion: {v}\n\n"
                "Ya puedes traducir con F8.")
            # Refrescar label de dependencias
            self._refrescar_deps()
        except Exception as e:
            messagebox.showerror("Error",
                f"El archivo no parece ser tesseract.exe valido:\n{e}\n\n"
                "Prueba con: C:\\Program Files\\Tesseract-OCR\\tesseract.exe")

    def _refrescar_deps(self):
        """Refresca el label de estado de dependencias."""
        try:
            if hasattr(self, "_deps_label"):
                self._deps_label.config(text=self._resumen_dependencias())
        except Exception:
            pass

    def _mostrar_idiomas_ocr(self):
        """Muestra los idiomas OCR instalados en Tesseract."""
        idiomas = detectar_idiomas_disponibles_tesseract()
        if not idiomas:
            messagebox.showerror("Sin Tesseract",
                "No se pudo consultar Tesseract. Configuralo primero.")
            return

        # Mapping inverso codigo tesseract -> nombre legible
        NOMBRES = {
            "spa": "Espanol", "eng": "Ingles", "fra": "Frances",
            "deu": "Aleman", "ita": "Italiano", "por": "Portugues",
            "jpn": "Japones", "kor": "Coreano", "chi_sim": "Chino simplificado",
            "chi_tra": "Chino tradicional", "ara": "Arabe", "rus": "Ruso",
            "hin": "Hindi", "nld": "Holandes", "swe": "Sueco",
            "pol": "Polaco", "tur": "Turco", "vie": "Vietnamita",
            "tha": "Tailandes", "heb": "Hebreo", "cat": "Catalan",
            "osd": "(orientacion, no traducible)",
        }

        # Idiomas que necesitas y NO tienes
        necesarios = set(TESS_LANG.values()) - {"auto"}
        necesarios_lista = set()
        for combo in necesarios:
            for l in combo.split("+"):
                necesarios_lista.add(l)

        instalados = set(idiomas)
        faltan = necesarios_lista - instalados

        msg = f"IDIOMAS OCR INSTALADOS ({len(idiomas)}):\n\n"
        for i in sorted(idiomas):
            nom = NOMBRES.get(i, i)
            emoji = "✓" if i != "osd" else "○"
            msg += f"  {emoji} {i} - {nom}\n"

        if faltan:
            msg += f"\n\nFALTAN idiomas utiles ({len(faltan)}):\n"
            for i in sorted(faltan):
                nom = NOMBRES.get(i, i)
                msg += f"  ✗ {i} - {nom}\n"
            msg += ("\nPara instalar mas idiomas:\n"
                    "1. Descarga .traineddata de:\n"
                    "   https://github.com/tesseract-ocr/tessdata_best\n"
                    "2. Copialos a:\n"
                    "   C:\\Program Files\\Tesseract-OCR\\tessdata\\\n"
                    "\nO reinstala Tesseract marcando MAS idiomas.")

        # Ventana con scroll
        dlg = tk.Toplevel(self.root)
        dlg.title("Idiomas OCR instalados")
        dlg.geometry("500x500")
        dlg.configure(bg=C["bg"])
        dlg.transient(self.root)

        tk.Label(dlg, text="🌐 Idiomas OCR de Tesseract",
            bg=C["bg"], fg=C["accent"],
            font=("Segoe UI", 13, "bold")).pack(pady=12)

        txt = scrolledtext.ScrolledText(dlg,
            bg=C["bg2"], fg=C["fg"],
            font=("Consolas", 10), wrap="word",
            relief="flat", padx=14, pady=14)
        txt.pack(fill="both", expand=True, padx=12, pady=8)
        txt.insert("1.0", msg)
        txt.config(state="disabled")

        tk.Button(dlg, text="Cerrar", command=dlg.destroy,
            bg=C["bg3"], fg=C["fg"], relief="flat",
            font=("Segoe UI", 10), padx=20, pady=6,
            cursor="hand2").pack(pady=10)

    def _test_ocr(self):
        """Hace un test de OCR y muestra qué detectó, para debug."""
        if not TESS_OK:
            messagebox.showwarning("Sin Tesseract",
                "Configura Tesseract primero")
            return

        # Ocultar ventana y capturar
        self._set_status("Test OCR en 2 seg...", C["warn"])
        try:
            self.root.attributes("-alpha", 0.0)
        except Exception: pass
        self.root.after(1500, self._test_ocr_capturar)

    def _test_ocr_capturar(self):
        try:
            img = ImageGrab.grab()
        except Exception as e:
            self._set_status(f"Error captura: {e}", C["err"])
            return
        try:
            self.root.attributes("-alpha", 1.0)
        except Exception: pass

        origen_ocr = TESS_LANG.get(self.idioma_origen, "eng+spa")
        if self.idioma_origen == "auto":
            origen_ocr = "eng+spa"

        # Verificar idiomas
        idiomas_inst = detectar_idiomas_disponibles_tesseract()
        para_usar = "+".join(l for l in origen_ocr.split("+")
                              if l in idiomas_inst)
        if not para_usar:
            para_usar = "eng" if "eng" in idiomas_inst else idiomas_inst[0]

        texto, boxes = hacer_ocr(img, idioma_ocr=para_usar, con_boxes=True)

        # Mostrar resultado en dialogo
        dlg = tk.Toplevel(self.root)
        dlg.title("Test OCR - Resultados")
        dlg.geometry("700x600")
        dlg.configure(bg=C["bg"])
        dlg.transient(self.root)

        tk.Label(dlg, text="🔍 Test de OCR",
            bg=C["bg"], fg=C["accent"],
            font=("Segoe UI", 13, "bold")).pack(pady=8)

        info = (f"Idioma OCR usado: {para_usar}\n"
                f"Lineas detectadas: {len(boxes)}\n"
                f"Total caracteres: {len(texto)}")
        tk.Label(dlg, text=info, bg=C["bg"], fg=C["fg2"],
            font=("Segoe UI", 9), justify="left"
            ).pack(anchor="w", padx=14)

        txt = scrolledtext.ScrolledText(dlg,
            bg=C["bg2"], fg=C["fg"],
            font=("Consolas", 10), wrap="word",
            relief="flat", padx=14, pady=14)
        txt.pack(fill="both", expand=True, padx=12, pady=8)

        if boxes:
            for i, b in enumerate(boxes, 1):
                txt.insert("end",
                    f"[{i}] ({b['x']},{b['y']}) {b['w']}x{b['h']}\n")
                txt.insert("end", f"    {b['texto']}\n\n")
        else:
            txt.insert("end", "SIN CAJAS DETECTADAS.\n\n")

        txt.insert("end", "\n=== TEXTO PLANO COMPLETO ===\n")
        txt.insert("end", texto[:2000] if texto else "(vacio)")
        txt.config(state="disabled")

        # Estado
        if boxes:
            self._set_status(f"Test OK: {len(boxes)} lineas detectadas",
                C["ok"])
        else:
            self._set_status("Test: SIN texto detectado", C["warn"])

        tk.Button(dlg, text="Cerrar", command=dlg.destroy,
            bg=C["bg3"], fg=C["fg"], relief="flat",
            font=("Segoe UI", 10), padx=20, pady=6,
            cursor="hand2").pack(pady=10)

    # ============================================================
    # HELPERS DEL PANEL DE MOTOR
    # ============================================================
    def _modelos_para(self, proveedor):
        """Modelos recomendados para traduccion (rapidos y buenos)."""
        MODELOS = {
            "Groq": [
                "llama-3.1-8b-instant",           # el mas rapido, ideal traduccion
                "llama-3.3-70b-versatile",
                "meta-llama/llama-4-scout-17b-16e-instruct",
                "openai/gpt-oss-20b",
                "moonshotai/kimi-k2-instruct",
            ],
            "Gemini": [
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-flash-latest",
                "gemini-2.5-pro",
            ],
            "OpenAI": [
                "gpt-4o-mini",
                "gpt-4.1-mini",
                "gpt-4o",
                "gpt-3.5-turbo",
            ],
            "NVIDIA": [
                "meta/llama-3.1-8b-instruct",
                "meta/llama-3.3-70b-instruct",
                "nvidia/llama-3.1-nemotron-70b-instruct",
                "qwen/qwen2.5-72b-instruct",
            ],
            "Claude": [
                "claude-3-5-haiku-latest",  # el mas rapido
                "claude-3-5-sonnet-latest",
                "claude-sonnet-4-5",
            ],
            "Ollama": [
                "llama3.2", "llama3.1", "mistral", "qwen2.5",
            ],
        }
        return MODELOS.get(proveedor, [])

    def _info_ia_status(self):
        key = self.cfg.get("api_keys", {}).get(self.proveedor, "")
        if self.proveedor == "Ollama":
            return "Ollama: local, sin API key. Necesita Ollama corriendo."
        if key:
            return f"✓ API Key configurada para {self.proveedor} ({key[:6]}...{key[-4:]})"
        return f"⚠ Falta API Key. Pulsa 'Config API Key' para configurarla."

    def _on_motor_change(self):
        self.motor_trad = self.motor_var.get()
        # Mostrar/ocultar panel IA (tanto para 'ia' como 'vision')
        if self.motor_trad in ("ia", "vision"):
            self.ia_frame.pack(fill="x", padx=10, pady=(2, 8))
            # Si esta en vision, cambiar los modelos disponibles
            if self.motor_trad == "vision":
                self._refrescar_modelos_vision()
            else:
                self._refrescar_modelos_normal()
        else:
            self.ia_frame.pack_forget()
        # Refrescar etiqueta del overlay si esta abierto
        self._refrescar_etiqueta_overlay()
        self._actualizar_cfg()

    def _refrescar_modelos_vision(self):
        """Solo muestra modelos con capacidad de vision."""
        modelos = MODELOS_CON_VISION.get(self.proveedor, [])
        if not modelos:
            # Este proveedor no tiene modelos con vision
            self.modelo_combo["values"] = ["(este proveedor no tiene vision)"]
            self.modelo_var.set("(este proveedor no tiene vision)")
            self.ia_status.config(
                text=f"⚠ {self.proveedor} NO tiene modelos con vision.\n"
                      f"Prueba Gemini, OpenAI o Claude.",
                fg=C["warn"])
        else:
            self.modelo_combo["values"] = modelos
            if self.modelo not in modelos:
                self.modelo = modelos[0]
                self.modelo_var.set(self.modelo)
            self.ia_status.config(text=self._info_ia_status(),
                fg=C["fg2"])

    def _refrescar_modelos_normal(self):
        """Muestra modelos normales (no necesariamente con vision)."""
        modelos = self._modelos_para(self.proveedor)
        self.modelo_combo["values"] = modelos
        if self.modelo not in modelos and modelos:
            self.modelo = modelos[0]
            self.modelo_var.set(self.modelo)
        self.ia_status.config(text=self._info_ia_status(), fg=C["fg2"])

    def _refrescar_etiqueta_overlay(self):
        """Actualiza la etiqueta del overlay con el motor/idioma actual."""
        try:
            if hasattr(self, "mini_lbl_motor") and self.mini_lbl_motor.winfo_exists():
                if self.motor_trad == "vision":
                    motor_txt = f"👁️ Vision ({self.proveedor})"
                elif self.motor_trad == "google":
                    motor_txt = "🌐 Google"
                else:
                    motor_txt = f"🤖 {self.proveedor}"
                self.mini_lbl_motor.config(
                    text=f"◆ NOVA · {motor_txt} · {self.idioma_origen}→{self.idioma_destino}")
        except Exception:
            pass

    def _on_proveedor_change(self, evt=None):
        self.proveedor = self.prov_var.get()
        self.api_key = self.cfg.get("api_keys", {}).get(self.proveedor, "")
        # Refrescar modelos segun el modo actual
        if self.motor_trad == "vision":
            self._refrescar_modelos_vision()
        else:
            self._refrescar_modelos_normal()
        # Refrescar etiqueta overlay
        self._refrescar_etiqueta_overlay()
        self._actualizar_cfg()

    def _cambiar_alpha(self, val):
        self.transparencia = float(val)
        if self.overlay_window:
            try:
                self.overlay_window.attributes("-alpha", self.transparencia)
            except Exception: pass

    def _dialog_config(self):
        cfg = {"proveedor": self.proveedor, "modelo": self.modelo,
               "api_key": self.api_key, "api_keys": self.cfg.get("api_keys", {})}
        col = {"bg": C["bg"], "bg2": C["bg2"], "fg": C["fg"],
               "accent": C["accent"], "warn": C["warn"], "ok": C["ok"]}
        def on_save(n):
            self.proveedor = n["proveedor"]; self.modelo = n["modelo"]
            self.api_key = n["api_key"]
            self.cfg["api_keys"] = n["api_keys"]
            # Refrescar el panel visual
            self.prov_var.set(self.proveedor)
            self.modelo_var.set(self.modelo)
            self.modelo_combo["values"] = self._modelos_para(self.proveedor)
            self.ia_status.config(text=self._info_ia_status())
            self._actualizar_cfg()
        dialogo_config(self.root, cfg, on_save,
            titulo="Config IA - Translator", colores=col)

    # ============================================================
    # OVERLAY - ventana transparente encima
    # ============================================================
    def aplicar_modo(self):
        self.modo = self.modo_var.get()
        # Cerrar ventanas existentes
        if self.overlay_window:
            try: self.overlay_window.destroy()
            except: pass
            self.overlay_window = None
        if self.panel_window:
            try: self.panel_window.destroy()
            except: pass
            self.panel_window = None

        if self.modo == "overlay":
            self._crear_overlay()
        else:
            self._crear_panel_lateral()

    def _crear_overlay(self):
        """Ventana transparente a pantalla completa, click-through."""
        self.overlay_window = tk.Toplevel(self.root)
        self.overlay_window.title("NOVA Translator - Overlay")
        # Pantalla completa
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.overlay_window.geometry(f"{sw}x{sh}+0+0")
        self.overlay_window.overrideredirect(True)  # sin borde
        self.overlay_window.attributes("-topmost", True)
        self.overlay_window.attributes("-alpha", self.transparencia)

        # En Windows, hacer transparente el fondo con color mágico
        # (ventana clickeable pero se ve la pantalla debajo excepto en widgets)
        try:
            self.overlay_window.attributes("-transparentcolor", "#010203")
            self.overlay_window.configure(bg="#010203")
        except Exception:
            # No Windows -> semi-transparencia general
            self.overlay_window.configure(bg=C["bg"])
            self.overlay_window.attributes("-alpha", 0.3)

        # Canvas para dibujar traducciones
        self.overlay_canvas = tk.Canvas(self.overlay_window,
            bg="#010203" if sys.platform == "win32" else C["bg"],
            highlightthickness=0)
        self.overlay_canvas.pack(fill="both", expand=True)

        # Mini barra flotante en la esquina para no perder control
        mini_bar = tk.Frame(self.overlay_window, bg=C["bg2"], bd=2, relief="raised")
        # Posicionar arriba-centro
        mini_bar.place(relx=0.5, y=8, anchor="n")
        if self.motor_trad == "vision":
            motor_txt = f"👁️ Vision ({self.proveedor})"
        elif self.motor_trad == "google":
            motor_txt = "🌐 Google"
        else:
            motor_txt = f"🤖 {self.proveedor}"
        self.mini_lbl_motor = tk.Label(mini_bar,
            text=f"◆ NOVA · {motor_txt} · {self.idioma_origen}→{self.idioma_destino}",
            bg=C["bg2"], fg=C["accent"],
            font=("Segoe UI", 9, "bold"))
        self.mini_lbl_motor.pack(side="left", padx=10, pady=4)
        tk.Button(mini_bar, text="Traducir (F8)",
            command=self.traducir_ahora,
            bg=C["accent"], fg="white", relief="flat",
            font=("Segoe UI", 8, "bold"), padx=8,
            cursor="hand2").pack(side="left", padx=4, pady=4)
        tk.Button(mini_bar, text="Cambiar motor",
            command=self._toggle_motor_rapido,
            bg=C["bg3"], fg=C["fg"], relief="flat",
            font=("Segoe UI", 8), padx=6,
            cursor="hand2").pack(side="left", padx=4, pady=4)
        tk.Button(mini_bar, text="Panel",
            command=self._volver_control,
            bg=C["bg3"], fg=C["fg"], relief="flat",
            font=("Segoe UI", 8), padx=6,
            cursor="hand2").pack(side="left", padx=4, pady=4)

        self.overlay_window.bind_all("<F8>", lambda e: self.traducir_ahora())
        self.overlay_window.bind_all("<F9>", lambda e: self.toggle_automatico())
        self.overlay_window.bind_all("<F10>", lambda e: self.cambiar_modo())
        self.overlay_window.bind_all("<Escape>", lambda e: self.salir())
        # Al hacer click en el overlay (en zona sin widgets), refrescar
        self.overlay_canvas.bind("<Double-Button-1>",
            lambda e: self.traducir_ahora())

    def _volver_control(self):
        """Muestra el panel de control (que puede estar detras)."""
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(200, lambda: self.root.attributes("-topmost", True))

    def _toggle_motor_rapido(self):
        """Cicla entre los 3 motores desde el overlay: vision → google → ia → vision"""
        ciclo = {"vision": "google", "google": "ia", "ia": "vision"}
        self.motor_trad = ciclo.get(self.motor_trad, "vision")
        self.motor_var.set(self.motor_trad)
        self._on_motor_change()  # esto ya refresca la etiqueta
        # Avisar al usuario
        if self.motor_trad == "vision":
            if not self.api_key and self.proveedor != "Ollama":
                self._set_status(
                    f"Motor: VISION ({self.proveedor}) - FALTA API KEY!",
                    C["warn"])
            else:
                self._set_status(
                    f"Motor: VISION ({self.proveedor} / {self.modelo})",
                    C["ok"])
        elif self.motor_trad == "ia":
            if not self.api_key and self.proveedor != "Ollama":
                self._set_status(
                    f"Motor: IA + OCR ({self.proveedor}) - FALTA API KEY!",
                    C["warn"])
            else:
                self._set_status(
                    f"Motor: IA + OCR ({self.proveedor} / {self.modelo})",
                    C["ok"])
        else:
            self._set_status("Motor: Google Translate (gratis)", C["ok"])

    def _crear_panel_lateral(self):
        """Ventana lateral con lista de Original -> Traduccion."""
        self.panel_window = tk.Toplevel(self.root)
        self.panel_window.title("NOVA Translator - Panel")
        w = 380
        sh = self.root.winfo_screenheight()
        self.panel_window.geometry(f"{w}x{sh - 100}+0+50")
        self.panel_window.attributes("-topmost", True)
        self.panel_window.configure(bg=C["bg"])

        tk.Label(self.panel_window, text="◆ Panel de traduccion",
            bg=C["bg2"], fg=C["accent"],
            font=("Segoe UI", 12, "bold")).pack(fill="x", pady=(0, 8))

        tk.Label(self.panel_window,
            text="Pulsa 'Traducir ahora' (F8) para capturar",
            bg=C["bg"], fg=C["fg2"],
            font=("Segoe UI", 9, "italic")).pack(pady=4)

        # Botones rapidos en el panel
        pb = tk.Frame(self.panel_window, bg=C["bg"])
        pb.pack(fill="x", padx=10, pady=6)
        tk.Button(pb, text="Traducir (F8)",
            command=self.traducir_ahora,
            bg=C["accent"], fg="white", relief="flat",
            font=("Segoe UI", 10, "bold"), cursor="hand2",
            padx=10, pady=6).pack(side="left", padx=2, fill="x", expand=True)
        tk.Button(pb, text="Auto (F9)",
            command=self.toggle_automatico,
            bg=C["bg3"], fg=C["fg"], relief="flat",
            font=("Segoe UI", 9), cursor="hand2",
            padx=8, pady=6).pack(side="left", padx=2)

        # Area de resultados
        self.panel_lista = scrolledtext.ScrolledText(self.panel_window,
            bg=C["bg2"], fg=C["fg"], font=("Segoe UI", 10),
            wrap="word", relief="flat", padx=12, pady=12)
        self.panel_lista.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        self.panel_lista.tag_config("orig",
            foreground=C["fg2"], font=("Segoe UI", 9, "italic"))
        self.panel_lista.tag_config("trad",
            foreground=C["accent2"], font=("Segoe UI", 10, "bold"))
        self.panel_lista.tag_config("sep",
            foreground=C["bg3"])

    def cambiar_modo(self):
        self.modo = "panel" if self.modo == "overlay" else "overlay"
        self.modo_var.set(self.modo)
        self.aplicar_modo()

    # ============================================================
    # NUCLEO: TRADUCIR AHORA
    # ============================================================
    def traducir_ahora(self):
        if self.procesando:
            return
        if not PIL_OK:
            messagebox.showwarning("Falta Pillow",
                "Instala: pip install Pillow")
            return
        # Vision NO necesita Tesseract, los demas si
        if self.motor_trad != "vision" and not TESS_OK:
            messagebox.showwarning("Falta Tesseract",
                "El modo actual necesita Tesseract para OCR.\n\n"
                "OPCION MEJOR: cambia el motor a '👁️ VISION IA' arriba.\n"
                "Ese modo no necesita Tesseract y funciona mucho mejor.\n\n"
                "Si quieres seguir con OCR:\n"
                "1) Instala Tesseract:\n"
                "   https://github.com/UB-Mannheim/tesseract/wiki\n"
                "2) Reinicia el programa.")
            return
        # Vision necesita API key
        if self.motor_trad == "vision" and not self.api_key and self.proveedor != "Ollama":
            messagebox.showwarning("Falta API Key",
                f"El modo Vision necesita API Key de {self.proveedor}.\n\n"
                "Recomendado GRATIS: Gemini\n"
                "https://aistudio.google.com/apikey")
            return

        self.procesando = True
        self._set_status("Capturando pantalla...", C["accent"])

        def tarea():
            try:
                # Ocultar el panel de control brevemente para no capturarlo
                original_alpha = None
                try:
                    original_alpha = self.root.attributes("-alpha")
                    self.root.attributes("-alpha", 0.0)
                except Exception:
                    pass
                if self.overlay_window:
                    self._limpiar_overlay()
                    try:
                        self.overlay_window.attributes("-alpha", 0.0)
                    except Exception:
                        pass
                time.sleep(0.3)  # esperar a que se aplique

                # Capturar
                img = ImageGrab.grab()
                self.ultima_captura = img

                # Restaurar
                if original_alpha is not None:
                    try: self.root.attributes("-alpha", original_alpha)
                    except Exception: pass
                if self.overlay_window:
                    try:
                        self.overlay_window.attributes("-alpha", self.transparencia)
                    except Exception:
                        pass

                # ============================================================
                # RUTA A: MODO VISION (sin OCR, IA ve la imagen directamente)
                # ============================================================
                if self.motor_trad == "vision":
                    self.root.after(0,
                        lambda: self._set_status(
                            f"IA leyendo y traduciendo la imagen...", C["accent"]))

                    idioma_nombre = IDIOMAS.get(self.idioma_destino, "espanol")
                    respuesta, err = traducir_por_vision(
                        img, self.proveedor, self.modelo, self.api_key,
                        idioma_destino_nombre=idioma_nombre,
                        idioma_origen=self.idioma_origen)

                    if err:
                        self.root.after(0,
                            lambda e=err: self._set_status(
                                f"Error vision: {e}", C["err"]))
                        self.procesando = False
                        return

                    # Parsear respuesta en pares original -> traduccion
                    pares = parsear_traducciones_vision(respuesta)
                    if not pares:
                        self.root.after(0,
                            lambda: self._set_status(
                                "La IA no devolvio texto", C["warn"]))
                        self.procesando = False
                        return

                    # Convertir a formato "boxes" (sin posiciones reales, pero
                    # el modo panel no las necesita; el overlay las simula)
                    boxes = []
                    for i, p in enumerate(pares):
                        boxes.append({
                            "texto": p["original"] or f"(linea {i+1})",
                            "traduccion": p["traduccion"],
                            "x": 20, "y": 40 + i * 30,
                            "w": 400, "h": 26,
                        })

                    # Mostrar en el panel (mejor para vision porque no hay
                    # posiciones exactas)
                    if self.modo == "overlay":
                        self.root.after(0,
                            lambda: self._mostrar_overlay_vision(pares))
                    else:
                        self.root.after(0, lambda: self._mostrar_panel(boxes))

                    self.root.after(0,
                        lambda: self._actualizar_historial(boxes))
                    self.root.after(0,
                        lambda n=len(pares): self._set_status(
                            f"OK Vision - {n} textos traducidos", C["ok"]))
                    self.procesando = False
                    return

                # ============================================================
                # RUTA B: MODO OCR (Google o IA + Tesseract)
                # ============================================================
                self.root.after(0,
                    lambda: self._set_status("OCR... detectando texto", C["accent"]))

                # OCR - usar solo idiomas realmente instalados
                origen_ocr = TESS_LANG.get(self.idioma_origen, "eng+spa")
                if self.idioma_origen == "auto":
                    origen_ocr = "eng+spa"

                # Filtrar por lo que Tesseract realmente tiene
                idiomas_inst = detectar_idiomas_disponibles_tesseract()
                if idiomas_inst:
                    origen_lista = origen_ocr.split("+")
                    filtrados = [l for l in origen_lista if l in idiomas_inst]
                    if not filtrados:
                        # Fallback: usar eng si esta, si no el primero
                        if "eng" in idiomas_inst:
                            filtrados = ["eng"]
                        else:
                            filtrados = [idiomas_inst[0]]
                    origen_ocr = "+".join(filtrados)

                print(f"[Translator] OCR con idiomas: {origen_ocr}")
                _, boxes = hacer_ocr(img, idioma_ocr=origen_ocr, con_boxes=True)

                if not boxes:
                    self.root.after(0,
                        lambda: self._set_status(
                            "No detecte texto. Prueba modo VISION IA", C["warn"]))
                    self.procesando = False
                    return

                self.root.after(0,
                    lambda n=len(boxes): self._set_status(
                        f"Traduciendo {n} lineas...", C["accent"]))

                # Traducir (agrupar el texto en un solo request si es corto)
                textos_a_traducir = [b["texto"] for b in boxes]
                traducciones = self._traducir_lista(textos_a_traducir)
                for b, t in zip(boxes, traducciones):
                    b["traduccion"] = t

                # Mostrar segun modo
                if self.modo == "overlay":
                    self.root.after(0, lambda: self._mostrar_overlay(boxes))
                else:
                    self.root.after(0, lambda: self._mostrar_panel(boxes))

                # Historial
                self.root.after(0, lambda: self._actualizar_historial(boxes))

                self.root.after(0,
                    lambda n=len(boxes): self._set_status(
                        f"OK - {n} lineas traducidas", C["ok"]))
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.root.after(0,
                    lambda e=e: self._set_status(f"Error: {e}", C["err"]))
            finally:
                self.procesando = False

        threading.Thread(target=tarea, daemon=True).start()

    def _traducir_lista(self, textos):
        """Traduce una lista de textos y devuelve la lista de traducciones.
        Ahora hace BATCH real: manda todos los textos en UNA sola llamada IA."""
        if not textos:
            return []

        idioma_nombre = IDIOMAS.get(self.idioma_destino, "espanol")

        # Separar los que estan en cache de los que no
        resultados = [None] * len(textos)
        pendientes_indices = []
        pendientes_textos = []
        for i, txt in enumerate(textos):
            if not txt.strip():
                resultados[i] = ""
                continue
            key = f"{self.idioma_origen}>{self.idioma_destino}::{txt}"
            if key in self.cache_traducciones:
                resultados[i] = self.cache_traducciones[key]
            else:
                pendientes_indices.append(i)
                pendientes_textos.append(txt)

        if not pendientes_textos:
            return resultados  # todo estaba en cache

        # Traducir los pendientes segun motor
        if self.motor_trad == "ia":
            # BATCH: una sola llamada con todos los textos
            traducidos = traducir_ia_batch(
                pendientes_textos,
                self.proveedor, self.modelo, self.api_key,
                idioma_destino_nombre=idioma_nombre,
                idioma_origen=self.idioma_origen,
            )
        else:  # google (una llamada por texto, pero es rapido)
            traducidos = []
            for txt in pendientes_textos:
                trad, err = traducir_google(txt,
                    origen=self.idioma_origen, destino=self.idioma_destino)
                if err or not trad:
                    trad = f"[?] {txt}"
                traducidos.append(trad)

        # Rellenar resultados y guardar en cache
        for idx, trad in zip(pendientes_indices, traducidos):
            resultados[idx] = trad
            key = f"{self.idioma_origen}>{self.idioma_destino}::{textos[idx]}"
            self.cache_traducciones[key] = trad

        # Persistir cache (limitada)
        if len(self.cache_traducciones) > 2000:
            # Eliminar los mas viejos
            self.cache_traducciones = dict(
                list(self.cache_traducciones.items())[-1500:])
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache_traducciones, f, ensure_ascii=False)
        except Exception:
            pass

        return resultados

    # ============================================================
    # MOSTRAR RESULTADOS
    # ============================================================
    def _limpiar_overlay(self):
        if not self.overlay_window:
            return
        try:
            self.overlay_canvas.delete("traduccion")
            for w in self.overlays_texto:
                try: w.destroy()
                except: pass
            self.overlays_texto = []
        except Exception:
            pass

    def _mostrar_overlay(self, boxes):
        if not self.overlay_window:
            return
        self._limpiar_overlay()

        for b in boxes:
            if not b.get("traduccion"): continue
            # Fondo semitransparente detras del texto
            x, y, w, h = b["x"], b["y"], b["w"], b["h"]

            # Rectangulo de fondo (amarillo con bordes)
            self.overlay_canvas.create_rectangle(
                x - 2, y - 2, x + w + 2, y + h + 4,
                fill=C["highlight"], outline=C["accent"],
                width=1, tags="traduccion")

            # Texto de la traduccion (encima)
            # Ajustar tamano de fuente al alto de la caja
            font_size = max(9, min(int(h * 0.7), 16))
            self.overlay_canvas.create_text(
                x + 2, y + h // 2,
                text=b["traduccion"],
                anchor="w",
                font=("Segoe UI", font_size, "bold"),
                fill="#000000",
                tags="traduccion",
                width=w + 40,
            )

    def _mostrar_overlay_vision(self, pares):
        """Overlay para modo vision: como no tenemos coords, mostramos
        un panel grande arrastrable con Original -> Traduccion."""
        if not self.overlay_window:
            return
        self._limpiar_overlay()

        # Recuperar posicion guardada (o default esquina superior izquierda)
        panel_x = self.cfg.get("vision_panel_x", 20)
        panel_y = self.cfg.get("vision_panel_y", 60)

        sh = self.overlay_canvas.winfo_screenheight() if hasattr(
            self.overlay_canvas, "winfo_screenheight") else 800
        panel_w = 500
        panel_h = min(sh - 100, 80 + len(pares) * 55)

        # Crear un frame flotante sobre el canvas
        panel = tk.Frame(self.overlay_window,
            bg=C["bg2"], bd=3, relief="ridge",
            highlightthickness=2, highlightbackground=C["accent"])
        panel.place(x=panel_x, y=panel_y, width=panel_w, height=panel_h)
        self.overlays_texto.append(panel)

        # ============================================================
        # HEADER ARRASTRABLE (drag)
        # ============================================================
        header = tk.Frame(panel, bg=C["accent"], cursor="fleur")
        header.pack(fill="x")

        # Icono de mover
        tk.Label(header, text="✥",
            bg=C["accent"], fg="white",
            font=("Segoe UI", 14, "bold"),
            cursor="fleur", padx=8, pady=4
            ).pack(side="left")

        # Titulo (tambien arrastrable)
        header_lbl = tk.Label(header,
            text=f"VISION IA · {len(pares)} textos",
            bg=C["accent"], fg="white",
            font=("Segoe UI", 10, "bold"),
            anchor="w", padx=6, pady=6, cursor="fleur")
        header_lbl.pack(side="left", fill="x", expand=True)

        # Botones del header
        btn_min = tk.Button(header, text="_",
            command=lambda: self._minimizar_panel(panel, panel_w, panel_h),
            bg=C["accent"], fg="white", relief="flat",
            font=("Segoe UI", 10, "bold"), cursor="hand2",
            padx=8, pady=2, bd=0,
            activebackground=C["bg3"], activeforeground="white")
        btn_min.pack(side="right", padx=2)

        btn_x = tk.Button(header, text="✕",
            command=lambda: self._limpiar_overlay(),
            bg=C["accent"], fg="white", relief="flat",
            font=("Segoe UI", 10, "bold"), cursor="hand2",
            padx=8, pady=2, bd=0,
            activebackground=C["err"], activeforeground="white")
        btn_x.pack(side="right", padx=2)

        # === Sistema de arrastre ===
        drag = {"x": 0, "y": 0}

        def start_drag(e):
            drag["x"] = e.x_root - panel.winfo_x()
            drag["y"] = e.y_root - panel.winfo_y()

        def do_drag(e):
            nx = e.x_root - drag["x"]
            ny = e.y_root - drag["y"]
            # Limitar a la pantalla
            sw = self.root.winfo_screenwidth()
            sh_full = self.root.winfo_screenheight()
            nx = max(0, min(nx, sw - 100))
            ny = max(0, min(ny, sh_full - 40))
            panel.place(x=nx, y=ny)

        def end_drag(e):
            # Guardar posicion nueva
            self.cfg["vision_panel_x"] = panel.winfo_x()
            self.cfg["vision_panel_y"] = panel.winfo_y()
            self._guardar_cfg()

        # Bindear el header (icono, label y el propio frame) para arrastrar
        for w in (header, header_lbl):
            w.bind("<ButtonPress-1>", start_drag)
            w.bind("<B1-Motion>", do_drag)
            w.bind("<ButtonRelease-1>", end_drag)

        # ============================================================
        # CONTENIDO SCROLLABLE
        # ============================================================
        cont = tk.Frame(panel, bg=C["bg2"])
        cont.pack(fill="both", expand=True)

        canvas_inner = tk.Canvas(cont, bg=C["bg2"],
            highlightthickness=0)
        sb = tk.Scrollbar(cont, orient="vertical",
            command=canvas_inner.yview)
        frame_inner = tk.Frame(canvas_inner, bg=C["bg2"])

        frame_inner.bind("<Configure>",
            lambda e: canvas_inner.configure(scrollregion=canvas_inner.bbox("all")))
        canvas_inner.create_window((0, 0), window=frame_inner,
            anchor="nw", width=panel_w - 20)
        canvas_inner.configure(yscrollcommand=sb.set)
        canvas_inner.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Mostrar cada par
        for i, p in enumerate(pares):
            item = tk.Frame(frame_inner, bg=C["bg3"], bd=0)
            item.pack(fill="x", padx=6, pady=3)
            if p["original"]:
                tk.Label(item, text=p["original"],
                    bg=C["bg3"], fg=C["fg2"],
                    font=("Segoe UI", 9, "italic"),
                    wraplength=panel_w - 40,
                    justify="left", anchor="w"
                    ).pack(fill="x", padx=10, pady=(6, 0))
            tk.Label(item, text=p["traduccion"],
                bg=C["bg3"], fg=C["accent2"],
                font=("Segoe UI", 11, "bold"),
                wraplength=panel_w - 40,
                justify="left", anchor="w"
                ).pack(fill="x", padx=10, pady=(2, 6))

        # ============================================================
        # HANDLE DE REDIMENSIONAR (esquina inferior derecha)
        # ============================================================
        resize_handle = tk.Frame(panel, bg=C["accent"],
            cursor="bottom_right_corner", width=15, height=15)
        resize_handle.place(relx=1.0, rely=1.0, anchor="se")

        resize = {"w": panel_w, "h": panel_h, "x0": 0, "y0": 0}

        def start_resize(e):
            resize["x0"] = e.x_root
            resize["y0"] = e.y_root
            resize["w"] = panel.winfo_width()
            resize["h"] = panel.winfo_height()

        def do_resize(e):
            dx = e.x_root - resize["x0"]
            dy = e.y_root - resize["y0"]
            nw = max(250, resize["w"] + dx)
            nh = max(150, resize["h"] + dy)
            panel.place(width=nw, height=nh)
            # Actualizar ancho del contenido tambien
            canvas_inner.itemconfig(canvas_inner.find_all()[0], width=nw - 20)

        def end_resize(e):
            self.cfg["vision_panel_w"] = panel.winfo_width()
            self.cfg["vision_panel_h"] = panel.winfo_height()
            self._guardar_cfg()

        resize_handle.bind("<ButtonPress-1>", start_resize)
        resize_handle.bind("<B1-Motion>", do_resize)
        resize_handle.bind("<ButtonRelease-1>", end_resize)

        # Aplicar tamaño guardado si lo hay
        saved_w = self.cfg.get("vision_panel_w")
        saved_h = self.cfg.get("vision_panel_h")
        if saved_w and saved_h:
            panel.place(width=saved_w, height=saved_h)

        # Rueda del raton para scroll
        def _mw(e):
            canvas_inner.yview_scroll(-int(e.delta / 60), "units")
        panel.bind_all("<MouseWheel>", _mw)

        # Guardar referencia para poder maximizar/minimizar
        self._panel_vision = panel
        self._panel_vision_contenido = cont
        self._panel_vision_minimizado = False

    def _minimizar_panel(self, panel, w_full, h_full):
        """Minimiza/restaura el panel (solo header visible)."""
        if not hasattr(self, "_panel_vision_contenido"):
            return
        cont = self._panel_vision_contenido
        if self._panel_vision_minimizado:
            # Restaurar
            cont.pack(fill="both", expand=True)
            saved_h = self.cfg.get("vision_panel_h", h_full)
            panel.place(height=saved_h)
            self._panel_vision_minimizado = False
        else:
            # Minimizar
            cont.pack_forget()
            panel.place(height=40)
            self._panel_vision_minimizado = True

    def _mostrar_panel(self, boxes):
        if not self.panel_window:
            return
        self.panel_lista.delete("1.0", "end")
        for b in boxes:
            if not b.get("traduccion"): continue
            self.panel_lista.insert("end", f"{b['texto']}\n", "orig")
            self.panel_lista.insert("end", f"{b['traduccion']}\n", "trad")
            self.panel_lista.insert("end",
                "─────────────────────────\n", "sep")
        self.panel_lista.see("1.0")

    def _actualizar_historial(self, boxes):
        hora = datetime.now().strftime("%H:%M:%S")
        self.hist_text.insert("1.0",
            f"[{hora}] {len(boxes)} lineas · "
            f"{self.idioma_origen}→{self.idioma_destino}\n")
        # Mostrar solo primeras 2 traducciones
        for b in boxes[:3]:
            if b.get("traduccion"):
                self.hist_text.insert("2.0",
                    f"  {b['traduccion'][:80]}\n")
        # Limitar historial
        lineas = int(self.hist_text.index("end-1c").split(".")[0])
        if lineas > 40:
            self.hist_text.delete("30.0", "end")

    # ============================================================
    # AUTOMATICO
    # ============================================================
    def toggle_automatico(self):
        self.automatico = not self.automatico
        if self.automatico:
            self.btn_auto.config(text=f"AUTOMATICO ON ({self.intervalo_var.get()}s)",
                                   bg=C["ok"])
            self._loop_auto()
        else:
            self.btn_auto.config(text="AUTOMATICO OFF (F9)",
                                   bg=C["bg3"])

    def _loop_auto(self):
        if not self.automatico:
            return
        self.traducir_ahora()
        segundos = max(1, int(self.intervalo_var.get()))
        self.intervalo = segundos
        self.root.after(segundos * 1000, self._loop_auto)

    # ============================================================
    # SALIR
    # ============================================================
    def _set_status(self, texto, color=C["fg"]):
        self.status.config(text=texto, fg=color)

    def salir(self):
        self._actualizar_cfg()
        try:
            if self.overlay_window: self.overlay_window.destroy()
            if self.panel_window: self.panel_window.destroy()
        except: pass
        self.root.destroy()


if __name__ == "__main__":
    print("Iniciando NOVA Translator...")
    try:
        root = tk.Tk()
        app = NovaTranslator(root)
        print("Traductor listo. Pulsa F8 para traducir la pantalla.")
        root.mainloop()
    except Exception as e:
        import traceback
        print(f"\n[ERROR]: {e}")
        traceback.print_exc()
        input("\nPulsa ENTER para cerrar...")
