"""
nova_updater.py - Sistema de actualizaciones para NOVA AI
==========================================================
Comprueba nuevas versiones de cualquier modulo NOVA y las descarga.

Uso:
    from nova_updater import Updater
    updater = Updater(modulo="jarvis", version_actual="2.0.0")
    info = updater.comprobar()
    if info["disponible"]:
        print(f"Nueva version {info['version']}: {info['changelog']}")
        updater.actualizar()  # descarga y reemplaza archivos

Configura la URL del manifest en NOVA_MANIFEST_URL abajo.
Por defecto usa GitHub (repo aqdriop/nova-ai-updates).
"""
import os, sys, json, urllib.request, urllib.error, hashlib, shutil
from datetime import datetime

# ============================================================
# CONFIGURACION
# ============================================================
# URL del manifest de versiones (JSON alojado en GitHub Raw)
# Cambia esto si tienes tu propio repo
NOVA_MANIFEST_URL = ("https://raw.githubusercontent.com/aqdriop/"
                      "Nova-Studios/main/manifest.json")

# URL base para descargar archivos
NOVA_FILES_BASE = ("https://raw.githubusercontent.com/aqdriop/"
                    "Nova-Studios/main/files/")

# Cache local del manifest (para no re-consultar en cada arranque)
CACHE_HOURS = 6  # consultar como maximo cada 6 horas

USER_AGENT = "NovaUpdater/1.0"


# ============================================================
# HELPERS
# ============================================================
def _cache_file(modulo):
    """Archivo cache local para un modulo."""
    app_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(app_dir, f".update_cache_{modulo}.json")


def _comparar_versiones(v1, v2):
    """Compara dos versiones semver. Devuelve 1 si v1>v2, 0 si iguales, -1 si v1<v2."""
    def norm(v):
        try:
            return [int(x) for x in v.strip().split(".")]
        except Exception:
            return [0]
    a, b = norm(v1), norm(v2)
    # Igualar longitud
    while len(a) < len(b): a.append(0)
    while len(b) < len(a): b.append(0)
    if a > b: return 1
    if a < b: return -1
    return 0


