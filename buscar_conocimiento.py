"""
Busca en ChromaDB las preguntas frecuentes más relevantes para una pregunta.
Se usa desde alice_voz.py; también se puede probar suelto (muestra el puntaje
de cada resultado, útil para ajustar el umbral de alice_voz.py):

    python buscar_conocimiento.py "cuanto dura la carrera"

La búsqueda es HÍBRIDA:
  1. Por significado (vectores de ChromaDB): encuentra preguntas parecidas
     aunque usen otras palabras.
  2. Por palabras: el modelo de vectores a veces no entiende palabras clave
     cortas (para él, "hay becas" no se parece a "hay becas para estudiar"),
     así que además se mira qué palabras importantes de la pregunta aparecen
     escritas en cada bloque.
Las dos se combinan en un solo puntaje de 0 a 1 (más alto = más relevante).
"""
import math
import re
import sys
import unicodedata

import chromadb

import embeddings

NOMBRE_COLECCION = "conocimiento_itcha"
_coleccion = None
_indice_palabras = None  # se arma una sola vez: {id_bloque: (fuertes, debiles)} y el idf
_bloques = None

# Cuánto pesa cada parte en el puntaje final (suman 1).
PESO_VECTORES = 0.5
PESO_PALABRAS = 0.5

# Palabras que la gente usa pero que en los .md están escritas de otra forma.
# Se reemplazan SOLO en el texto que se usa para buscar (no en lo que se le
# manda a Ollama). Por ejemplo: en el ITCHA las "materias" se llaman "módulos".
SINONIMOS_BUSQUEDA = {
    r"\bmaterias\b": "módulos",
    r"\bmateria\b": "módulo",
    r"\basignaturas?\b": "módulos",
    r"\bpensum\b": "plan de estudio",
    r"\bcolegiatura\b": "mensualidad",
    # Whisper suele escuchar "C#" como "ce numeral", "se sharp", etc.
    r"\b(?:c|ce|se|ese)\s*(?:numeral|sharp|charp|shar|chard)\b": "C#",
}

# Palabras que no ayudan a distinguir un tema de otro.
PALABRAS_VACIAS = set("""
a al algo algun alguna alguno ante asi bien cada como con cual cuales cuando cuanto cuanta
cuantos cuantas de del donde e el ella ellos en entre era es esa ese eso esta este esto estos
estas fue ha hay hace hacen hacer han la las le les lo los mas me mi mis mucho muchos mucha
muchas muy ni no nos o para pero por porque puede pueden puedo pues que quiero se sea ser si
sin sobre son su sus tambien te tiene tienen tengo tu tus un una uno unos unas usted ustedes
va vamos y ya yo hablame dime cuentame decir saber gustaria explicame informacion
carrera itcha agape tecnico ingenieria computacion alice alicia hola gracias todos ver mira
ay eh mm este puedes podrias podria hablarme contarme explicarme decirme quisiera claro bueno
""".split())


def normalizar_pregunta(pregunta):
    texto = pregunta.lower()
    for patron, reemplazo in SINONIMOS_BUSQUEDA.items():
        texto = re.sub(patron, reemplazo, texto)
    return texto


def _raiz(palabra):
    """Quita acentos y plurales sencillos: "Becas" -> "beca", "módulos" -> "modulo"."""
    palabra = unicodedata.normalize("NFD", palabra.lower())
    palabra = "".join(c for c in palabra if unicodedata.category(c) != "Mn")
    if len(palabra) > 4 and palabra.endswith("es"):
        palabra = palabra[:-2]
    elif len(palabra) > 3 and palabra.endswith("s"):
        palabra = palabra[:-1]
    return palabra


def _palabras(texto):
    sueltas = re.findall(r"[a-záéíóúüñ#0-9]+", texto.lower())
    return {_raiz(p) for p in sueltas} - {_raiz(p) for p in PALABRAS_VACIAS}


def _obtener_coleccion():
    global _coleccion
    if _coleccion is None:
        client = chromadb.PersistentClient(path="./chroma_db")
        _coleccion = client.get_or_create_collection(
            name=NOMBRE_COLECCION,
            embedding_function=embeddings.obtener_funcion_embeddings(),
            metadata={"hnsw:space": "cosine"},
        )
    return _coleccion


def _bloques_cargados():
    """{id_bloque: metadatos} de todos los bloques de la colección (se lee una sola vez)."""
    global _bloques
    if _bloques is None:
        metas = _obtener_coleccion().get(include=["metadatas"])["metadatas"]
        _bloques = {m["id_bloque"]: m for m in metas if "id_bloque" in m}
    return _bloques


