"""
nova_rag.py - RAG (Retrieval-Augmented Generation) para NOVA
=============================================================
Indexa una carpeta con documentos (PDF, TXT, DOCX, MD) y permite
hacer preguntas sobre su contenido, citando el fragmento fuente.

Uso:
    from nova_rag import NovaRAG
    rag = NovaRAG(carpeta_index="./mi_biblioteca")
    rag.indexar("/ruta/a/mis/documentos")  # una vez
    fragmentos = rag.buscar("que es la fotosintesis", top=3)
    # Cada fragmento: {"texto": ..., "fuente": ..., "score": 0.87}

    respuesta = rag.preguntar("resumen del capitulo 2",
                                llamar_llm_fn, prov, modelo, key)

No requiere librerias pesadas (usa TF-IDF + cosine similarity manual).
Si esta sentence-transformers instalado, usa embeddings semanticos.
"""
import os, json, re, math, hashlib
from datetime import datetime
from collections import Counter

# Dependencias opcionales para diferentes formatos
try:
    from PyPDF2 import PdfReader
    PDF_OK = True
except ImportError:
    PDF_OK = False

try:
    import docx as python_docx
    DOCX_OK = True
except ImportError:
    DOCX_OK = False

# Embeddings semanticos (opcional, mejor calidad)
try:
    from sentence_transformers import SentenceTransformer
    EMB_OK = True
    _modelo_emb = None
except ImportError:
    EMB_OK = False


