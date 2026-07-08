"""
nova_brain.py - Memoria/cerebro compartido del ecosistema NOVA AI
==================================================================
Un unico almacen persistente que TODOS los modulos leen/escriben.
Guardado en: AsistenteIA/nova_brain.json

Estructura:
{
  "perfil": {
    "nombre": "...", "edad": "...", "email": "...", "ciudad": "...",
    "profesion": "...", "idioma": "es", ...
  },
  "preferencias": {
    "tema": "dark", "voz_activada": true, "voz_id": "...",
    "proveedor_favorito": "Groq", ...
  },
  "hechos": [
    {"texto": "...", "fecha": "...", "modulo": "jarvis"},
    ...
  ],
  "eventos": [
    {"tipo": "documento_creado", "modulo": "office",
     "data": {"tipo": "word", "titulo": "..."}, "fecha": "..."},
    ...
  ],
  "stats": {"jarvis": {"conversaciones": 42, ...}, ...}
}

Uso:
    from nova_brain import Brain
    b = Brain()
    b.perfil("nombre", "Adrian")
    b.recordar("Le gusta la paella", modulo="jarvis")
    b.evento("documento_creado", "office", {"tipo": "word", "titulo": "Ensayo"})
    b.stat("jarvis", "conversaciones", incrementar=1)
    print(b.perfil("nombre"))          # "Adrian"
    print(b.hechos_recientes(5))       # ultimos 5 hechos
"""
import os, json, threading
from datetime import datetime

# ============================================================
# Localizacion del archivo compartido
# ============================================================
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
# Si estamos en un subfolder de AsistenteIA, sube un nivel
_MAYBE_PARENT = os.path.dirname(_APP_DIR)
if os.path.exists(os.path.join(_MAYBE_PARENT, "asistente.py")) or \
   os.path.basename(_MAYBE_PARENT) == "AsistenteIA":
    BRAIN_FILE = os.path.join(_MAYBE_PARENT, "nova_brain.json")
else:
    BRAIN_FILE = os.path.join(_APP_DIR, "nova_brain.json")