def _obtener_indice_palabras():
    global _indice_palabras
    if _indice_palabras is None:
        bloques = {}
        for id_bloque, meta in _bloques_cargados().items():
            fuertes = _palabras(meta.get("terminos", "") + " " + meta.get("pregunta", ""))
            debiles = _palabras(meta.get("respuesta", ""))
            bloques[id_bloque] = (fuertes, debiles)
        # idf: una palabra que aparece en pocos bloques vale más que una que está en todos.
        n = max(len(bloques), 1)
        conteo = {}
        for fuertes, debiles in bloques.values():
            for p in fuertes | debiles:
                conteo[p] = conteo.get(p, 0) + 1
        idf = {p: math.log(1 + n / c) for p, c in conteo.items()}
        _indice_palabras = (bloques, idf)
    return _indice_palabras


def _puntaje_palabras(palabras_pregunta, id_bloque):
    """0 a 1: qué parte de las palabras importantes de la pregunta aparece en el
    bloque. Cuenta completo si está en la pregunta/variantes/palabras clave, y
    a la mitad si solo aparece dentro de la respuesta."""
    bloques, idf = _obtener_indice_palabras()
    if id_bloque not in bloques:
        return 0.0
    fuertes, debiles = bloques[id_bloque]
    # Palabras que no existen en ningún bloque no cuentan (no deben bajar el puntaje).
    conocidas = [p for p in palabras_pregunta if p in idf]
    total = sum(idf[p] for p in conocidas)
    if total == 0:
        return 0.0
    logrado = sum(idf[p] * (1.0 if p in fuertes else 0.5 if p in debiles else 0.0) for p in conocidas)
    return logrado / total


def palabras_importantes(texto):
    """Palabras de la pregunta que sí existen en la base (sin "qué", "hay", "puedes"...).
    Si no queda ninguna, la frase no trae un tema propio: es un comentario
    ("mira, quiero ver") o una pregunta de seguimiento ("¿cómo lo solicito?")."""
    _, idf = _obtener_indice_palabras()
    return {p for p in _palabras(normalizar_pregunta(texto)) if p in idf}


def bloques_por_titulo(titulos):
    """Devuelve los bloques con esos títulos ("## ..." en los .md), en el mismo
    orden. Los títulos que no existan se avisan y se saltan."""
    por_titulo = {m.get("titulo"): m for m in _bloques_cargados().values()}
    encontrados = []
    for titulo in titulos:
        meta = por_titulo.get(titulo)
        if meta is None:
            print(f"Aviso: no hay ningún bloque con el título «{titulo}» en la base.")
            continue
        encontrados.append({"titulo": titulo, "respuesta": meta.get("respuesta", "")})
    return encontrados


def contar_preguntas():
    """Cuántas preguntas (bloques) hay cargadas en la base, para mostrarlo al arrancar."""
    return len(_bloques_cargados())


def buscar_bloques(pregunta, n_resultados=3):
    """Devuelve una lista de hasta n_resultados bloques distintos, del más
    relevante al menos. Cada uno es un dict con titulo, pregunta, respuesta,
    categoria, distancia (de vectores, 0 = idéntico) y puntaje (0 a 1,
    combinado; más alto = más relevante)."""
    coleccion = _obtener_coleccion()
    total = coleccion.count()
    if total == 0:
        return []
    texto = normalizar_pregunta(pregunta)
    # Se piden bastantes resultados porque cada bloque está guardado varias
    # veces (una por cada forma de preguntarlo); luego se agrupan por bloque.
    res = coleccion.query(query_texts=[texto], n_results=min(60, total), include=["metadatas", "distances"])
    distancias = {}
    for meta, dist in zip(res["metadatas"][0], res["distances"][0]):
        clave = meta.get("id_bloque")
        distancias[clave] = min(dist, distancias.get(clave, 1.0))

    palabras_pregunta = _palabras(texto)
    candidatos = []
    for id_bloque, meta in _bloques_cargados().items():
        dist = distancias.get(id_bloque, 1.0)
        similitud = max(0.0, 1.0 - dist)
        pal = _puntaje_palabras(palabras_pregunta, id_bloque)
        candidatos.append({
            "titulo": meta.get("titulo", ""),
            "pregunta": meta.get("pregunta", ""),
            "respuesta": meta.get("respuesta", ""),
            "categoria": meta.get("categoria", ""),
            "distancia": dist,
            "palabras": pal,
            "puntaje": PESO_VECTORES * similitud + PESO_PALABRAS * pal,
        })
    candidatos.sort(key=lambda b: b["puntaje"], reverse=True)
    return candidatos[:n_resultados]


if __name__ == "__main__":
    pregunta = " ".join(sys.argv[1:]) or "¿Cuánto dura la carrera?"
    print("Pregunta:", pregunta)
    print("Se busca como:", normalizar_pregunta(pregunta))
    print("Palabras importantes:", _palabras(normalizar_pregunta(pregunta)), "\n")
    bloques = buscar_bloques(pregunta, n_resultados=5)
    if not bloques:
        print("(la colección está vacía; corre primero cargar_conocimiento.py)")
    for b in bloques:
        print(f"  puntaje {b['puntaje']:.2f}  (vector {b['distancia']:.2f}, palabras {b['palabras']:.2f})  {b['titulo']}")
