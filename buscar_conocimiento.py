"""
Busca en ChromaDB los chunks más relevantes para una pregunta.
Se usa desde alice_voz.py; también se puede probar suelto:

    python buscar_conocimiento.py "cuanto dura la carrera"
"""
import sys

import chromadb

NOMBRE_COLECCION = "conocimiento_itcha"
_coleccion = None


def _obtener_coleccion():
    global _coleccion
    if _coleccion is None:
        client = chromadb.PersistentClient(path="./chroma_db")
        _coleccion = client.get_or_create_collection(name=NOMBRE_COLECCION)
    return _coleccion


def contar_preguntas():
    """Cuántas preguntas hay cargadas en la base, para mostrarlo al arrancar."""
    return _obtener_coleccion().count()


def buscar_contexto(pregunta, n_resultados=3):
    """Devuelve un solo texto con los chunks más parecidos a la pregunta,
    listo para pegarlo en el prompt de Ollama. Si no hay nada cargado
    todavía, devuelve una cadena vacía."""
    coleccion = _obtener_coleccion()
    if coleccion.count() == 0:
        return ""
    resultados = coleccion.query(query_texts=[pregunta], n_results=min(n_resultados, coleccion.count()))
    return "\n\n".join(resultados["documents"][0])


if __name__ == "__main__":
    pregunta = " ".join(sys.argv[1:]) or "¿Cuánto dura la carrera?"
    print("Pregunta:", pregunta)
    print("\nContexto encontrado:\n")
    print(buscar_contexto(pregunta) or "(la colección está vacía; corre primero cargar_conocimiento.py)")