def _descargar_url(url, timeout=30):
    """Descarga contenido de una URL."""
    req = urllib.request.Request(url,
        headers={"User-Agent": USER_AGENT,
                 "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _descargar_json(url, timeout=15):
    """Descarga y parsea un JSON."""
    data = _descargar_url(url, timeout)
    return json.loads(data.decode("utf-8"))


def _hash_archivo(ruta):
    """SHA256 de un archivo local."""
    if not os.path.exists(ruta):
        return None
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ============================================================
# CLASE UPDATER
# ============================================================
class Updater:
    """Gestiona actualizaciones de un modulo NOVA."""

    def __init__(self, modulo, version_actual, carpeta_destino=None,
                    manifest_url=None):
        """
        modulo: nombre del modulo (ej: "jarvis", "translator", "office")
        version_actual: version actual instalada (ej: "2.0.0")
        carpeta_destino: donde actualizar (default: carpeta del script)
        """
        self.modulo = modulo
        self.version_actual = version_actual
        self.manifest_url = manifest_url or NOVA_MANIFEST_URL
        if carpeta_destino:
            self.carpeta = carpeta_destino
        else:
            # Por defecto, la carpeta del script que llame a esto
            self.carpeta = os.path.dirname(os.path.abspath(sys.argv[0]))

        self.info_ultima = None  # resultado de la ultima comprobacion

    # ========================================================
    # COMPROBAR
    # ========================================================
    def comprobar(self, forzar=False):
        """
        Comprueba si hay una nueva version.
        Devuelve dict:
            {
                "disponible": bool,
                "version": "2.1.0",
                "changelog": "...",
                "archivos": [{"nombre":..., "hash":..., "url":...}, ...],
                "error": "..." o None
            }
        """
        # Cache
        cache_path = _cache_file(self.modulo)
        if not forzar and os.path.exists(cache_path):
            edad = (datetime.now().timestamp() -
                    os.path.getmtime(cache_path)) / 3600
            if edad < CACHE_HOURS:
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        self.info_ultima = json.load(f)
                    return self.info_ultima
                except Exception:
                    pass

        # Descargar manifest
        try:
            manifest = _descargar_json(self.manifest_url)
        except urllib.error.HTTPError as e:
            return self._resultado_error(f"HTTP {e.code}: {e.reason}")
        except Exception as e:
            return self._resultado_error(f"Sin conexion: {e}")

        # Buscar el modulo en el manifest
        modulos = manifest.get("modulos", {})
        info_mod = modulos.get(self.modulo)
        if not info_mod:
            return self._resultado_error(
                f"Modulo '{self.modulo}' no esta en el manifest")

        version_remota = info_mod.get("version", "0.0.0")
        cmp = _comparar_versiones(version_remota, self.version_actual)

        resultado = {
            "disponible": cmp > 0,
            "version": version_remota,
            "version_actual": self.version_actual,
            "changelog": info_mod.get("changelog", ""),
            "archivos": info_mod.get("archivos", []),
            "fecha": info_mod.get("fecha", ""),
            "error": None,
        }

        # Guardar cache
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(resultado, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        self.info_ultima = resultado
        return resultado

    def _resultado_error(self, mensaje):
        return {
            "disponible": False,
            "version": self.version_actual,
            "version_actual": self.version_actual,
            "changelog": "",
            "archivos": [],
            "error": mensaje,
        }

    # ========================================================
    # ACTUALIZAR
    # ========================================================
    def actualizar(self, progress=None, backup=True):
        """
        Descarga y aplica los archivos nuevos.
        progress(archivo, indice, total): callback opcional.
        Devuelve dict:
            {
                "ok": bool,
                "actualizados": [nombres],
                "fallidos": [nombres],
                "backup_dir": ruta,
                "error": "..." o None
            }
        """
        if not self.info_ultima:
            self.comprobar()
        if not self.info_ultima or not self.info_ultima.get("disponible"):
            return {"ok": False, "actualizados": [], "fallidos": [],
                     "error": "No hay actualizacion disponible"}

        archivos = self.info_ultima.get("archivos", [])
        if not archivos:
            return {"ok": False, "actualizados": [], "fallidos": [],
                     "error": "El manifest no tiene archivos"}

        # === BACKUP ===
        backup_dir = None
        if backup:
            fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = os.path.join(self.carpeta,
                f".backup_{self.modulo}_{fecha}")
            os.makedirs(backup_dir, exist_ok=True)

        actualizados = []
        fallidos = []

        for i, archivo in enumerate(archivos):
            nombre = archivo.get("nombre")
            url = archivo.get("url") or (NOVA_FILES_BASE + nombre)
            if not nombre:
                continue

            if progress:
                try: progress(nombre, i + 1, len(archivos))
                except: pass

            ruta_local = os.path.join(self.carpeta, nombre)

            # Backup del archivo actual (si existe)
            if backup and os.path.exists(ruta_local):
                try:
                    shutil.copy2(ruta_local,
                        os.path.join(backup_dir, nombre))
                except Exception as e:
                    print(f"[Updater] Backup fallo para {nombre}: {e}")

            # Descargar
            try:
                data = _descargar_url(url, timeout=60)
            except Exception as e:
                fallidos.append(f"{nombre}: {e}")
                continue

            # Escribir
            try:
                # Crear directorios intermedios si el nombre lleva /
                os.makedirs(os.path.dirname(ruta_local) or ".",
                    exist_ok=True)
                with open(ruta_local, "wb") as f:
                    f.write(data)
                actualizados.append(nombre)
            except Exception as e:
                fallidos.append(f"{nombre}: {e}")

        # Invalidar cache para que la proxima vez consulte de nuevo
        try:
            cp = _cache_file(self.modulo)
            if os.path.exists(cp):
                os.unlink(cp)
        except Exception:
            pass

        return {
            "ok": len(fallidos) == 0,
            "actualizados": actualizados,
            "fallidos": fallidos,
            "backup_dir": backup_dir,
            "error": None if not fallidos else f"{len(fallidos)} fallos",
        }


# ============================================================
# HELPER DE UI TKINTER (opcional)
# ============================================================
def mostrar_dialogo_update(root, modulo, version_actual, manifest_url=None,
                              on_actualizar=None):
    """
    Comprueba y muestra un dialogo bonito si hay actualizacion.
    Se puede llamar desde cualquier modulo NOVA.
    Devuelve True si el usuario actualizo, False si no.
    """
    import tkinter as tk
    from tkinter import messagebox, scrolledtext
    import threading

    updater = Updater(modulo, version_actual, manifest_url=manifest_url)

    def hacer_check_bg():
        info = updater.comprobar()
        root.after(0, lambda: _tras_check(info))

    def _tras_check(info):
        if info.get("error"):
            print(f"[Updater] {info['error']}")
            return
        if not info.get("disponible"):
            return  # no hay update

        # Mostrar dialogo
        dlg = tk.Toplevel(root)
        dlg.title(f"🆕 Actualizacion disponible para {modulo}")
        dlg.geometry("560x460")
        dlg.configure(bg="#1e293b")
        dlg.transient(root)
        dlg.grab_set()

        # Header con emoji
        tk.Label(dlg, text=f"🆕 UPDATE: NOVA {modulo.capitalize()}",
            bg="#1e293b", fg="#22c55e",
            font=("Segoe UI", 16, "bold")).pack(pady=(16, 4))

        tk.Label(dlg,
            text=f"Version actual: {info['version_actual']}   →   Nueva: {info['version']}",
            bg="#1e293b", fg="#94a3b8",
            font=("Segoe UI", 10)).pack(pady=2)

        if info.get("fecha"):
            tk.Label(dlg, text=f"Publicada: {info['fecha']}",
                bg="#1e293b", fg="#64748b",
                font=("Segoe UI", 9, "italic")).pack(pady=2)

        # Changelog
        tk.Label(dlg, text="Novedades:",
            bg="#1e293b", fg="#a78bfa",
            font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=20, pady=(12, 4))

        txt = scrolledtext.ScrolledText(dlg,
            bg="#0d1729", fg="#f1f5f9",
            font=("Consolas", 10), wrap="word",
            relief="flat", padx=12, pady=12, height=12)
        txt.pack(fill="both", expand=True, padx=20, pady=6)
        txt.insert("1.0", info.get("changelog", "(sin changelog)"))
        txt.config(state="disabled")

        # Botones
        bf = tk.Frame(dlg, bg="#1e293b")
        bf.pack(pady=14)

        def hacer_update():
            dlg.destroy()
            # Ventana de progreso
            prog_dlg = tk.Toplevel(root)
            prog_dlg.title("Actualizando...")
            prog_dlg.geometry("400x180")
            prog_dlg.configure(bg="#1e293b")
            prog_dlg.transient(root)
            prog_dlg.grab_set()

            tk.Label(prog_dlg, text="⏳ Descargando archivos...",
                bg="#1e293b", fg="#22c55e",
                font=("Segoe UI", 12, "bold")).pack(pady=20)

            lbl_actual = tk.Label(prog_dlg, text="",
                bg="#1e293b", fg="#94a3b8",
                font=("Segoe UI", 10))
            lbl_actual.pack(pady=4)

            bar_bg = tk.Frame(prog_dlg, bg="#0d1729", height=20)
            bar_bg.pack(fill="x", padx=30, pady=10)
            bar_bg.pack_propagate(False)
            bar_fill = tk.Frame(bar_bg, bg="#22c55e")
            bar_fill.place(x=0, y=0, relheight=1, relwidth=0)

            def prog(archivo, i, total):
                pct = i / total
                root.after(0, lambda: lbl_actual.config(
                    text=f"[{i}/{total}] {archivo}"))
                root.after(0, lambda: bar_fill.place(
                    x=0, y=0, relheight=1, relwidth=pct))

            def tarea_update():
                res = updater.actualizar(progress=prog, backup=True)
                root.after(0, lambda: _mostrar_resultado(prog_dlg, res))

            threading.Thread(target=tarea_update, daemon=True).start()

            if on_actualizar:
                try: on_actualizar()
                except: pass

        tk.Button(bf, text="🚀 Actualizar ahora",
            command=hacer_update,
            bg="#22c55e", fg="white", relief="flat",
            font=("Segoe UI", 11, "bold"),
            padx=20, pady=8, cursor="hand2"
            ).pack(side="left", padx=6)

        tk.Button(bf, text="Mas tarde",
            command=dlg.destroy,
            bg="#334155", fg="#f1f5f9", relief="flat",
            font=("Segoe UI", 10),
            padx=16, pady=8, cursor="hand2"
            ).pack(side="left", padx=6)

    def _mostrar_resultado(prog_dlg, res):
        prog_dlg.destroy()
        if res.get("ok"):
            n = len(res.get("actualizados", []))
            backup = res.get("backup_dir", "")
            messagebox.showinfo("✅ Actualizado",
                f"Actualizados {n} archivos correctamente.\n\n"
                f"Se hizo backup en:\n{backup}\n\n"
                "REINICIA el modulo para aplicar los cambios.")
        else:
            fallidos = res.get("fallidos", [])
            messagebox.showerror("❌ Error",
                f"La actualizacion fallo:\n\n"
                f"Actualizados: {len(res.get('actualizados', []))}\n"
                f"Fallidos: {len(fallidos)}\n\n"
                + "\n".join(f"  - {f}" for f in fallidos[:5]))

    threading.Thread(target=hacer_check_bg, daemon=True).start()


# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    print("Test de nova_updater")
    updater = Updater("jarvis", "2.0.0")
    print(f"Consultando: {updater.manifest_url}")
    info = updater.comprobar()
    print(f"Resultado: {json.dumps(info, indent=2, ensure_ascii=False)}")
