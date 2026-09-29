"""
Lee todos los .md de la carpeta "conocimiento" y los carga a ChromaDB.

Formato esperado en cada .md (ver conocimiento/faq_prueba.md de ejemplo):

    ## P: pregunta
    R: respuesta (puede tener varias líneas, hasta el siguiente "## P:")

Se puede correr las veces que haga falta: primero borra la colección
y la vuelve a construir con lo que haya en los archivos en ese momento,
así nunca quedan preguntas viejas o duplicadas.

Uso:   python cargar_conocimiento.py
"""
import glob
import hashlib
import re

import chromadb

CARPETA = "conocimiento"
NOMBRE_COLECCION = "conocimiento_itcha"


def leer_bloques(texto):
    """Parte un .md en bloques (pregunta, respuesta). Ignora lo que esté
    antes de la primera "## P:" (por ejemplo, el comentario de instrucciones)."""
    partes = re.split(r"^##\s*P:\s*", texto, flags=re.MULTILINE)[1:]
    bloques = []
    for parte in partes:
        pregunta, _, resto = parte.partition("\n")
        m = re.search(r"^R:\s*(.*)", resto, flags=re.DOTALL)
        if not m:
            print(f"  Aviso: la pregunta «{pregunta.strip()}» no tiene una línea 'R:', se ignora.")
            continue
        respuesta = m.group(1).strip()
        bloques.append((pregunta.strip(), respuesta))
    return bloques


def cargar():
    client = chromadb.PersistentClient(path="./chroma_db")
    try:
        client.delete_collection(NOMBRE_COLECCION)
    except Exception:
        pass  # todavía no existía, no hay nada que borrar
    coleccion = client.get_or_create_collection(name=NOMBRE_COLECCION)

    documentos, metadatos, ids = [], [], []
    archivos = sorted(glob.glob(f"{CARPETA}/*.md"))
    if not archivos:
        print(f"No encontré ningún .md en la carpeta '{CARPETA}'.")
        return

    for archivo in archivos:
        with open(archivo, encoding="utf-8") as f:
            texto = f.read()
        bloques = leer_bloques(texto)
        print(f"{archivo}: {len(bloques)} preguntas")
        for pregunta, respuesta in bloques:
            # Guardamos pregunta + respuesta juntas: así, aunque la búsqueda
            # encuentre el chunk por la pregunta, el modelo recibe también su
            # respuesta ya lista para usar.
            documentos.append(f"Pregunta: {pregunta}\nRespuesta: {respuesta}")
            metadatos.append({"archivo": archivo, "pregunta": pregunta})
            ids.append(hashlib.md5(f"{archivo}|{pregunta}".encode()).hexdigest())

    if documentos:
        coleccion.add(documents=documentos, metadatas=metadatos, ids=ids)
    print(f"\nListo: {len(documentos)} preguntas cargadas en la colección '{NOMBRE_COLECCION}'.")


if __name__ == "__main__":
    cargar()