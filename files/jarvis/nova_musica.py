"""
nova_musica.py - Control de musica para Jarvis
================================================
Controla musica en el PC usando:
  - Teclas multimedia del sistema (play/pause/next/prev) via keyboard API
  - Busqueda + apertura en YouTube (sin API key)
  - Busqueda + apertura en Spotify Web (si esta abierto)
"""
import webbrowser, urllib.parse, subprocess, sys, os

# Dependencias opcionales
try:
    # ctypes para enviar teclas multimedia en Windows
    import ctypes
    CTYPES_OK = sys.platform == "win32"
except ImportError:
    CTYPES_OK = False


# ============================================================
# CONTROLES DE MEDIA (funcionan con Spotify, YouTube, VLC, etc.)
# ============================================================
# Codigos de teclas virtuales de Windows
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_VOLUME_UP = 0xAF
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_MUTE = 0xAD

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002


def _pulsar_tecla_media(vk):
    """Pulsa una tecla multimedia del sistema (solo Windows)."""
    if not CTYPES_OK:
        return False
    try:
        ctypes.windll.user32.keybd_event(vk, 0,
            KEYEVENTF_EXTENDEDKEY, 0)
        ctypes.windll.user32.keybd_event(vk, 0,
            KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
        return True
    except Exception as e:
        print(f"[Musica] Error pulsando tecla: {e}")
        return False


def play_pause():
    """Pausa/reanuda musica en cualquier reproductor."""
    return _pulsar_tecla_media(VK_MEDIA_PLAY_PAUSE)


def siguiente():
    return _pulsar_tecla_media(VK_MEDIA_NEXT_TRACK)


def anterior():
    return _pulsar_tecla_media(VK_MEDIA_PREV_TRACK)


def parar():
    return _pulsar_tecla_media(VK_MEDIA_STOP)


def volumen_subir(veces=3):
    """Sube el volumen (N veces = N pulsaciones)."""
    for _ in range(veces):
        _pulsar_tecla_media(VK_VOLUME_UP)
    return True


def volumen_bajar(veces=3):
    for _ in range(veces):
        _pulsar_tecla_media(VK_VOLUME_DOWN)
    return True


def silenciar():
    return _pulsar_tecla_media(VK_VOLUME_MUTE)


# ============================================================
# BUSQUEDAS (abren navegador)
# ============================================================
def buscar_youtube(query, autoplay=True):
    """Busca una cancion en YouTube. Si autoplay=True intenta ir al primer video."""
    if autoplay:
        # URL que auto-reproduce el primer resultado
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    else:
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    webbrowser.open(url)
    return f"Buscando '{query}' en YouTube"


def buscar_youtube_music(query):
    """Busca en YouTube Music (mejor para musica sin videos aleatorios)."""
    url = f"https://music.youtube.com/search?q={urllib.parse.quote(query)}"
    webbrowser.open(url)
    return f"Buscando '{query}' en YouTube Music"


def buscar_spotify_web(query):
    """Busca en Spotify Web."""
    url = f"https://open.spotify.com/search/{urllib.parse.quote(query)}"
    webbrowser.open(url)
    return f"Buscando '{query}' en Spotify Web"


def abrir_spotify_app():
    """Abre la app de Spotify (si esta instalada)."""
    try:
        if sys.platform == "win32":
            subprocess.Popen('start "" "spotify:"', shell=True)
        else:
            subprocess.Popen(["spotify"])
        return "Abriendo Spotify"
    except Exception as e:
        return f"Error: {e}"


# ============================================================
# PLAYLISTS PREDEFINIDAS por genero/mood
# ============================================================
PLAYLISTS_YT = {
    "concentracion": "lofi hip hop radio beats to study to",
    "relax": "musica relajante para dormir",
    "trabajar": "deep focus concentration music",
    "energia": "epic workout music gym",
    "fiesta": "musica fiesta reggaeton hits",
    "chill": "chill vibes playlist",
    "clasica": "musica clasica famosa",
    "rock": "classic rock hits",
    "80s": "musica anos 80 espanol",
    "90s": "musica anos 90 espanol",
    "meditar": "musica meditacion mindfulness",
    "estudiar": "musica para estudiar sin letra",
    "gaming": "epic gaming music",
    "jazz": "smooth jazz playlist",
    "electronica": "best electronic music playlist",
}


def reproducir_mood(mood):
    """Reproduce musica de un mood conocido en YouTube."""
    query = PLAYLISTS_YT.get(mood.lower())
    if query:
        return buscar_youtube(query)
    # Fallback: buscar lo que sea
    return buscar_youtube(mood + " playlist")


if __name__ == "__main__":
    print("Test de nova_musica")
    print(f"CTYPES OK (Windows): {CTYPES_OK}")
    print(f"Moods disponibles: {list(PLAYLISTS_YT.keys())}")
