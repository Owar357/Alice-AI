"""
Lee todos los .md de la carpeta "conocimiento" y los carga a ChromaDB.

Formato esperado en cada .md (ver los ejemplos de esa carpeta):

    ## Título corto del tema
    Categoría: nombre de la categoría          (opcional)

    Pregunta principal: la pregunta tal cual

    Preguntas similares:                        (opcional, una por línea con "- ")
    - otra forma de preguntar lo mismo
    - otra forma más, con errores de escritura si hace falta

    Palabras clave: palabra uno, palabra dos    (opcional)

    Respuesta: la respuesta real, puede tener
    varias líneas, hasta el siguiente "## título".

Solo "Pregunta principal" y "Respuesta" son obligatorias; el resto ayuda a que
la búsqueda encuentre la pregunta aunque alguien la haga con otras palabras.

Se puede correr las veces que haga falta: primero borra la colección
y la vuelve a construir con lo que haya en los archivos en ese momento,
así nunca quedan preguntas viejas o duplicadas.

Uso:   python cargar_conocimiento.py
"""
import glob
import hashlib
import re

import chromadb

import embeddings

CARPETA = "conocimiento"
NOMBRE_COLECCION = "conocimiento_itcha"


def _parsear_campos(titulo, cuerpo):
    """Saca pregunta, categoría, variantes, palabras clave y respuesta del
    cuerpo de un bloque. Devuelve None si falta la pregunta o la respuesta."""
    pregunta = categoria = palabras_clave = None
    variantes = []
    respuesta_lineas = []
    seccion = None  # None | "variantes" | "respuesta"

    for linea in cuerpo.split("\n"):
        m = re.match(r"^Categ(?:oría|oria):\s*(.*)$", linea)
        if m:
            categoria = m.group(1).strip()
            seccion = None
            continue
        m = re.match(r"^Pregunta(?:\s+principal)?:\s*(.*)$", linea)
        if m:
            pregunta = m.group(1).strip()
            seccion = None
            continue
        if re.match(r"^(?:Preguntas similares|Variantes):\s*$", linea):
            seccion = "variantes"
            continue
        m = re.match(r"^Palabras clave:\s*(.*)$", linea)
        if m:
            palabras_clave = m.group(1).strip()
            seccion = None
            continue
        m = re.match(r"^R(?:espuesta)?:\s*(.*)$", linea)
        if m:
            seccion = "respuesta"
            if m.group(1).strip():
                respuesta_lineas.append(m.group(1))
            continue

        if seccion == "variantes":
            m2 = re.match(r"^[-•●]\s*(.+)$", linea)
            if m2:
                variantes.append(m2.group(1).strip())
        elif seccion == "respuesta":
            respuesta_lineas.append(linea)

    respuesta = "\n".join(respuesta_lineas).strip()
    if not pregunta or not respuesta:
        print(f"  Aviso: el bloque «{titulo}» no tiene pregunta principal y/o respuesta, se ignora.")
        return None

    return {
        "titulo": titulo,
        "categoria": categoria,
        "pregunta": pregunta,
        "variantes": variantes,
        "palabras_clave": palabras_clave,
        "respuesta": respuesta,
    }


def leer_bloques(texto):
    """Parte un .md en bloques, uno por cada encabezado '## '. Ignora lo que
    esté antes del primer encabezado (por ejemplo, comentarios de instrucciones)."""
    partes = re.split(r"(?m)^##\s+(.+)$", texto)
    bloques = []
    for i in range(1, len(partes), 2):
        titulo = partes[i].strip()
        cuerpo = partes[i + 1] if i + 1 < len(partes) else ""
        bloque = _parsear_campos(titulo, cuerpo)
        if bloque:
            bloques.append(bloque)
    return bloques


def _textos_para_buscar(bloque):
    """Cada bloque se guarda VARIAS veces: una por la pregunta principal, una por
    cada pregunta similar, una por el título, una por las palabras clave y una
    por la respuesta. Así una pregunta corta como "hay becas" se compara contra
    textos cortos parecidos, en vez de contra un documento largo que mezcla todo
    (eso hacía que la búsqueda fallara). Al buscar se agrupan por bloque."""
    textos = [bloque["pregunta"], bloque["titulo"]] + bloque["variantes"]
    if bloque["palabras_clave"]:
        textos.append(bloque["palabras_clave"])
    # La respuesta también se indexa: hay datos (como la nota mínima) que solo
    # aparecen dentro de la respuesta de otro tema.
    textos.append(bloque["respuesta"])
    return textos


def cargar():
    client = chromadb.PersistentClient(path="./chroma_db")
    try:
        client.delete_collection(NOMBRE_COLECCION)
    except Exception:
        pass  # todavía no existía, no hay nada que borrar
    coleccion = client.get_or_create_collection(
        name=NOMBRE_COLECCION,
        embedding_function=embeddings.obtener_funcion_embeddings(),
        metadata={"hnsw:space": "cosine"},  # distancia coseno: 0 = idéntico, 1 = nada que ver
    )

    documentos, metadatos, ids = [], [], []
    n_bloques = 0
    archivos = sorted(glob.glob(f"{CARPETA}/*.md"))
    if not archivos:
        print(f"No encontré ningún .md en la carpeta '{CARPETA}'.")
        return

    for archivo in archivos:
        with open(archivo, encoding="utf-8") as f:
            texto = f.read()
        bloques = leer_bloques(texto)
        print(f"{archivo}: {len(bloques)} preguntas")
        for bloque in bloques:
            n_bloques += 1
            id_bloque = hashlib.md5(f"{archivo}|{bloque['titulo']}".encode()).hexdigest()
            meta = {
                "archivo": archivo,
                "id_bloque": id_bloque,
                "titulo": bloque["titulo"],
                "pregunta": bloque["pregunta"],
                "respuesta": bloque["respuesta"],
                # Texto con todas las formas de preguntar, para la búsqueda por
                # palabras que complementa a la de vectores (ver buscar_conocimiento.py).
                "terminos": " ".join(
                    [bloque["titulo"], bloque["pregunta"], bloque["palabras_clave"] or ""]
                    + bloque["variantes"]
                ),
            }
            if bloque["categoria"]:
                meta["categoria"] = bloque["categoria"]
            for n, texto in enumerate(_textos_para_buscar(bloque)):
                documentos.append(texto)
                metadatos.append(meta)
                ids.append(f"{id_bloque}-{n}")

    if documentos:
        coleccion.add(documents=documentos, metadatas=metadatos, ids=ids)
    print(f"\nListo: {n_bloques} preguntas ({len(documentos)} formas de buscarlas) "
          f"cargadas en la colección '{NOMBRE_COLECCION}'.")


if __name__ == "__main__":
    cargar()