# ============================================================
# UTILIDADES DE EXTRACCION
# ============================================================
def extraer_texto(ruta):
    """Extrae texto de un archivo segun su extension."""
    ext = os.path.splitext(ruta)[1].lower()
    try:
        if ext == ".pdf":
            if not PDF_OK: return ""
            r = PdfReader(ruta)
            return "\n".join(p.extract_text() or "" for p in r.pages)
        if ext in (".txt", ".md", ".py", ".js", ".html", ".css", ".json"):
            with open(ruta, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        if ext in (".docx",):
            if not DOCX_OK: return ""
            d = python_docx.Document(ruta)
            return "\n".join(p.text for p in d.paragraphs)
    except Exception as e:
        print(f"[RAG] Error leyendo {ruta}: {e}")
    return ""


def partir_en_chunks(texto, chunk_size=500, overlap=80):
    """Divide un texto largo en fragmentos con solape."""
    if not texto:
        return []
    palabras = texto.split()
    if len(palabras) <= chunk_size:
        return [texto]
    chunks = []
    i = 0
    while i < len(palabras):
        chunk = " ".join(palabras[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


# ============================================================
# TF-IDF simple (sin dependencias)
# ============================================================
def _tokenizar(texto):
    """Tokenizacion basica en espanol."""
    texto = texto.lower()
    # Quitar puntuacion basica
    texto = re.sub(r"[^\w\s]", " ", texto, flags=re.UNICODE)
    tokens = texto.split()
    # Quitar palabras muy cortas y stopwords muy basicas
    STOP = {"el","la","los","las","un","una","de","del","y","o","a","al","en",
            "por","para","que","se","es","son","con","su","sus","le","les",
            "lo","me","te","nos","si","no","como","mas","ya","muy","este",
            "esta","esto","the","a","of","and","to","in","for","is"}
    return [t for t in tokens if len(t) > 2 and t not in STOP]


def _cosine_similarity(a, b):
    """Similitud coseno entre dos dicts {palabra: frecuencia}."""
    if not a or not b: return 0.0
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if mag_a == 0 or mag_b == 0: return 0.0
    return dot / (mag_a * mag_b)


# ============================================================
# CLASE PRINCIPAL RAG
# ============================================================
class NovaRAG:
    """
    Indexa documentos y permite busqueda semantica sobre ellos.

    Estrategia:
    - Si sentence-transformers disponible: usa embeddings reales (mejor)
    - Si no: usa TF-IDF ponderado (rapido, funciona sin instalar nada)
    """

    def __init__(self, carpeta_index=None, usar_embeddings=None):
        if carpeta_index is None:
            carpeta_index = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "rag_index")
        os.makedirs(carpeta_index, exist_ok=True)
        self.carpeta_index = carpeta_index
        self.index_file = os.path.join(carpeta_index, "index.json")
        self.emb_file = os.path.join(carpeta_index, "embeddings.json")

        # Usar embeddings si esta disponible y se pide
        self.usar_embeddings = (usar_embeddings if usar_embeddings is not None
                                  else EMB_OK)

        self.chunks = []  # [{id, texto, fuente, tokens, vector?}]
        self._cargar()

    # ========================================================
    # PERSISTENCIA
    # ========================================================
    def _cargar(self):
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    self.chunks = json.load(f)
                # Recalcular Counter para busqueda
                for c in self.chunks:
                    if isinstance(c.get("tokens"), list):
                        c["tokens"] = Counter(c["tokens"])
            except Exception as e:
                print(f"[RAG] Error cargando: {e}")
                self.chunks = []

    def _guardar(self):
        try:
            # Convertir Counters a listas para guardar
            data = []
            for c in self.chunks:
                cc = dict(c)
                if isinstance(cc.get("tokens"), Counter):
                    # Guardar como dict expandido pero pequeño
                    cc["tokens"] = list(cc["tokens"].elements())[:200]
                data.append(cc)
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
        except Exception as e:
            print(f"[RAG] Error guardando: {e}")

    # ========================================================
    # INDEXACION
    # ========================================================
    def indexar(self, ruta_carpeta, reemplazar=False, progress=None):
        """
        Indexa recursivamente todos los documentos de una carpeta.
        progress(actual, total, nombre_archivo): callback opcional
        Devuelve (n_docs_indexados, n_chunks_totales).
        """
        if reemplazar:
            self.chunks = []

        ruta_carpeta = os.path.expanduser(ruta_carpeta)
        if not os.path.isdir(ruta_carpeta):
            return 0, 0

        # Recolectar archivos soportados
        archivos = []
        for raiz, _, files in os.walk(ruta_carpeta):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in (".pdf", ".txt", ".md", ".docx"):
                    archivos.append(os.path.join(raiz, f))

        total = len(archivos)
        docs_ok = 0

        for i, ruta in enumerate(archivos):
            if progress:
                try: progress(i + 1, total, os.path.basename(ruta))
                except Exception: pass

            texto = extraer_texto(ruta)
            if not texto or len(texto) < 50:
                continue

            fragmentos = partir_en_chunks(texto)
            for j, frag in enumerate(fragmentos):
                cid = hashlib.md5(f"{ruta}::{j}".encode()).hexdigest()[:12]
                self.chunks.append({
                    "id": cid,
                    "texto": frag,
                    "fuente": os.path.basename(ruta),
                    "ruta": ruta,
                    "chunk_idx": j,
                    "tokens": Counter(_tokenizar(frag)),
                })
            docs_ok += 1

        self._guardar()

        # Generar embeddings si toca
        if self.usar_embeddings and EMB_OK:
            self._generar_embeddings(progress)

        return docs_ok, len(self.chunks)

    def _generar_embeddings(self, progress=None):
        global _modelo_emb
        try:
            if _modelo_emb is None:
                _modelo_emb = SentenceTransformer(
                    "paraphrase-multilingual-MiniLM-L12-v2")
            textos = [c["texto"] for c in self.chunks]
            embs = _modelo_emb.encode(textos, show_progress_bar=False)
            for c, e in zip(self.chunks, embs):
                c["vector"] = e.tolist()
            self._guardar()
        except Exception as e:
            print(f"[RAG] Error generando embeddings: {e}")

    # ========================================================
    # BUSQUEDA
    # ========================================================
    def buscar(self, consulta, top=4):
        """Devuelve los fragmentos mas relevantes para la consulta."""
        if not self.chunks:
            return []

        # Si tenemos embeddings, usarlos
        if self.usar_embeddings and EMB_OK and self.chunks[0].get("vector"):
            return self._buscar_embeddings(consulta, top)

        # Fallback: TF-IDF simple
        return self._buscar_tfidf(consulta, top)

    def _buscar_tfidf(self, consulta, top):
        q_tokens = Counter(_tokenizar(consulta))
        if not q_tokens:
            return []

        scores = []
        for c in self.chunks:
            score = _cosine_similarity(q_tokens, c["tokens"])
            if score > 0:
                scores.append((score, c))

        scores.sort(key=lambda x: x[0], reverse=True)
        return [{"texto": c["texto"], "fuente": c["fuente"],
                  "score": round(s, 3)} for s, c in scores[:top]]

    def _buscar_embeddings(self, consulta, top):
        global _modelo_emb
        try:
            if _modelo_emb is None:
                _modelo_emb = SentenceTransformer(
                    "paraphrase-multilingual-MiniLM-L12-v2")
            q_vec = _modelo_emb.encode([consulta])[0]
            scores = []
            for c in self.chunks:
                if "vector" not in c: continue
                v = c["vector"]
                # Cosine similarity manual
                dot = sum(a * b for a, b in zip(q_vec, v))
                mag = math.sqrt(sum(a*a for a in q_vec)) * math.sqrt(sum(b*b for b in v))
                if mag > 0:
                    scores.append((dot / mag, c))
            scores.sort(key=lambda x: x[0], reverse=True)
            return [{"texto": c["texto"], "fuente": c["fuente"],
                      "score": round(float(s), 3)} for s, c in scores[:top]]
        except Exception as e:
            print(f"[RAG] Error busqueda embed: {e}")
            return self._buscar_tfidf(consulta, top)

    # ========================================================
    # PREGUNTA + LLM (RAG completo)
    # ========================================================
    def preguntar(self, consulta, llamar_llm_fn, proveedor, modelo, api_key,
                    top=4):
        """
        Hace una pregunta usando los fragmentos como contexto.
        Devuelve (respuesta, [fragmentos_usados]).
        """
        fragmentos = self.buscar(consulta, top=top)
        if not fragmentos:
            return "No he encontrado nada relevante en tus documentos.", []

        contexto = "\n\n".join(
            f"[Fragmento {i+1} de {f['fuente']}]\n{f['texto']}"
            for i, f in enumerate(fragmentos))

        system = (
            "Eres un asistente que responde preguntas basandose EXCLUSIVAMENTE "
            "en los fragmentos de documentos que se te proporcionan. "
            "Si la respuesta no esta en los fragmentos, di 'No lo encuentro "
            "en tus documentos'. Cita las fuentes al final entre corchetes.")
        user = (f"Fragmentos disponibles:\n\n{contexto}\n\n"
                f"Pregunta: {consulta}\n\n"
                f"Responde en espanol y cita las fuentes que uses.")

        resp, err = llamar_llm_fn(proveedor, modelo, api_key,
                                    system, user, timeout=90)
        if err:
            return f"Error: {err}", fragmentos
        return resp, fragmentos

    # ========================================================
    # GESTION
    # ========================================================
    def resumen(self):
        """Devuelve resumen del indice."""
        fuentes = set(c["fuente"] for c in self.chunks)
        return {
            "docs": len(fuentes),
            "chunks": len(self.chunks),
            "usa_embeddings": self.usar_embeddings and EMB_OK,
            "carpeta": self.carpeta_index,
        }

    def limpiar(self):
        """Borra el indice."""
        self.chunks = []
        if os.path.exists(self.index_file):
            os.unlink(self.index_file)


# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    print("Test de NovaRAG")
    print(f"  PDF: {'OK' if PDF_OK else 'FALTA (pip install PyPDF2)'}")
    print(f"  DOCX: {'OK' if DOCX_OK else 'FALTA (pip install python-docx)'}")
    print(f"  Embeddings: {'OK' if EMB_OK else 'opcional (pip install sentence-transformers)'}")

    rag = NovaRAG()
    print(f"\nResumen del indice: {rag.resumen()}")
    if rag.chunks:
        print("\nPrueba de busqueda 'ejemplo':")
        for r in rag.buscar("ejemplo"):
            print(f"  [{r['score']}] {r['fuente']}: {r['texto'][:80]}...")
