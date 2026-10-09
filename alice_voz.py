import os
import re
import threading

import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import requests
import random
import animaze_gestos
import voz_rapida
import buscar_conocimiento
from texto_para_voz import limpiar_texto_para_voz

# --- Configuración Whisper ---
SAMPLE_RATE = 16000
whisper_model = WhisperModel("small", device="cpu", compute_type="int8")

# Vocabulario que Whisper debe esperar: le ayuda a escribir bien los nombres
# propios y siglas (si no, "MEGATEC" sale como "mega tech", "C#" como "se numeral"...).
VOCABULARIO_WHISPER = (
    "Conversación en el Open House del ITCHA-AGAPE sobre el Técnico en Ingeniería en "
    "Computación: módulos, materias, becas MEGATEC, MINED, matrícula, mensualidad, "
    "inscripción, bases de datos, C#, Java, PHP, Laravel, Python, redes, ciclos."
)
# Si Whisper cree que un trozo es ruido (no voz) con esta probabilidad o más, se descarta.
# Evita frases inventadas como "¡Muchas gracias a todos!" cuando solo hubo ruido.
PROB_NO_ES_VOZ = 0.6

# --- Configuración detección de voz (VAD simple por volumen) ---
UMBRAL_SILENCIO = 0.015
SILENCIO_PARA_PARAR = 2.5
DURACION_MAXIMA = 20
BLOQUE_DURACION = 0.1
IDLE_HABLANDO = 19   # número del gesto de explicación
IDLE_REPOSO = 17   # número del gesto predeterminado
GESTO_SALUDO = 0   # número de "Hello" en Animaciones (python animaze_gestos.py especial)
# Cada cuántos segundos se vuelve a mandar IDLE_HABLANDO mientras Alice habla.
# Sirve si esa animación NO se repite sola en Animaze y se acaba antes que la voz.
# Ponlo en None si tu animación ya se repite en bucle (o si al refrescarla se ve un salto).
REPETIR_GESTO_CADA = 6

# --- Configuración Ollama ---
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:3b"   # alternativa del mismo tamaño y velocidad, mejor en español: "qwen2.5:3b"
MAX_TOKENS_RESPUESTA = 200
# 0 = siempre la misma respuesta exacta; un poco más le da estilo propio sin que invente.
TEMPERATURA = 0.3

# --- Configuración Piper ---
# Rutas relativas a la carpeta del proyecto, para que funcione aunque se ejecute desde otra carpeta.
CARPETA = os.path.dirname(os.path.abspath(__file__))
PIPER_EXE = os.path.join(CARPETA, "piper", "piper", "piper.exe")
VOZ_MODELO = os.path.join(CARPETA, "piper", "es_AR-daniela-high.onnx")
AUDIO_SALIDA = os.path.join(CARPETA, "respuesta.wav")

# Velocidad de la voz: 1.0 es la normal de Piper. Más alto = más lento y claro.
VELOCIDAD_VOZ = 1.15

# --- Búsqueda en la base de conocimiento ---
# Puntaje de 0 a 1 que da buscar_conocimiento.py (prueba: python buscar_conocimiento.py "tu pregunta").
# Por debajo de esto se considera que la pregunta NO tiene que ver con la base
# (saludos, "gracias", comentarios, preguntas de otros temas).
UMBRAL_RELEVANCIA = 0.42
# Además del mejor resultado, se mandan los que estén a esta distancia o menos de él.
MARGEN_EXTRA = 0.12
MAX_DATOS = 3

# --- Conversación ---
# Cuántos intercambios anteriores (pregunta + respuesta) recuerda Alice.
# Pocos: con muchos, el modelo pequeño se pone lento y empieza a repetir respuestas viejas.
TURNOS_HISTORIAL = 2
# Si no se oye a nadie en esta cantidad de grabaciones seguidas (cada una dura
# DURACION_MAXIMA segundos), se asume que el visitante se fue y Alice se reinicia.
GRABACIONES_VACIAS_PARA_REINICIAR = 3

