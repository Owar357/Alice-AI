import subprocess
import threading

import sounddevice as sd
import soundfile as sf
import numpy as np
from faster_whisper import WhisperModel
import requests
import re
import random
import animaze_gestos
import voz_rapida
import buscar_conocimiento

# --- Configuración Whisper ---
SAMPLE_RATE = 16000
whisper_model = WhisperModel("small", device="cpu", compute_type="int8")

# --- Configuración detección de voz (VAD simple por volumen) ---
UMBRAL_SILENCIO = 0.015
SILENCIO_PARA_PARAR = 2.5
DURACION_MAXIMA = 20
BLOQUE_DURACION = 0.1
IDLE_HABLANDO = 19   # número del gesto de explicación
IDLE_REPOSO = 17   # número del gesto predeterminado
GESTO_SALUDO = 0   # número de "Hello" en Animaciones (python animaze_gestos.py especial)

# --- Configuración Ollama ---
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:3b"
MAX_TOKENS_RESPUESTA = 200

# --- Configuración Piper ---
PIPER_EXE = "piper/piper/piper.exe"
VOZ_MODELO = "piper/es_AR-daniela-high.onnx"
AUDIO_SALIDA = "respuesta.wav"

# --- Base de conocimiento (preguntas frecuentes, vía ChromaDB) ---
FRASES_DESPEDIDA = [
    "¡Gracias por venir! Espero verte pronto en el ITCHA.",
    "¡Nos vemos! No olvides pasar por el stand si tienes más dudas.",
    "¡Anímate a inscribirte! Todavía hay cupo, y en el ITCHA te estamos esperando.",
    "¡Fue un gusto platicar contigo! Ojalá te animes a estudiar con nosotros.",
]

SYSTEM_PROMPT_FAQ = """Eres Alice, la asistente virtual de un stand del Open House del ITCHA,
para la carrera de Técnico en Ingeniería en Computación.

REGLAS:
1. Responde ÚNICAMENTE usando la información que aparece en "INFORMACIÓN DISPONIBLE"
   dentro del mensaje de la persona. Tienes PROHIBIDO agregar cifras, marcas, nombres
   de programas, lenguajes de programación o cualquier otro dato que no esté escrito
   ahí LITERALMENTE - ni siquiera si te parece típico, razonable o del mismo tema.
   Ejemplo de lo que NO debes hacer: si la información disponible dice "16 gigabytes
   de RAM y 500 gigabytes de disco sólido" y no menciona ningún lenguaje de programación,
   NUNCA agregues por tu cuenta que hace falta instalar Java, C++, Eclipse o NetBeans,
   aunque suene razonable para una carrera de computación. Si no está escrito ahí,
   para ti no existe.
2. Si esa información no responde lo que te preguntaron, dilo con honestidad -
   por ejemplo "no tengo ese dato" - y sugiere preguntarle a alguien del stand.
   No trates de adivinar ni de completar con suposiciones.
3. Sé breve y conversacional, entre dos y cuatro oraciones, ya que se lee en voz alta.
4. NUNCA uses formato Markdown, ni símbolos como guiones, asteriscos o numerales.
5. NUNCA leas la palabra "INFORMACIÓN DISPONIBLE" ni menciones que consultaste
   un contexto o una base de datos - responde de forma natural, como si ya lo supieras.
"""


