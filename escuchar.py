import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel

DURACION = 5  # segundos que va a grabar
SAMPLE_RATE = 16000  # Whisper espera audio a 16kHz

print("Cargando modelo Whisper (solo la primera vez tarda un poco)...")
model = WhisperModel("small", device="cpu", compute_type="int8")

def grabar_audio():
    print(f"\n🎤 Grabando por {DURACION} segundos... ¡habla ahora!")
    audio = sd.rec(int(DURACION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="float32")
    sd.wait()
    print("Grabación terminada.")
    return audio.flatten()

def transcribir(audio):
    segments, info = model.transcribe(audio, language="es")
    texto = " ".join([segment.text for segment in segments])
    return texto.strip()

if __name__ == "__main__":
    audio = grabar_audio()
    print("Transcribiendo...")
    texto = transcribir(audio)
    print(f"\nDijiste: {texto}")