PALABRAS_SALUDO = ["hola", "buenas", "buenos días", "buenos dias", "buenas tardes",
                   "buenas noches", "alice", "alicia", "hey", "oye", "qué tal", "que tal"]
# Ojo: no poner "salir" ni "terminar", porque aparecen en preguntas normales
# ("¿en cuánto tiempo termino la carrera?", "¿qué pasa si quiero salir del técnico?").
PALABRAS_SALIDA = ["adiós", "adios", "hasta luego", "nos vemos", "chao", "bye", "hasta pronto"]

# Frases que indican que la persona sigue con el tema anterior ("háblame más de eso").
SEGUIMIENTO = re.compile(
    r"\b(más|mas|eso|esa|ese|esto|ella|ellos|también|tambien|otra vez|explica\w*|detalle\w*"
    r"|y\s+(?:si|cuánto|cuanto|qué|que|cómo|como)"
    r"|\w+(?:arlo|erlo|irlo|arla|erla|irla|arlos|erlos|irlos))\b",  # "solicitarlo", "pedirla"
    re.IGNORECASE)

# Se elige una al azar cada vez que alguien se despide. Todas invitan a entrar
# a la carrera. Sin cifras ni fechas, para no decir datos que no estén en la base.
# Preguntas sobre la carrera en general ("explícame sobre la carrera"), que no traen un tema concreto.
PREGUNTA_GENERAL = re.compile(
    r"\b(carrera|t[eé]cnico|computaci[oó]n|ingenier[ií]a|qu[eé] (?:es|estudian|ense[ñn]an|ven)|"
    r"de qu[eé] (?:trata|va|se trata))\b",
    re.IGNORECASE)

FRASES_DESPEDIDA = [
    "¡Gracias por venir! Espero verte pronto como estudiante del ITCHA.",
    "¡Nos vemos! Si te quedan dudas, aquí estaremos todo el Open House.",
    "¡Anímate a inscribirte! En el ITCHA te estamos esperando.",
    "¡Fue un gusto platicar contigo! Ojalá te animes a estudiar con nosotros.",
    "¡Hasta pronto! Si te gusta la tecnología, esta carrera es para ti. ¡Te esperamos!",
    "¡Cuídate mucho! Imagínate creando tus propias aplicaciones; aquí puedes aprender a hacerlo.",
    "¡Gracias por tu visita! Ojalá el próximo ciclo te veamos en nuestras aulas.",
    "¡Nos vemos pronto! Tu futuro en la tecnología puede empezar aquí en el ITCHA.",
    "¡Fue un placer conocerte! Anímate, la computación tiene muchas oportunidades esperándote.",
    "¡Hasta luego! Recuerda que en Ingeniería en Computación del ITCHA siempre hay un lugar para ti.",
]

# --- Mini comercial ---
# Cuando alguien del stand dice "promociónate" (o "haz el comercial"), Alice da un
# comercial corto invitando a estudiar la carrera. Funciona en cualquier momento,
# haya o no un visitante conversando.
ORDEN_COMERCIAL = re.compile(
    r"\bpromoci[oó]na(?:te|rte|nos)?\b|\bpromu[eé]vete\b|\bcomercial\b|\bpromociona la carrera\b",
    re.IGNORECASE)
# Temas de la base (títulos "## " de los .md) que venden la carrera. Cada comercial
# usa "De qué trata la carrera" más TEMAS_POR_COMERCIAL de estos al azar, así no
# suena igual cada vez. Si cambias un título en los .md, cámbialo aquí también.
TEMA_FIJO_COMERCIAL = "De qué trata la carrera"
TEMAS_COMERCIAL = [
    "Duración de la carrera",
    "Becas, financiamiento y gastos adicionales",
    "Áreas de trabajo y competencias",
    "Lenguajes y herramientas que se enseñan",
    "Continuación universitaria",
    "Páginas web y tiendas en línea",
    "Conocimientos previos de programación",
    "Límite de edad para matricularse",
    "Costo de mensualidad y matrícula",
]
TEMAS_POR_COMERCIAL = 3
MAX_TOKENS_COMERCIAL = 300

