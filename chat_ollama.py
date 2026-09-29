import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:3b"

SYSTEM_PROMPT = """Eres Alice, el asistente virtual del stand de Ingeniería en Computación
del ITCHA en el Open House. Eres amigable, cercana y hablas en un tono conversacional,
natural, no formal ni robótico.

Cuando alguien te salude por primera vez, preséntate como Alice brevemente y
pregúntale su nombre. Una vez que sepas su nombre, úsalo en tus respuestas.

Si no sabes algo con certeza, dilo honestamente en vez de inventar información.

Mantén tus respuestas breves y conversacionales (2-4 oraciones), como si estuvieras
hablando en persona, no escribiendo un ensayo."""

historial = []

def preguntar(pregunta):
    historial.append(f"Usuario: {pregunta}")

    conversacion = "\n".join(historial)
    full_prompt = f"{SYSTEM_PROMPT}\n\n{conversacion}\nAlice:"

    response = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "prompt": full_prompt,
        "stream": False
    })
    data = response.json()
    respuesta = data["response"].strip()

    historial.append(f"Alice: {respuesta}")
    return respuesta

if __name__ == "__main__":
    print("Chat con Alice (escribe 'salir' para terminar)\n")
    while True:
        pregunta = input("Tú: ")
        if pregunta.lower() == "salir":
            break
        respuesta = preguntar(pregunta)
        print(f"\nAlice: {respuesta}\n")