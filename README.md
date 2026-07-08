# 🔄 NOVA AI — Sistema de actualizaciones

Este es el **repositorio de updates** para el ecosistema NOVA AI. Aquí publicas nuevas versiones y **todos los usuarios las reciben automáticamente** al abrir sus módulos.

## 🚀 Cómo funciona (visión general)

1. Los módulos de NOVA (Jarvis, Translator, etc.) tienen una `VERSION` local
2. Cada vez que arrancan, consultan el `manifest.json` de este repo
3. Si la versión remota es mayor, muestran **"🆕 UPDATE disponible"** al usuario
4. Al pulsar "Actualizar", descargan los archivos nuevos automáticamente
5. Se hace **backup** de los archivos antiguos por si algo falla
6. El usuario **reinicia** el módulo y ya tiene la nueva versión

## 📦 Estructura del repo

```
nova-ai-updates/           ← este repo en GitHub
├── manifest.json          ← el índice de versiones (LO IMPORTANTE)
└── files/                 ← los .py actualizados
    ├── jarvis/
    │   ├── nova_jarvis.py
    │   ├── nova_personalidades.py
    │   └── nova_musica.py
    ├── translator/
    │   └── nova_translator.py
    ├── office/
    │   └── nova_office.py
    ├── shared/
    │   └── nova_ia_lib.py   ← este afecta a TODOS los módulos
    └── ... (uno por módulo)
```

## ✍️ Publicar una nueva versión (proceso paso a paso)

Imagina que has mejorado NOVA Jarvis y quieres publicar la v2.1.0:

### 1. Sube el archivo actualizado

Ve a tu repo GitHub y sube el nuevo `nova_jarvis.py` a:
```
files/jarvis/nova_jarvis.py
```

Puedes hacerlo desde la web de GitHub (drag & drop) o con git:
```bash
git add files/jarvis/nova_jarvis.py
git commit -m "Jarvis v2.1.0"
git push
```

### 2. Actualiza `manifest.json`

Edita el `manifest.json` (desde GitHub Web es fácil) y cambia:

```json
"jarvis": {
  "version": "2.1.0",   ← incrementa el número
  "fecha": "2026-07-06",
  "changelog": "🎉 v2.1.0 - MEJORAS NUEVAS\n\n✨ Cambios:\n- Añadido X\n- Arreglado Y\n- Mejorado Z"
  ...
}
```

**Reglas semver**:
- `1.0.0 → 1.0.1` — bugfix (arreglos menores)
- `1.0.0 → 1.1.0` — features nuevas (retrocompatible)
- `1.0.0 → 2.0.0` — cambio grande (puede romper cosas)

### 3. Guarda el commit

Los usuarios verán el update en las siguientes **6 horas** (cache), o al instante si pulsan el botón "🆕 Update" manualmente.

## 🔧 Configurar el repo (primera vez)

### Opción A: usar el repo por defecto (`aqdriop/nova-ai-updates`)
Si vas a ser el mantenedor oficial, crea el repo:

1. Ve a https://github.com/new
2. Nombre: `nova-ai-updates`
3. Public
4. Add README
5. Create repository

Luego sube:
- `manifest.json` (el que hay en esta carpeta)
- Carpeta `files/` con los .py actualizados

### Opción B: usar TU PROPIO repo
Cambia la URL en `nova_updater.py` (línea `NOVA_MANIFEST_URL`) por la tuya:

```python
NOVA_MANIFEST_URL = "https://raw.githubusercontent.com/TU_USUARIO/TU_REPO/main/manifest.json"
NOVA_FILES_BASE = "https://raw.githubusercontent.com/TU_USUARIO/TU_REPO/main/files/"
```

## 🎁 Multi-archivo por módulo

Un módulo puede tener MÚLTIPLES archivos:

```json
"jarvis": {
  "version": "2.1.0",
  "archivos": [
    {"nombre": "nova_jarvis.py", "url": "..."},
    {"nombre": "nova_personalidades.py", "url": "..."},
    {"nombre": "nova_musica.py", "url": "..."}
  ]
}
```

Todos se descargarán juntos.

## 🛡️ Sistema de backup

Antes de actualizar, se hace **backup automático** en:
```
Nova Jarvis/.backup_jarvis_20260706_143022/
    nova_jarvis.py       ← el archivo antiguo
```

Si algo va mal después del update:
1. Cierra el módulo
2. Copia los archivos del backup a la carpeta principal
3. Vuelve a abrir

## 🔒 Seguridad

- Los archivos se descargan desde **raw.githubusercontent.com** (HTTPS)
- Se **muestra el changelog** ANTES de actualizar (el usuario decide)
- Se hace **backup** antes de sobrescribir nada
- **NO se ejecuta** ningún código durante la descarga

## 💡 Trucos avanzados

### Verificar hashes (opcional)
Añade `"hash"` en el manifest para verificar integridad:
```json
{
  "nombre": "nova_jarvis.py",
  "hash": "sha256_del_archivo",
  "url": "..."
}
```

### Forzar update en todos
Cambia la versión aunque no haya cambios significativos y todos los usuarios recibirán la notificación.

### Cache de 6 horas
Los usuarios comprueban updates cada 6h por defecto. Si quieres reducir eso, edita `CACHE_HOURS` en `nova_updater.py`.

### Rollback
Si publicas una versión rota, sube una nueva versión más alta con la corrección. NO bajes versiones (los usuarios ya tienen la "nueva").

## 📊 Estado actual

Módulos incluidos en el manifest:
- 🤖 jarvis (2.0.0)
- 🌍 translator (1.0.0)
- 💼 office (1.0.0)
- 🎓 coach (1.0.0)
- 🎬 studio (1.0.0)
- 📖 reader (1.0.0)
- 🔍 search (1.0.0)
- 🎮 game_master (1.0.0)
- 🧠 brain_hub (1.0.0)
- 📱 telegram (1.0.0)
- 🔗 ia_lib (2.0.0) — librería compartida

## 🎯 Ejemplo de flujo real

**Tú (mantenedor):**
1. Arreglas un bug en `nova_jarvis.py`
2. Subes el archivo a `files/jarvis/nova_jarvis.py`
3. Actualizas manifest: `"version": "2.0.1"`
4. Commit + push

**Usuario:**
1. Abre Jarvis
2. A los 3 segundos ve en el chat: `🆕 UPDATE: Version 2.0.1 disponible`
3. Pulsa el botón "🆕 Update" en la cabecera
4. Ve el changelog con las mejoras
5. Pulsa "Actualizar ahora"
6. Se descarga, se hace backup
7. Reinicia → tiene la última versión ✅

Todo en 30 segundos, sin re-instalar nada. 🚀