PROMPT_COMERCIAL = """Eres Alice, la asistente virtual del stand de la carrera de Técnico en
Ingeniería en Computación del ITCHA, en el Open House. Eres mujer.

Vas a dar un mini comercial EN VOZ ALTA para los estudiantes que pasan por el stand:
entusiasta, cercano y motivador, como un anuncio de radio de unos treinta segundos.

REGLAS:
1. Usa ÚNICAMENTE los datos que aparecen en "DATOS". No inventes cifras, beneficios,
   lenguajes, convenios ni nada que no esté escrito ahí.
2. Empieza llamando la atención de quien pasa, menciona dos o tres ventajas de la
   carrera tomadas de los datos y termina invitando a inscribirse en el ITCHA.
3. Entre cuatro y seis oraciones cortas. Nada de listas, Markdown, guiones ni asteriscos.
4. No enumeres todo: de lenguajes, herramientas o materias menciona como mucho dos
   ejemplos. Es un anuncio, no un plan de estudios.
5. No menciones "DATOS" ni que consultaste información.
6. Empieza DIRECTAMENTE con el anuncio. Nunca digas "aquí tienes", "este es mi
   comercial", "anuncio", "spot" ni nada que presente lo que vas a decir: eres tú
   hablándole al público, no alguien entregando un texto.
"""

# Por si el modelo igual arranca presentando el comercial ("¡Hola! Aquí tienes tu
# minicomercial: ..."), se borra esa parte antes de decirlo.
INTRO_COMERCIAL = re.compile(
    r"^(?:[¡¿]?[^.!?:]{0,40}[.!?]\s*)?"   # un saludo corto opcional antes ("¡Hola!")
    r"[^.!?:]*\b(?:aqu[ií] (?:tienes|va|est[aá]|un|te)|(?:mini\s?)?comercial|minic[oó]mico|anuncio|spot)\b[^.!?:]*:\s*",
    re.IGNORECASE)

# Si Ollama falla, se dice uno de estos (solo con datos que están en la base).
COMERCIALES_RESPALDO = [
    "¿Te gusta la tecnología? En el ITCHA puedes estudiar el Técnico en Ingeniería en Computación "
    "en solo 2 años. Aprenderás a desarrollar aplicaciones web y móviles, administrar bases de datos "
    "y gestionar redes. ¡Anímate a inscribirte, te estamos esperando!",
    "¡Atención, futuros programadores! Con el Técnico en Ingeniería en Computación del ITCHA puedes "
    "trabajar en desarrollo de software, bases de datos y redes informáticas. Además, existe el programa "
    "de becas MINED MEGATEC. ¡Ven e inscríbete, tu futuro en la tecnología empieza aquí!",
]

