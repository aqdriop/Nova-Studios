"""
📱 NOVA TELEGRAM BOT — Habla con NOVA desde tu móvil
=====================================================
- Bot de Telegram conectado a tu IA preferida (Gemini, Groq, Ollama...)
- Funciona desde cualquier parte del mundo
- Solo tú puedes usarlo (filtro por chat_id)
- Comandos: /start /imagen /reset /help
- Genera imágenes con Pollinations
- Mantiene historial de conversación
"""
import os, sys, json, threading, time
import urllib.request, urllib.parse, urllib.error

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# VERSION (para el sistema de actualizaciones)
# ============================================================
VERSION = "1.0.0"
MODULO_ID = "telegram"

PARENT = os.path.dirname(APP_DIR)
CONFIG = os.path.join(PARENT, "config.json")
BOT_CONFIG = os.path.join(APP_DIR, "telegram_config.json")

def cargar_cfg():
    cfgs = {}
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG, "r", encoding="utf-8") as f: cfgs.update(json.load(f))
        except: pass
    if os.path.exists(BOT_CONFIG):
        try:
            with open(BOT_CONFIG, "r", encoding="utf-8") as f: cfgs.update(json.load(f))
        except: pass
    return cfgs

def guardar_bot_cfg(c):
    actual = {}
    if os.path.exists(BOT_CONFIG):
        try:
            with open(BOT_CONFIG, "r", encoding="utf-8") as f: actual = json.load(f)
        except: pass
    actual.update(c)
    with open(BOT_CONFIG, "w", encoding="utf-8") as f:
        json.dump(actual, f, indent=2)