def grabar_audio_dinamico(silencio_para_parar=None, duracion_maxima=None):
    silencio_para_parar = silencio_para_parar or SILENCIO_PARA_PARAR
    duracion_maxima = duracion_maxima or DURACION_MAXIMA

    print("\n🎤 Escuchando... (habla cuando quieras)")
    muestras_por_bloque = int(SAMPLE_RATE * BLOQUE_DURACION)
    bloques = []
    silencio_acumulado = 0
    empezo_a_hablar = False
    tiempo_total = 0

    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", device=elegir_microfono())
    stream.start()

    while tiempo_total < duracion_maxima:
        bloque, _ = stream.read(muestras_por_bloque)
        bloques.append(bloque.copy())
        volumen = np.abs(bloque).mean()
        tiempo_total += BLOQUE_DURACION

        if volumen > UMBRAL_SILENCIO:
            empezo_a_hablar = True
            silencio_acumulado = 0
        elif empezo_a_hablar:
            silencio_acumulado += BLOQUE_DURACION
            if silencio_acumulado >= silencio_para_parar:
                break

    stream.stop()
    stream.close()
    print("Grabación terminada.")

    if not empezo_a_hablar:
        return np.array([], dtype="float32")
    return np.concatenate(bloques).flatten()


def transcribir(audio):
    if audio.size == 0:
        return ""
    segments, info = whisper_model.transcribe(audio, language="es")
    return " ".join([segment.text for segment in segments]).strip()


def preguntar_a_ollama(mensajes):
    response = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "messages": mensajes,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": MAX_TOKENS_RESPUESTA}
    })
    datos = response.json()
    texto = datos["message"]["content"].strip()
    if datos.get("done_reason") == "length":
        # Se cortó por el límite de largo: quita la frase que quedó a medias
        corte = max(texto.rfind("."), texto.rfind("!"), texto.rfind("?"))
        if corte > 0:
            texto = texto[:corte + 1]
    return texto


historial = []  # lista de dicts {"role": "user"/"assistant", "content": "..."}


def responder_pregunta(pregunta_persona):
    """Busca en la base de conocimiento (ChromaDB) la información relacionada
    con la pregunta y le pide a Ollama que conteste usando solo eso."""
    contexto = buscar_conocimiento.buscar_contexto(pregunta_persona)

    if contexto:
        mensaje_usuario = (
            f"INFORMACIÓN DISPONIBLE:\n{contexto}\n\n"
            f"Pregunta de la persona: {pregunta_persona}"
        )
    else:
        mensaje_usuario = (
            f"Pregunta de la persona: {pregunta_persona}\n\n"
            "(No se encontró información relacionada en la base. Dile con honestidad "
            "que no tienes ese dato y que pregunte a alguien del stand.)"
        )

    historial.append({"role": "user", "content": mensaje_usuario})
    mensajes = [{"role": "system", "content": SYSTEM_PROMPT_FAQ}] + historial

    respuesta = preguntar_a_ollama(mensajes)
    historial.append({"role": "assistant", "content": respuesta})
    return respuesta


# Siglas técnicas en inglés que Piper suele leer mal o "atropellado" en español.
# Se reemplazan por su forma hablada ANTES de limpiar el resto del texto.
TERMINOS_TECNICOS = {
    r"\bSSD\b": "disco sólido",
    r"\bHDD\b": "disco duro",
    r"\bRAM\b": "memoria RAM",
    r"\bCPU\b": "procesador",
    r"\b(\d+)\s*GB\b": r"\1 gigabytes",
    r"\b(\d+)\s*TB\b": r"\1 terabytes",
    r"\bWi-?Fi\b": "wifi",
}


def normalizar_terminos_tecnicos(texto):
    for patron, reemplazo in TERMINOS_TECNICOS.items():
        texto = re.sub(patron, reemplazo, texto, flags=re.IGNORECASE)
    return texto


def limpiar_texto_para_voz(texto):
    texto = normalizar_terminos_tecnicos(texto)
    texto = re.sub(r'\*\*(.*?)\*\*', r'\1', texto)
    texto = re.sub(r'\*(.*?)\*', r'\1', texto)
    texto = re.sub(r'#{1,6}\s*', '', texto)
    texto = re.sub(r'^[-*]\s+', '', texto, flags=re.MULTILINE)  # bullets con - o *
    texto = re.sub(r'\*', '', texto)         # cualquier asterisco suelto restante
    texto = texto.replace('`', '')          # comillas invertidas de código
    texto = texto.replace('::', ', ')        # doble dos puntos de namespaces PHP
    texto = texto.replace('->', ' ')         # flechas de acceso a métodos/propiedades
    texto = re.sub(r'\s{2,}', ' ', texto)    # colapsa espacios dobles que queden
    return texto.strip()



