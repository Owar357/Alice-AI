"""
Modelo de embeddings compartido por cargar_conocimiento.py y buscar_conocimiento.py.

Los dos tienen que usar EXACTAMENTE el mismo modelo, porque ChromaDB guarda los
vectores con el tamaño que da este modelo: si al cargar usas uno y al buscar
usas otro, las búsquedas fallan o dan resultados sin sentido. Por eso está en
un solo archivo que ambos importan, en vez de repetir la configuración en cada uno.

Se usa un modelo multilingüe más grande que el que trae ChromaDB por defecto,
para que entienda mejor el español y reconozca preguntas casi idénticas con
más confiabilidad. La primera vez que se use, descarga el modelo de internet
(unos cientos de MB); después queda en caché y funciona sin conexión.
"""
import os

# Una vez que el modelo ya está descargado (la primera vez que corriste
# cargar_conocimiento.py), esto evita que la librería intente conectarse a
# internet en cada arranque. Quita también el aviso de "HF_TOKEN".
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

NOMBRE_MODELO = "paraphrase-multilingual-MiniLM-L12-v2"

_funcion = None


def obtener_funcion_embeddings():
    global _funcion
    if _funcion is None:
        _funcion = SentenceTransformerEmbeddingFunction(model_name=NOMBRE_MODELO)
    return _funcion