class NovaTelegramBot:
    def __init__(self):
        self.cfg = cargar_cfg()
        self.token = self.cfg.get("telegram_bot_token", "")
        self.allowed_chats = self.cfg.get("telegram_allowed_chats", [])  # IDs permitidos
        self.proveedor = self.cfg.get("telegram_proveedor", "Gemini")
        self.modelo = self.cfg.get("telegram_modelo", "gemini-2.5-flash")
        self.api_key = self.cfg.get("api_keys", {}).get(self.proveedor, "")
        self.historiales = {}  # {chat_id: [mensajes]}
        self.offset = 0
        self.running = False

    def tg(self, method, **params):
        """Llamada a la API de Telegram."""
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        data = urllib.parse.urlencode(params).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:
            print(f"❌ Error Telegram: {e}")
            return None

    def enviar(self, chat_id, texto):
        # Telegram limita a 4096 chars
        for i in range(0, len(texto), 4000):
            self.tg("sendMessage", chat_id=chat_id, text=texto[i:i+4000], parse_mode="Markdown")

    def enviar_imagen(self, chat_id, url):
        self.tg("sendPhoto", chat_id=chat_id, photo=url)

    def enviar_typing(self, chat_id):
        self.tg("sendChatAction", chat_id=chat_id, action="typing")

    def llamar_llm(self, mensajes, system):
        try:
            if self.proveedor == "Gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.modelo}:generateContent?key={self.api_key}"
                contents = []
                for m in mensajes:
                    contents.append({"role": "user" if m["role"]=="user" else "model",
                                      "parts": [{"text": m["content"]}]})
                body = {"system_instruction":{"parts":[{"text":system}]}, "contents":contents}
                req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                    headers={"Content-Type":"application/json","User-Agent":"NovaTelegram/1.0"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    return json.loads(r.read())["candidates"][0]["content"]["parts"][0]["text"]
            if self.proveedor == "Ollama":
                body = {"model":self.modelo, "stream":False,
                        "messages":[{"role":"system","content":system}]+mensajes}
                req = urllib.request.Request("http://localhost:11434/api/chat",
                    data=json.dumps(body).encode("utf-8"),
                    headers={"Content-Type":"application/json"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    return json.loads(r.read())["message"]["content"]
            # Groq, OpenAI
            endpoints = {"Groq":"https://api.groq.com/openai/v1/chat/completions",
                          "OpenAI":"https://api.openai.com/v1/chat/completions"}
            body = {"model":self.modelo,
                    "messages":[{"role":"system","content":system}]+mensajes,
                    "temperature":0.7}
            req = urllib.request.Request(endpoints[self.proveedor],
                data=json.dumps(body).encode("utf-8"),
                headers={"Authorization":f"Bearer {self.api_key}",
                         "Content-Type":"application/json",
                         "User-Agent":"NovaTelegram/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())["choices"][0]["message"]["content"]
        except Exception as e:
            return f"❌ Error: {str(e)[:200]}"

    def manejar_mensaje(self, msg):
        chat_id = msg["chat"]["id"]
        texto = msg.get("text", "")
        nombre = msg["from"].get("first_name", "amigo")

        # Filtro de seguridad: solo chats permitidos (si está configurado)
        if self.allowed_chats and chat_id not in self.allowed_chats:
            self.enviar(chat_id,
                f"❌ Lo siento, no estás autorizado.\n\n"
                f"Pídele al propietario del bot que añada tu Chat ID: `{chat_id}`")
            return

        # Comandos
        if texto.startswith("/start"):
            self.enviar(chat_id,
                f"👋 ¡Hola {nombre}! Soy *NOVA*, tu asistente IA personal.\n\n"
                f"📝 Escríbeme lo que quieras\n"
                f"🎨 /imagen [descripción] para generar imágenes\n"
                f"🧹 /reset para borrar nuestra conversación\n"
                f"❓ /help para ver más opciones\n\n"
                f"🤖 Modelo actual: `{self.modelo}` ({self.proveedor})\n"
                f"🆔 Tu Chat ID: `{chat_id}`")
            return

        if texto.startswith("/help"):
            self.enviar(chat_id,
                "📋 *Comandos disponibles:*\n\n"
                "/start — Mensaje de bienvenida\n"
                "/imagen [prompt] — Genera una imagen\n"
                "/reset — Borra historial de conversación\n"
                "/info — Estado del bot\n\n"
                "💬 O simplemente escribe cualquier cosa para charlar.")
            return

        if texto.startswith("/reset"):
            self.historiales[chat_id] = []
            self.enviar(chat_id, "🧹 Historial borrado. ¡Empezamos de cero!")
            return

        if texto.startswith("/info"):
            hist_len = len(self.historiales.get(chat_id, []))
            self.enviar(chat_id,
                f"ℹ️ *Estado del bot:*\n\n"
                f"• Modelo: `{self.modelo}` ({self.proveedor})\n"
                f"• Mensajes en historial: {hist_len}\n"
                f"• Chats autorizados: {len(self.allowed_chats) or '∞ (todos)'}")
            return

        if texto.startswith("/imagen"):
            prompt = texto[7:].strip()
            if not prompt:
                self.enviar(chat_id, "Uso: /imagen descripción de la imagen")
                return
            self.enviar(chat_id, "🎨 Generando imagen, espera...")
            slug = urllib.parse.quote(prompt)
            url = f"https://image.pollinations.ai/prompt/{slug}?width=768&height=768&nologo=true"
            self.enviar_imagen(chat_id, url)
            return

        # Mensaje normal → enviar a la IA
        if not texto: return
        self.enviar_typing(chat_id)

        hist = self.historiales.setdefault(chat_id, [])
        hist.append({"role":"user","content":texto})
        if len(hist) > 20: hist[:] = hist[-20:]

        system = (f"Eres NOVA, asistente personal por Telegram. "
                  f"Responde de forma natural, breve y útil. "
                  f"Hablas con {nombre}. Usa Markdown si ayuda. Idioma: español.")

        respuesta = self.llamar_llm(hist, system)
        hist.append({"role":"assistant","content":respuesta})

        self.enviar(chat_id, respuesta)

    def loop(self):
        if not self.token:
            print("❌ No hay BOT_TOKEN configurado. Edita telegram_config.json")
            return
        if not self.api_key and self.proveedor != "Ollama":
            print(f"❌ No hay API key para {self.proveedor}")
            return

        print(f"\n{'='*60}")
        print(f"🤖 NOVA TELEGRAM BOT INICIADO")
        print(f"{'='*60}")
        print(f"📱 Proveedor: {self.proveedor} ({self.modelo})")
        print(f"🔒 Chats permitidos: {self.allowed_chats or 'todos'}")
        print(f"✅ Escuchando mensajes...")
        print(f"💡 Abre Telegram y busca tu bot")
        print(f"   Ctrl+C para detener")
        print(f"{'='*60}\n")

        self.running = True
        # Limpiar updates pendientes
        r = self.tg("getUpdates", offset=-1)
        if r and r.get("result"):
            self.offset = r["result"][-1]["update_id"] + 1

        while self.running:
            try:
                r = self.tg("getUpdates", offset=self.offset, timeout=20)
                if not r or not r.get("ok"):
                    time.sleep(2); continue
                for update in r.get("result", []):
                    self.offset = update["update_id"] + 1
                    if "message" in update:
                        msg = update["message"]
                        print(f"📩 [{msg['from'].get('first_name','?')}] {msg.get('text','')[:60]}")
                        threading.Thread(target=self.manejar_mensaje, args=(msg,),
                                         daemon=True).start()
            except KeyboardInterrupt:
                print("\n👋 Bot detenido")
                self.running = False
                break
            except Exception as e:
                print(f"⚠️ {e}")
                time.sleep(3)

# Si se ejecuta directamente, hacer setup interactivo
def setup_interactivo():
    print("\n" + "="*60)
    print("🤖 SETUP DE NOVA TELEGRAM BOT")
    print("="*60)
    print("\n📝 Necesitas dos cosas:")
    print("   1. Un BOT TOKEN (gratis, te lo da @BotFather en Telegram)")
    print("   2. Una API key (Gemini gratis: https://aistudio.google.com/apikey)")
    print("\n¿Cómo crear el bot?")
    print("   1. Abre Telegram y busca @BotFather")
    print("   2. Escríbele: /newbot")
    print("   3. Dale un nombre (ej: MiNovaBot)")
    print("   4. Te dará un TOKEN tipo: 123456789:ABCdef-XXXXXXXX")
    print()

    cfg = cargar_cfg()
    actual_token = cfg.get("telegram_bot_token", "")

    if actual_token:
        print(f"✅ Ya tienes token configurado: ...{actual_token[-15:]}")
        usar = input("¿Usar este token? [s/n]: ").strip().lower()
        if usar != "s":
            actual_token = ""

    if not actual_token:
        token = input("Pega tu BOT TOKEN: ").strip()
        if not token:
            print("❌ Sin token, no se puede continuar."); return None
        guardar_bot_cfg({"telegram_bot_token": token})
        cfg["telegram_bot_token"] = token

    # Proveedor IA
    prov_actual = cfg.get("telegram_proveedor", "Gemini")
    print(f"\nProveedor IA actual: {prov_actual}")
    cambiar = input("¿Cambiar proveedor? [s/n]: ").strip().lower()
    if cambiar == "s":
        print("Opciones: Gemini / Groq / OpenAI / Ollama")
        prov = input("Proveedor: ").strip() or prov_actual
        modelos_default = {"Gemini":"gemini-2.5-flash", "Groq":"llama-3.3-70b-versatile",
                           "OpenAI":"gpt-4o-mini", "Ollama":"llama3.2"}
        modelo = input(f"Modelo [{modelos_default.get(prov,'')}]: ").strip() or modelos_default.get(prov, "")
        if prov != "Ollama":
            api_key = input(f"API Key de {prov}: ").strip()
            cfg.setdefault("api_keys", {})[prov] = api_key
            with open(CONFIG, "w", encoding="utf-8") as f:
                json.dump({k:v for k,v in cfg.items() if not k.startswith("telegram_")}, f, indent=2)
        guardar_bot_cfg({"telegram_proveedor": prov, "telegram_modelo": modelo})

    print("\n✅ Configuración guardada.")
    print("💡 Cuando inicies el bot por primera vez en Telegram, anota tu Chat ID")
    print("   y añádelo a 'telegram_allowed_chats' en telegram_config.json")
    print("   para restringir el acceso solo a ti.\n")
    return True

def main():
    cfg = cargar_cfg()
    if not cfg.get("telegram_bot_token"):
        print("⚠️ Bot no configurado. Iniciando setup...")
        if not setup_interactivo():
            input("Pulsa Enter para salir..."); return
    bot = NovaTelegramBot()
    try:
        bot.loop()
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        input("Pulsa Enter para salir...")

if __name__ == "__main__":
    main()
