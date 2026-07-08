"""
🔌 nova_ia_lib.py — Librería compartida de conexión a IAs
==========================================================
Una sola fuente de verdad para conectar con LLMs.
Usada por: Nova Jarvis, Nova Reader, Nova Search, Nova Game Master, Nova Telegram.

Características:
  • Detección AUTOMÁTICA de modelos disponibles por API
  • Reintentos inteligentes con backoff
  • Manejo robusto de errores HTTP
  • Mismo interfaz para Gemini/Groq/OpenAI/Ollama/Anthropic
  • Cache de modelos para no re-consultar siempre
"""
import os, json, time
import urllib.request, urllib.parse, urllib.error

USER_AGENT = "NovaAI/2.0 (Educational)"

# ============================================================
# MODELOS POR DEFECTO (fallback si la API no devuelve nada)
# ============================================================
MODELOS_DEFAULT = {
    "Gemini": [
        "gemini-2.5-flash", "gemini-2.5-pro",
        "gemini-2.0-flash", "gemini-flash-latest",
    ],
    "Groq": [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3-32b",
        "moonshotai/kimi-k2-instruct",
        "groq/compound",
    ],
    "OpenAI": [
        "gpt-4o-mini", "gpt-4o", "gpt-4.1", "gpt-4.1-mini",
        "o3-mini", "gpt-3.5-turbo",
    ],
    "Claude": [
        "claude-sonnet-4-5", "claude-3-5-sonnet-latest",
        "claude-3-5-haiku-latest", "claude-3-haiku-20240307",
    ],
    "NVIDIA": [
        "meta/llama-3.3-70b-instruct",
        "meta/llama-3.1-405b-instruct",
        "meta/llama-3.1-70b-instruct",
        "meta/llama-3.1-8b-instruct",
        "moonshotai/kimi-k2-instruct",
        "deepseek-ai/deepseek-r1",
        "mistralai/mixtral-8x22b-instruct-v0.1",
        "qwen/qwen2.5-72b-instruct",
        "google/gemma-2-27b-it",
        "nvidia/llama-3.1-nemotron-70b-instruct",
    ],
    "Ollama": [
        "llama3.2", "llama3.1", "mistral", "qwen2.5", "gemma2", "phi3",
    ],
}

URLS_API_KEY = {
    "Gemini": "https://aistudio.google.com/apikey",
    "Groq": "https://console.groq.com/keys",
    "OpenAI": "https://platform.openai.com/api-keys",
    "Claude": "https://console.anthropic.com/settings/keys",
    "NVIDIA": "https://build.nvidia.com/",
    "Ollama": "https://ollama.com",
}

# ============================================================
# DETECCIÓN AUTOMÁTICA DE MODELOS DISPONIBLES
# ============================================================
_cache_modelos = {}  # {proveedor: [modelos]}