SYSTEM_PROMPT_FAQ = """Eres Alice, la asistente virtual de un stand del Open House del ITCHA,
para la carrera de Técnico en Ingeniería en Computación. Hablas en voz alta con
visitantes, de forma amable, cercana y natural, con tus propias palabras.
Eres mujer: habla de ti en femenino ("encantada", "lista", "contenta").

En el ITCHA las materias se llaman "módulos": materia y módulo son lo mismo.

REGLAS:
1. Para datos de la carrera usa ÚNICAMENTE lo que aparece en "DATOS" dentro del
   mensaje. Puedes explicarlo con tu estilo, pero tienes PROHIBIDO agregar cifras,
   nombres de programas, lenguajes o cualquier dato que no esté escrito ahí, aunque
   suene razonable para una carrera de computación. Ejemplo: si los datos hablan de
   desarrollo web pero no dicen "HTML" ni "CSS", tú tampoco los digas.
2. Si los datos dicen que algo NO es posible o NO se ofrece, tu respuesta dice que NO.
   Nunca lo contradigas ni lo suavices.
3. Los DATOS pueden traer varios temas; usa solo los que respondan la pregunta e
   ignora el resto. Si la respuesta está en los datos aunque sea dentro de otro
   tema, úsala: no digas que no la tienes.
4. Si los datos de verdad no responden la pregunta, dilo con honestidad, por ejemplo
   "no tengo ese dato", y sugiere preguntarle a alguien del stand. No adivines.
   Pero si los datos SÍ responden, da la respuesta directo, sin mandar a nadie al stand.
5. Si la persona no hace una pregunta (agradece, saluda, comenta algo), respóndele
   breve y amable, e invítala a preguntar sobre la carrera. No le des datos que no pidió
   y no te despidas: la conversación sigue.
6. No repitas una respuesta que ya diste; si te preguntan lo mismo, dilo de otra forma
   y más corto.
7. Sé breve: entre dos y cuatro oraciones, porque se lee en voz alta.
8. NUNCA uses Markdown, listas, guiones, asteriscos ni numerales.
9. NUNCA menciones "DATOS", ni que consultaste una base o un contexto: responde como
   si ya lo supieras.
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
    segments, info = whisper_model.transcribe(
        audio,
        language="es",
        initial_prompt=VOCABULARIO_WHISPER,
        vad_filter=True,                    # ignora los tramos sin voz
        condition_on_previous_text=False,   # evita que repita frases en bucle
    )
    return " ".join(s.text for s in segments if s.no_speech_prob < PROB_NO_ES_VOZ).strip()


def preguntar_a_ollama(mensajes, temperatura=None, max_tokens=None):
    response = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "messages": mensajes,
        "stream": False,
        "options": {
            "temperature": TEMPERATURA if temperatura is None else temperatura,
            "repeat_penalty": 1.15,
            "num_predict": max_tokens or MAX_TOKENS_RESPUESTA,
        }
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
ultima_pregunta_con_datos = ""  # para entender preguntas de seguimiento ("háblame más de eso")


def elegir_datos(pregunta_persona):
    """Busca en la base los bloques que responden la pregunta. Devuelve solo los
    relevantes (puede ser una lista vacía si la pregunta no tiene que ver)."""
    global ultima_pregunta_con_datos
    importantes = buscar_conocimiento.palabras_importantes(pregunta_persona)
    es_seguimiento = bool(SEGUIMIENTO.search(pregunta_persona))

    if len(importantes) <= 1 and es_seguimiento and ultima_pregunta_con_datos:
        # Pregunta de seguimiento sin tema propio ("háblame más de eso",
        # "¿cómo lo solicito?"): se busca junto con la pregunta anterior.
        # Así no se le pasan al modelo temas al azar que luego mezcla.
        texto_busqueda = ultima_pregunta_con_datos + " " + pregunta_persona
    elif not importantes and PREGUNTA_GENERAL.search(pregunta_persona):
        # "Explícame sobre la carrera", "¿qué es esto?": pregunta general, sin tema concreto.
        texto_busqueda = "de qué trata la carrera"
    elif not importantes:
        # Ninguna palabra con tema ("y...", "mira, quiero ver"): es un comentario,
        # no se le pasan datos para que no suelte información que nadie pidió.
        return []
    else:
        texto_busqueda = pregunta_persona

    bloques = buscar_conocimiento.buscar_bloques(texto_busqueda, n_resultados=MAX_DATOS)
    mejor = bloques[0]["puntaje"] if bloques else 0
    if mejor < UMBRAL_RELEVANCIA:
        return []
    elegidos = [b for b in bloques if b["puntaje"] >= max(UMBRAL_RELEVANCIA, mejor - MARGEN_EXTRA)]
    ultima_pregunta_con_datos = texto_busqueda
    return elegidos


def responder_pregunta(pregunta_persona):
    """Busca en la base de conocimiento (ChromaDB) la información relacionada
    con la pregunta y le pide a Ollama que conteste usando solo eso."""
    datos = elegir_datos(pregunta_persona)
    print("  [datos usados: " + (", ".join(f"{b['titulo']} ({b['puntaje']:.2f})" for b in datos)
                                 or "ninguno") + "]")

    if datos:
        # Al modelo solo le llega el tema y la respuesta oficial: las variantes y
        # palabras clave sirven para buscar, pero a él solo lo confundirían.
        texto_datos = "\n\n".join(f"Tema: {b['titulo']}\n{b['respuesta']}" for b in datos)
        mensaje_con_contexto = (
            f"DATOS:\n{texto_datos}\n\n"
            f"Lo que dijo la persona: {pregunta_persona}"
        )
    else:
        mensaje_con_contexto = (
            f"Lo que dijo la persona: {pregunta_persona}\n\n"
            "(No hay datos de la carrera sobre esto. Si es un agradecimiento, saludo o "
            "comentario, respóndele amable y breve. Si es una pregunta, dile con honestidad "
            "que no tienes ese dato y que pregunte a alguien del stand. NO menciones "
            "materias, temas, lenguajes ni ningún dato de la carrera por tu cuenta.)"
        )

    # El historial guarda solo lo que dijo la persona (sin los datos), y solo los
    # últimos turnos, para que la conversación no se vuelva cada vez más pesada.
    mensajes = (
        [{"role": "system", "content": SYSTEM_PROMPT_FAQ}]
        + historial[-2 * TURNOS_HISTORIAL:]
        + [{"role": "user", "content": mensaje_con_contexto}]
    )

    try:
        respuesta = preguntar_a_ollama(mensajes)
    except Exception as e:
        print("Aviso: no se pudo hablar con Ollama (¿está encendido?):", e)
        return "Perdón, tuve un pequeño problema técnico. ¿Me lo puedes preguntar de nuevo?"
    historial.append({"role": "user", "content": pregunta_persona})
    historial.append({"role": "assistant", "content": respuesta})
    del historial[:-2 * TURNOS_HISTORIAL]
    return respuesta


def hacer_comercial():
    """Arma un mini comercial de la carrera con datos reales de la base."""
    temas = [TEMA_FIJO_COMERCIAL] + random.sample(TEMAS_COMERCIAL, TEMAS_POR_COMERCIAL)
    datos = buscar_conocimiento.bloques_por_titulo(temas)
    print("  [comercial con: " + ", ".join(b["titulo"] for b in datos) + "]")
    if not datos:
        return random.choice(COMERCIALES_RESPALDO)
    texto_datos = "\n\n".join(f"Tema: {b['titulo']}\n{b['respuesta']}" for b in datos)
    mensajes = [
        {"role": "system", "content": PROMPT_COMERCIAL},
        {"role": "user", "content": f"DATOS:\n{texto_datos}\n\nDa el mini comercial ahora."},
    ]
    try:
        # Temperatura más alta que en las respuestas: así cada comercial sale distinto.
        texto = preguntar_a_ollama(mensajes, temperatura=0.7, max_tokens=MAX_TOKENS_COMERCIAL)
        texto = INTRO_COMERCIAL.sub("", texto).strip()
        return (texto[:1].upper() + texto[1:]) if texto else random.choice(COMERCIALES_RESPALDO)
    except Exception as e:
        print("Aviso: no se pudo hablar con Ollama (¿está encendido?):", e)
        return random.choice(COMERCIALES_RESPALDO)


def es_orden_comercial(texto):
    return bool(texto and ORDEN_COMERCIAL.search(texto))


def reiniciar_conversacion():
    """Olvida todo lo hablado, para que el siguiente visitante empiece de cero."""
    global ultima_pregunta_con_datos
    historial.clear()
    ultima_pregunta_con_datos = ""


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

def hablar(texto, gesto_especial=None):
    voz_rapida.hablar(texto, PIPER_EXE, VOZ_MODELO, AUDIO_SALIDA, IDLE_HABLANDO, IDLE_REPOSO, VELOCIDAD_VOZ,
                      gesto_especial=gesto_especial, repetir_gesto_cada=REPETIR_GESTO_CADA)


def decir(texto, gesto_especial=None):
    """gesto_especial: animación (ej. GESTO_SALUDO) que arranca junto con la voz."""
    texto_limpio = limpiar_texto_para_voz(texto)
    print(f"\nAlice: {texto_limpio}\n")
    hablar(texto_limpio, gesto_especial)


def contiene(texto, palabras):
    texto = texto.lower()
    return any(re.search(r"\b" + re.escape(p) + r"\b", texto) for p in palabras)


def esperar_saludo():
    """Escucha hasta que alguien salude (o diga "Alice"). Mientras tanto, si
    alguien del stand dice "promociónate", da el mini comercial y sigue esperando."""
    print("Esperando saludo... (di 'hola' o 'Alice' para empezar, 'promociónate' para el comercial)\n")
    while True:
        texto = transcribir(grabar_audio_dinamico())
        if texto:
            print(f"Tú dijiste: {texto}")
        if es_orden_comercial(texto):
            decir(hacer_comercial())
            continue
        if texto and contiene(texto, PALABRAS_SALUDO):
            return


def atender_visitante():
    """Una conversación completa con un visitante: termina cuando se despide
    o cuando deja de hablar un buen rato."""
    reiniciar_conversacion()
    decir(gesto_especial=GESTO_SALUDO, texto="¡Hola! Soy Alice, la asistente del Técnico en Ingeniería en Computación del ITCHA. Pregúntame lo que quieras sobre la carrera.")

    vacias_seguidas = 0
    while True:
        audio = grabar_audio_dinamico()
        print("Transcribiendo...")
        texto = transcribir(audio)
        print(f"Tú dijiste: {texto}")

        if not texto or len(texto.strip()) < 3:
            vacias_seguidas += 1
            if vacias_seguidas >= GRABACIONES_VACIAS_PARA_REINICIAR:
                print("(Nadie habla desde hace rato: se reinicia para el siguiente visitante.)")
                return
            print("(No se detectó voz clara, escuchando de nuevo...)\n")
            continue
        vacias_seguidas = 0

        if contiene(texto, PALABRAS_SALIDA):
            decir(random.choice(FRASES_DESPEDIDA), gesto_especial=GESTO_SALUDO)
            return

        if es_orden_comercial(texto):
            decir(hacer_comercial())
            continue

        decir(responder_pregunta(texto))


if __name__ == "__main__":
    n_preguntas = buscar_conocimiento.contar_preguntas()
    print(f"Alice está lista ({n_preguntas} preguntas cargadas en la base de conocimiento).")
    print("Di 'adiós' para terminar con un visitante. Ctrl+C para apagar a Alice.\n")
    idx = elegir_microfono()
    print("Micrófono en uso:", sd.query_devices(idx)["name"] if idx is not None else "ninguno")

    animaze_gestos.idle(IDLE_REPOSO)
    threading.Thread(target=calentar_ollama, daemon=True).start()

    try:
        # Atiende a un visitante tras otro: después de cada despedida vuelve a
        # esperar un saludo, con la conversación anterior ya olvidada.
        while True:
            esperar_saludo()
            atender_visitante()
            animaze_gestos.idle(IDLE_REPOSO)
            print("\n--- Listo para el siguiente visitante ---\n")
    except KeyboardInterrupt:
        animaze_gestos.idle(IDLE_REPOSO)
        print("\nAlice apagada.")