PALABRAS_VIRTUALES = ["cable", "vb-audio", "steam", "mezcla", "stereo mix", "asignador", "loopback"]

def es_microfono_real(dev):
    nombre = dev["name"].lower()
    return dev["max_input_channels"] > 0 and not any(p in nombre for p in PALABRAS_VIRTUALES)

def elegir_microfono():
    """Usa el micrófono predeterminado de Windows si es real; si el predeterminado
    es un cable virtual, usa el primer micrófono real que encuentre."""
    dispositivos = sd.query_devices()
    try:
        default_in = sd.default.device[0]
        if default_in is None or default_in < 0:
            default_in = sd.query_devices(kind="input")["index"]
        if es_microfono_real(dispositivos[default_in]):
            return default_in
    except Exception:
        pass
    for i, dev in enumerate(dispositivos):
        if es_microfono_real(dev):
            return i
    return None


def calentar_ollama():
    """Carga el modelo en memoria antes de la primera respuesta real."""
    try:
        requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "messages": [{"role": "user", "content": "hola"}],
            "stream": False,
            "options": {"num_predict": 1}
        }, timeout=120)
    except Exception:
        pass

def hablar(texto):
    voz_rapida.hablar(texto, PIPER_EXE, VOZ_MODELO, AUDIO_SALIDA, IDLE_HABLANDO, IDLE_REPOSO)


def decir(texto):
    texto_limpio = limpiar_texto_para_voz(texto)
    print(f"\nAlice: {texto_limpio}\n")
    hablar(texto_limpio)


if __name__ == "__main__":
    n_preguntas = buscar_conocimiento.contar_preguntas()
    print(f"Alice está lista ({n_preguntas} preguntas cargadas en la base de conocimiento).")
    print("Di 'salir' o 'adiós' para terminar.\n")
    idx = elegir_microfono()
    print("Micrófono en uso:", sd.query_devices(idx)["name"] if idx is not None else "ninguno")

    animaze_gestos.idle(IDLE_REPOSO)
    threading.Thread(target=calentar_ollama, daemon=True).start()

    # Espera a que la persona salude antes de empezar a recibir preguntas.
    palabras_saludo = ["hola", "buenas", "buenos días", "buenos dias", "buenas tardes", "buenas noches"]
    print("Esperando saludo... (di 'hola' para empezar)\n")
    while True:
        audio = grabar_audio_dinamico()
        texto = transcribir(audio)
        print(f"Tú dijiste: {texto}")
        if texto and any(palabra in texto.lower().strip() for palabra in palabras_saludo):
            break
        print("(Sigo esperando un saludo...)\n")

    animaze_gestos.accion_especial(GESTO_SALUDO)
    decir("¡Hola! Soy Alice, la asistente del Técnico en Ingeniería en Computación del ITCHA. Pregúntame lo que quieras sobre la carrera.")

    while True:
        audio = grabar_audio_dinamico()
        print("Transcribiendo...")
        texto = transcribir(audio)
        print(f"Tú dijiste: {texto}")

        if not texto or len(texto.strip()) < 3:
            print("(No se detectó voz clara, escuchando de nuevo...)\n")
            continue

        palabras_salida = ["salir", "adiós", "adios", "hasta luego", "terminar"]
        if any(palabra in texto.lower().strip() for palabra in palabras_salida):
            animaze_gestos.accion_especial(GESTO_SALUDO)
            decir(random.choice(FRASES_DESPEDIDA))
            break

        respuesta = responder_pregunta(texto)
        decir(respuesta)