def listar_modelos(proveedor, api_key="", forzar_refresh=False):
    """
    Devuelve la lista de modelos REALES que el proveedor acepta AHORA.
    Si falla la conexión, devuelve la lista por defecto.
    """
    # Cache (durante esta sesión)
    if not forzar_refresh and proveedor in _cache_modelos:
        return _cache_modelos[proveedor]

    modelos = None
    try:
        if proveedor == "Gemini" and api_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            modelos = [m["name"].replace("models/", "") for m in data.get("models", [])
                       if "generateContent" in m.get("supportedGenerationMethods", [])
                       and ("gemini" in m["name"].lower())]
        elif proveedor == "Groq" and api_key:
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}",
                         "User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            # Filtrar: solo chat models (excluir whisper, embeddings)
            modelos = sorted([m["id"] for m in data.get("data", [])
                              if not any(x in m["id"].lower()
                                          for x in ["whisper", "embed", "guard", "tts"])])
        elif proveedor == "OpenAI" and api_key:
            req = urllib.request.Request(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}",
                         "User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            modelos = sorted([m["id"] for m in data.get("data", [])
                              if any(p in m["id"] for p in ["gpt", "o1", "o3", "chatgpt"])
                              and not any(x in m["id"]
                                           for x in ["whisper", "tts", "embed", "moderation",
                                                     "audio", "realtime", "image", "vision"])])
        elif proveedor == "Claude" and api_key:
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": api_key,
                         "anthropic-version": "2023-06-01",
                         "User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            modelos = sorted([m["id"] for m in data.get("data", [])])
        elif proveedor == "NVIDIA" and api_key:
            req = urllib.request.Request(
                "https://integrate.api.nvidia.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}",
                         "User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            # Filtrar: excluir embeddings, reranking, etc.
            modelos = sorted([m["id"] for m in data.get("data", [])
                              if not any(x in m["id"].lower()
                                          for x in ["embed", "rerank",
                                                     "guard", "vision",
                                                     "riva", "nemoretriever"])])
        elif proveedor == "Ollama":
            try:
                req = urllib.request.Request("http://localhost:11434/api/tags",
                    headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=5) as r:
                    data = json.loads(r.read())
                modelos = sorted([m["name"] for m in data.get("models", [])])
            except Exception:
                modelos = None  # Ollama no responde
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return MODELOS_DEFAULT.get(proveedor, [])  # API key mala
    except Exception:
        pass

    # Si no obtuvimos nada, usar default
    if not modelos:
        modelos = MODELOS_DEFAULT.get(proveedor, [])

    _cache_modelos[proveedor] = modelos
    return modelos

# ============================================================
# LLAMADA UNIFICADA A LLM
# ============================================================
def llamar_llm(proveedor, modelo, api_key, system_prompt, user_prompt,
                historial=None, timeout=180, reintentos=3, imagen=None):
    """
    Llama a cualquier LLM y devuelve (respuesta, error).
    - Si historial=None se hace pregunta única.
    - Si historial=[{role,content}...] se mantiene contexto.
    - Si imagen=<ruta o bytes>, se envía como visión (solo Gemini/OpenAI/Claude/NVIDIA
      con modelos multimodales compatibles).
    """
    historial = historial or []
    mensajes = list(historial) + [{"role": "user", "content": user_prompt}]

    ultimo_err = None
    for intento in range(reintentos):
        try:
            if proveedor == "Gemini":
                return _llamar_gemini(modelo, api_key, system_prompt,
                                        mensajes, timeout, imagen=imagen)
            if proveedor == "Claude":
                return _llamar_claude(modelo, api_key, system_prompt,
                                        mensajes, timeout, imagen=imagen)
            if proveedor == "Ollama":
                return _llamar_ollama(modelo, system_prompt, mensajes,
                                        timeout, imagen=imagen)
            # Groq, OpenAI, NVIDIA (formato OpenAI-compatible)
            return _llamar_openai_compat(proveedor, modelo, api_key,
                                          system_prompt, mensajes, timeout,
                                          imagen=imagen)
        except urllib.error.HTTPError as e:
            cuerpo = e.read().decode("utf-8", errors="ignore")[:300]
            if e.code == 503:
                ultimo_err = "⏳ Servicio saturado (503)"
                if intento < reintentos - 1:
                    time.sleep(5 + intento * 5); continue
                return None, "❌ Servidor saturado. Espera 1 minuto."
            if e.code == 429:
                ultimo_err = "⏳ Rate limit"
                if intento < reintentos - 1:
                    time.sleep(15 + intento * 15); continue
                return None, "❌ Rate limit. Espera 1 minuto."
            if e.code == 401:
                if proveedor == "NVIDIA":
                    return None, ("🔑 API Key inválida para NVIDIA.\n\n"
                        "IMPORTANTE: Crea la key en:\n"
                        "  https://build.nvidia.com/settings/api-keys\n"
                        "(NO uses el botón azul 'Get API Key' de un modelo,\n"
                        "usa Settings → API Keys de tu cuenta)")
                return None, "🔑 API Key inválida"
            if e.code == 403:
                if proveedor == "NVIDIA":
                    return None, ("🛡️ NVIDIA: 'Authorization failed' (403).\n\n"
                        "Tu API key es válida pero tu cuenta no tiene\n"
                        "permiso 'Public API Endpoints'.\n\n"
                        "Solución:\n"
                        "1) Ve a https://build.nvidia.com/settings/api-keys\n"
                        "2) Borra la key actual\n"
                        "3) Crea una nueva key desde Settings (NO desde un modelo)\n"
                        "4) Si sigue fallando, la organización 'Personal' necesita\n"
                        "   permisos activados por NVIDIA (contacta soporte)")
                if "1010" in cuerpo:
                    return None, "🛡️ Bloqueado por Cloudflare"
                return None, f"🛡️ Acceso denegado: {cuerpo[:150]}"
            if e.code == 404:
                return None, (f"❌ Modelo '{modelo}' NO EXISTE en {proveedor}.\n"
                              f"Ve a ⚙ Config → 🔄 Refrescar modelos para ver "
                              f"los disponibles.")
            if e.code == 400:
                return None, f"❌ Petición incorrecta: {cuerpo[:200]}"
            return None, f"HTTP {e.code}: {cuerpo[:150]}"
        except urllib.error.URLError as e:
            if proveedor == "Ollama":
                return None, "🌟 Ollama no responde. ¿Está abierto?"
            return None, f"Sin conexión: {str(e)[:100]}"
        except Exception as e:
            return None, f"{type(e).__name__}: {str(e)[:200]}"
    return None, ultimo_err or "Error desconocido"

def _cargar_imagen_b64(imagen):
    """Convierte una ruta de imagen o bytes a base64."""
    import base64
    if isinstance(imagen, (bytes, bytearray)):
        return base64.b64encode(imagen).decode("utf-8")
    if isinstance(imagen, str):
        with open(imagen, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return None

def _mime_de_imagen(ruta):
    if isinstance(ruta, str):
        low = ruta.lower()
        if low.endswith(".png"): return "image/png"
        if low.endswith(".gif"): return "image/gif"
        if low.endswith(".webp"): return "image/webp"
    return "image/jpeg"

def _llamar_gemini(modelo, api_key, system, mensajes, timeout, imagen=None):
    url = (f"https://generativelanguage.googleapis.com/v1beta/"
           f"models/{modelo}:generateContent?key={api_key}")
    contents = []
    for i, m in enumerate(mensajes):
        role = "user" if m["role"] == "user" else "model"
        parts = [{"text": m["content"]}]
        # Adjuntar imagen al ULTIMO mensaje user
        if imagen and role == "user" and i == len(mensajes) - 1:
            b64 = _cargar_imagen_b64(imagen)
            if b64:
                parts.append({"inline_data": {
                    "mime_type": _mime_de_imagen(imagen),
                    "data": b64
                }})
        contents.append({"role": role, "parts": parts})
    body = {"contents": contents}
    if system:
        body["system_instruction"] = {"parts": [{"text": system}]}
    req = urllib.request.Request(url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    if "candidates" not in data or not data["candidates"]:
        return None, "Sin respuesta de Gemini (filtros de seguridad?)"
    return data["candidates"][0]["content"]["parts"][0]["text"], None

def _llamar_claude(modelo, api_key, system, mensajes, timeout, imagen=None):
    # Si hay imagen, adjuntarla al ultimo mensaje user
    if imagen and mensajes:
        b64 = _cargar_imagen_b64(imagen)
        if b64:
            ultimo = mensajes[-1]
            if ultimo["role"] == "user":
                ultimo["content"] = [
                    {"type": "image", "source": {
                        "type": "base64",
                        "media_type": _mime_de_imagen(imagen),
                        "data": b64,
                    }},
                    {"type": "text", "text": ultimo["content"]},
                ]
    body = {"model": modelo, "max_tokens": 4096, "messages": mensajes}
    if system: body["system"] = system
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={"x-api-key": api_key,
                 "anthropic-version": "2023-06-01",
                 "content-type": "application/json",
                 "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return data["content"][0]["text"], None

def _llamar_ollama(modelo, system, mensajes, timeout, imagen=None):
    msgs = []
    if system: msgs.append({"role": "system", "content": system})
    msgs.extend(mensajes)
    # Ollama: soporta imagenes en 'images' del ultimo user
    if imagen and msgs:
        b64 = _cargar_imagen_b64(imagen)
        if b64:
            for m in reversed(msgs):
                if m["role"] == "user":
                    m["images"] = [b64]
                    break
    body = {"model": modelo, "stream": False, "messages": msgs}
    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=max(timeout, 300)) as r:
        data = json.loads(r.read())
    return data["message"]["content"], None

def _llamar_openai_compat(proveedor, modelo, api_key, system, mensajes,
                             timeout, imagen=None):
    endpoints = {
        "OpenAI": "https://api.openai.com/v1/chat/completions",
        "Groq":   "https://api.groq.com/openai/v1/chat/completions",
        "NVIDIA": "https://integrate.api.nvidia.com/v1/chat/completions",
    }
    endpoint = endpoints.get(proveedor)
    if not endpoint:
        return None, f"Proveedor no soportado: {proveedor}"
    msgs = []
    if system: msgs.append({"role": "system", "content": system})
    msgs.extend(mensajes)
    # Si hay imagen, adjuntarla al ultimo user (formato OpenAI vision)
    if imagen and msgs:
        b64 = _cargar_imagen_b64(imagen)
        if b64:
            for m in reversed(msgs):
                if m["role"] == "user":
                    mime = _mime_de_imagen(imagen)
                    m["content"] = [
                        {"type": "text", "text": m["content"]},
                        {"type": "image_url", "image_url": {
                            "url": f"data:{mime};base64,{b64}"
                        }},
                    ]
                    break
    body = {"model": modelo, "messages": msgs, "temperature": 0.7}
    # NVIDIA acepta max_tokens mayor
    if proveedor == "NVIDIA":
        body["max_tokens"] = 4096
        body["top_p"] = 1.0
    req = urllib.request.Request(endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json",
                 "Accept": "application/json",
                 "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"], None

# ============================================================
# DIÁLOGO DE CONFIGURACIÓN UNIVERSAL (con detección de modelos)
# ============================================================
def dialogo_config(parent, cfg_actual, on_save, titulo="⚙ Configuración",
                    colores=None):
    """
    Crea un diálogo bonito de configuración que:
    - Lista modelos disponibles automáticamente
    - Cambia modelos al cambiar de proveedor
    - Recuerda API key por proveedor
    - Tiene botón 🔄 para refrescar modelos en vivo

    cfg_actual: dict con keys "proveedor", "modelo", "api_key", "api_keys"
    on_save(nuevo_cfg): callback cuando se guarda
    colores: dict opcional con bg, bg2, fg, accent...
    """
    import tkinter as tk
    from tkinter import ttk, messagebox

    C = colores or {
        "bg": "#1a1a2e", "bg2": "#282a36",
        "fg": "#f8f8f2", "accent": "#a78bfa",
        "warn": "#fbbf24", "ok": "#22c55e",
    }

    v = tk.Toplevel(parent)
    v.title(titulo)
    v.geometry("560x520")
    v.configure(bg=C["bg"])
    v.transient(parent)

    tk.Label(v, text=titulo, bg=C["bg"], fg=C["accent"],
             font=("Segoe UI", 14, "bold")).pack(pady=12)

    # Estado actual
    proveedor_actual = cfg_actual.get("proveedor", "Gemini")
    api_keys = cfg_actual.get("api_keys", {})

    # === Proveedor ===
    tk.Label(v, text="🤖 Proveedor:", bg=C["bg"], fg=C["accent"],
             font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=20, pady=(8, 2))
    prov_var = tk.StringVar(value=proveedor_actual)
    prov_combo = ttk.Combobox(v, textvariable=prov_var,
                                values=list(MODELOS_DEFAULT.keys()),
                                state="readonly", font=("Segoe UI", 10))
    prov_combo.pack(padx=20, fill="x", ipady=2)

    # === API Key (arriba para poder consultar modelos) ===
    tk.Label(v, text="🔑 API Key:", bg=C["bg"], fg=C["accent"],
             font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=20, pady=(10, 2))
    key_var = tk.StringVar(value=api_keys.get(proveedor_actual, ""))
    key_entry = tk.Entry(v, textvariable=key_var, show="*",
                          bg=C["bg2"], fg=C["fg"], relief="flat",
                          insertbackground=C["fg"], font=("Segoe UI", 10))
    key_entry.pack(padx=20, fill="x", ipady=4)

    link = tk.Label(v, text="", bg=C["bg"], fg="#60a5fa",
                     font=("Segoe UI", 8, "underline"), cursor="hand2")
    link.pack(padx=20, anchor="w", pady=(2, 8))

    # === Modelo (con botón refrescar) ===
    mod_frame = tk.Frame(v, bg=C["bg"])
    mod_frame.pack(fill="x", padx=20, pady=(6, 0))
    tk.Label(mod_frame, text="📦 Modelo:", bg=C["bg"], fg=C["accent"],
             font=("Segoe UI", 10, "bold")).pack(side="left")
    btn_refrescar = tk.Button(mod_frame, text="🔄 Refrescar modelos",
                                bg=C["accent"], fg=C["bg"], relief="flat",
                                font=("Segoe UI", 8, "bold"), cursor="hand2",
                                padx=8, pady=2)
    btn_refrescar.pack(side="right")

    mod_var = tk.StringVar(value=cfg_actual.get("modelo", ""))
    mod_combo = ttk.Combobox(v, textvariable=mod_var, font=("Segoe UI", 10))
    mod_combo.pack(padx=20, fill="x", ipady=2)

    # Estado de modelos
    lbl_estado = tk.Label(v, text="", bg=C["bg"], fg=C["warn"],
                           font=("Segoe UI", 9, "italic"))
    lbl_estado.pack(padx=20, anchor="w", pady=(4, 8))

    def cargar_modelos(prov, key, forzar=False):
        """Carga modelos del proveedor en el combo."""
        lbl_estado.config(text="⏳ Consultando modelos disponibles...", fg=C["warn"])
        v.update_idletasks()
        try:
            modelos = listar_modelos(prov, key, forzar_refresh=forzar)
            mod_combo["values"] = modelos
            if mod_var.get() not in modelos and modelos:
                mod_var.set(modelos[0])
            if modelos:
                lbl_estado.config(
                    text=f"✅ {len(modelos)} modelos disponibles",
                    fg=C["ok"])
            else:
                lbl_estado.config(text="⚠️ No se pudieron consultar modelos",
                                   fg=C["warn"])
        except Exception as e:
            lbl_estado.config(text=f"❌ {str(e)[:60]}", fg="#ef4444")

    def upd_link():
        u = URLS_API_KEY.get(prov_var.get(), "")
        if prov_var.get() == "Ollama":
            link.config(text="🌟 Ollama es LOCAL — no necesita API key")
        else:
            link.config(text=f"🌐 Conseguir API Key gratis ({u})")
        link.unbind("<Button-1>")
        link.bind("<Button-1>", lambda e: __import__("webbrowser").open(u))

    def cambio_prov(*a):
        np = prov_var.get()
        # Cargar API key guardada de este proveedor
        kg = api_keys.get(np, "")
        key_var.set(kg)
        upd_link()
        if np == "Ollama":
            key_entry.config(state="disabled")
            key_var.set("(no necesario)")
        else:
            key_entry.config(state="normal")
            if key_var.get() == "(no necesario)": key_var.set("")
        # Cargar modelos para el nuevo proveedor
        v.after(100, lambda: cargar_modelos(np, key_var.get()))

    prov_combo.bind("<<ComboboxSelected>>", cambio_prov)
    btn_refrescar.config(command=lambda: cargar_modelos(
        prov_var.get(), key_var.get(), forzar=True))

    # Inicialización
    upd_link()
    if proveedor_actual == "Ollama":
        key_entry.config(state="disabled")
        key_var.set("(no necesario)")
    v.after(200, lambda: cargar_modelos(proveedor_actual, key_var.get()))

    # Botones
    bf = tk.Frame(v, bg=C["bg"]); bf.pack(side="bottom", pady=14)

    def guardar():
        kr = key_var.get().strip()
        if kr == "(no necesario)": kr = ""
        nuevo = {
            "proveedor": prov_var.get(),
            "modelo": mod_var.get().strip(),
            "api_key": kr,
        }
        # Guardar api key en api_keys (por proveedor)
        if kr:
            api_keys[nuevo["proveedor"]] = kr
        nuevo["api_keys"] = api_keys
        on_save(nuevo)
        v.destroy()
        messagebox.showinfo("✅ Guardado",
            f"Proveedor: {nuevo['proveedor']}\nModelo: {nuevo['modelo']}")

    tk.Button(bf, text="💾 Guardar", command=guardar,
              bg=C["ok"], fg="white", font=("Segoe UI", 11, "bold"),
              relief="flat", padx=22, pady=7, cursor="hand2"
              ).pack(side="left", padx=8)
    tk.Button(bf, text="Cancelar", command=v.destroy,
              bg=C["bg2"], fg=C["fg"], font=("Segoe UI", 10),
              relief="flat", padx=18, pady=7, cursor="hand2"
              ).pack(side="left", padx=8)