# ============================================================
# CEREBRO
# ============================================================
class Brain:
    """Singleton (mas o menos) que gestiona el estado global compartido."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self.datos = self._cargar()

    def _cargar(self):
        if os.path.exists(BRAIN_FILE):
            try:
                with open(BRAIN_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                # Asegurar estructura minima
                d.setdefault("perfil", {})
                d.setdefault("preferencias", {})
                d.setdefault("hechos", [])
                d.setdefault("eventos", [])
                d.setdefault("stats", {})
                return d
            except Exception as e:
                print(f"[Brain] Error cargando: {e}")
        return {
            "perfil": {}, "preferencias": {},
            "hechos": [], "eventos": [], "stats": {},
            "creado": datetime.now().isoformat(),
        }

    def guardar(self):
        try:
            with open(BRAIN_FILE, "w", encoding="utf-8") as f:
                json.dump(self.datos, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Brain] Error guardando: {e}")

    def recargar(self):
        """Fuerza recarga desde disco (util si otro modulo modifico)."""
        self.datos = self._cargar()

    # ========================================================
    # PERFIL DEL USUARIO
    # ========================================================
    def perfil(self, campo=None, valor=None):
        """Get/set del perfil del usuario."""
        if campo is None:
            return dict(self.datos["perfil"])
        if valor is None:
            return self.datos["perfil"].get(campo, "")
        self.datos["perfil"][campo] = valor
        self.guardar()
        return valor

    def perfil_multi(self, **kwargs):
        """Guarda multiples campos de golpe."""
        self.datos["perfil"].update(kwargs)
        self.guardar()

    # ========================================================
    # PREFERENCIAS
    # ========================================================
    def pref(self, clave, valor=None, default=None):
        """Get/set de preferencia."""
        if valor is None:
            return self.datos["preferencias"].get(clave, default)
        self.datos["preferencias"][clave] = valor
        self.guardar()
        return valor

    # ========================================================
    # HECHOS (memoria semantica)
    # ========================================================
    def recordar(self, texto, modulo="general"):
        """Guarda un hecho en la memoria."""
        self.datos["hechos"].append({
            "texto": texto,
            "modulo": modulo,
            "fecha": datetime.now().isoformat(),
        })
        # Limitar a 500 hechos
        if len(self.datos["hechos"]) > 500:
            self.datos["hechos"] = self.datos["hechos"][-500:]
        self.guardar()

    def olvidar(self, indice):
        try:
            del self.datos["hechos"][int(indice)]
            self.guardar()
            return True
        except Exception:
            return False

    def hechos_recientes(self, n=10):
        return self.datos["hechos"][-n:]

    def hechos_por_modulo(self, modulo, n=None):
        h = [f for f in self.datos["hechos"] if f.get("modulo") == modulo]
        return h[-n:] if n else h

    def buscar_hechos(self, palabra):
        """Busca hechos que contengan la palabra."""
        p = palabra.lower()
        return [h for h in self.datos["hechos"] if p in h["texto"].lower()]

    def resumen_hechos_para_ia(self, n=20):
        """Devuelve string con hechos formateado para inyectar en system prompt."""
        h = self.hechos_recientes(n)
        if not h:
            return ""
        lineas = ["HECHOS QUE RECUERDO SOBRE EL USUARIO:"]
        for f in h:
            lineas.append(f"  - {f['texto']}")
        return "\n".join(lineas) + "\n"

    # ========================================================
    # EVENTOS (para conectar modulos entre si)
    # ========================================================
    def evento(self, tipo, modulo, data=None):
        """Registra un evento (ej: documento_creado, imagen_generada)."""
        self.datos["eventos"].append({
            "tipo": tipo, "modulo": modulo,
            "data": data or {},
            "fecha": datetime.now().isoformat(),
        })
        if len(self.datos["eventos"]) > 300:
            self.datos["eventos"] = self.datos["eventos"][-300:]
        self.guardar()

    def eventos_recientes(self, n=20, tipo=None, modulo=None):
        ev = self.datos["eventos"]
        if tipo:
            ev = [e for e in ev if e["tipo"] == tipo]
        if modulo:
            ev = [e for e in ev if e["modulo"] == modulo]
        return ev[-n:]

    # ========================================================
    # ESTADISTICAS
    # ========================================================
    def stat(self, modulo, clave, valor=None, incrementar=None):
        s = self.datos["stats"].setdefault(modulo, {})
        if incrementar is not None:
            s[clave] = s.get(clave, 0) + incrementar
            self.guardar()
            return s[clave]
        if valor is not None:
            s[clave] = valor
            self.guardar()
            return valor
        return s.get(clave, 0)

    def stats_modulo(self, modulo):
        return dict(self.datos["stats"].get(modulo, {}))

    def stats_totales(self):
        return {m: dict(v) for m, v in self.datos["stats"].items()}


# ============================================================
# DETECTOR AUTOMATICO DE HECHOS (util para Jarvis/otros)
# ============================================================
import re

_PATRONES_HECHOS = [
    (r"(?:me llamo|mi nombre es)\s+([A-Za-zÀ-ÿ]+)", "nombre"),
    (r"vivo en\s+([A-Za-zÀ-ÿ\s]+?)(?:\.|$|,)", "ciudad"),
    (r"soy (?:de|del)\s+([A-Za-zÀ-ÿ\s]+?)(?:\.|$|,)", "origen"),
    (r"tengo\s+(\d+)\s+años", "edad"),
    (r"mi email es\s+(\S+@\S+)", "email"),
    (r"mi telefono es\s+([\d\s\+\-]+)", "telefono"),
    (r"trabajo (?:de|como)\s+([A-Za-zÀ-ÿ\s]+?)(?:\.|$|,)", "profesion"),
]

def extraer_hechos(texto):
    """Analiza un texto y extrae hechos estructurados."""
    hechos = []
    t = texto.lower()
    for patron, campo in _PATRONES_HECHOS:
        for m in re.finditer(patron, t, re.IGNORECASE):
            valor = m.group(1).strip()
            hechos.append({"campo": campo, "valor": valor, "texto": m.group(0)})
    return hechos


# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    b = Brain()
    print(f"Archivo: {BRAIN_FILE}")
    print(f"Perfil actual: {b.perfil()}")
    print(f"Hechos: {len(b.datos['hechos'])}")

    # Test
    b.perfil("nombre", "Adrian")
    b.perfil("ciudad", "Cordoba")
    b.recordar("Le gusta el codigo Python", modulo="jarvis")
    b.evento("test", "brain_test", {"ok": True})
    b.stat("brain_test", "runs", incrementar=1)

    print(f"Nombre: {b.perfil('nombre')}")
    print(f"Hechos recientes: {b.hechos_recientes(3)}")
    print(f"Stats: {b.stats_totales()}")

    # Test detector
    txt = "Hola, me llamo Ana, vivo en Sevilla y tengo 27 años"
    print(f"\nExtraidos de '{txt}':")
    for h in extraer_hechos(txt):
        print(f"  {h}")
