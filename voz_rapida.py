"""
Hace que Alice empiece a hablar antes.

En vez de generar la voz de TODA la respuesta y recién entonces reproducirla,
parte la respuesta en frases: genera la primera, empieza a reproducirla, y mientras
suena va generando las siguientes. Así el silencio antes de que hable es mucho menor.

Usa lo que ya tienes: Piper, sounddevice, soundfile y animaze_gestos.
"""
import os
import queue
import re
import subprocess
import threading
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

import animaze_gestos


def partir_en_frases(texto, minimo=40):
    """Parte el texto en trozos de una o varias frases. Los trozos muy cortos se
    juntan con el siguiente, porque cada llamada a Piper tiene un costo fijo."""
    frases = re.split(r"(?<=[.!?…])\s+", texto.strip())
    trozos, actual = [], ""
    for frase in frases:
        actual = (actual + " " + frase).strip()
        if len(actual) >= minimo:
            trozos.append(actual)
            actual = ""
    if actual:
        if trozos:
            trozos[-1] += " " + actual
        else:
            trozos.append(actual)
    return trozos


def _indice_cable():
    for i, dev in enumerate(sd.query_devices()):
        if "CABLE Input" in dev["name"]:
            return i
    return None


def hablar(texto, piper_exe, voz_modelo, archivo_salida, idle_hablando=None, idle_reposo=None, velocidad=1.0,
           gesto_especial=None, repetir_gesto_cada=None):
    """gesto_especial: animación especial (ej. "Hello") que se dispara justo cuando
    empieza a sonar la voz, no antes. repetir_gesto_cada: cada cuántos segundos se
    vuelve a mandar idle_hablando mientras habla, para animaciones que no se
    repiten solas en Animaze (None = solo una vez)."""
    trozos = partir_en_frases(texto)
    if not trozos:
        return

    cola = queue.Queue()

    def productor():
        try:
            for trozo in trozos:
                try:
                    os.remove(archivo_salida)  # así nunca se reproduce audio viejo por error
                except FileNotFoundError:
                    pass
                subprocess.run(
                    [piper_exe, "--model", voz_modelo, "--output_file", archivo_salida,
                     "--length_scale", str(velocidad)],
                    input=trozo.encode("utf-8"),
                    capture_output=True,
                )
                if os.path.exists(archivo_salida):
                    cola.put(sf.read(archivo_salida))
                else:
                    print("Aviso: Piper no generó audio para:", trozo[:50])
        except Exception as e:
            print("Aviso: falló la generación de voz:", e)
        finally:
            cola.put(None)  # señal de que ya no hay más

    hilo = threading.Thread(target=productor, daemon=True)
    hilo.start()

    indice_cable = _indice_cable()
    if indice_cable is None:
        print("Advertencia: No se encontró 'CABLE Input'. Reproduciendo en salida por defecto.")

    # Se abre UNA sola salida de audio para toda la respuesta (antes se abría una
    # por frase, y eso metía retraso al empezar y cortecitos entre frases).
    stream = None
    segundos_desde_gesto = 0.0
    espera_total = 0.0
    try:
        while True:
            inicio_espera = time.perf_counter()
            item = cola.get()
            if stream is not None:
                # Si hubo que esperar a Piper con la voz ya sonando, se oye un hueco.
                espera_total += time.perf_counter() - inicio_espera
            if item is None:
                break
            data, samplerate = item
            data = np.asarray(data, dtype="float32")
            if data.ndim == 1:
                data = data.reshape(-1, 1)

            if stream is None:
                stream = sd.OutputStream(samplerate=samplerate, channels=data.shape[1],
                                         dtype="float32", device=indice_cable)
                stream.start()
                # Los gestos se mandan ahora, con el audio ya listo para sonar.
                if gesto_especial is not None:
                    animaze_gestos.accion_especial(gesto_especial)
                animaze_gestos.idle(idle_hablando)

            # Se escribe en pedazos de medio segundo para poder refrescar el gesto
            # en medio de una frase larga.
            pedazo = int(samplerate * 0.5)
            for i in range(0, len(data), pedazo):
                if repetir_gesto_cada and segundos_desde_gesto >= repetir_gesto_cada:
                    animaze_gestos.idle(idle_hablando)
                    segundos_desde_gesto = 0.0
                bloque = data[i:i + pedazo]
                stream.write(bloque)
                segundos_desde_gesto += len(bloque) / samplerate
    finally:
        if stream is not None:
            stream.stop()   # espera a que termine de sonar lo que queda en el búfer
            stream.close()
        animaze_gestos.idle(idle_reposo)
        hilo.join(timeout=30)
    if espera_total > 0.5:
        print(f"(Aviso: la voz se quedó esperando a Piper {espera_total:.1f} s en total; "
              "la PC va justa de CPU mientras habla.)")