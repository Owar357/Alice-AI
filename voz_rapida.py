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


def hablar(texto, piper_exe, voz_modelo, archivo_salida, idle_hablando=None, idle_reposo=None):
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
                    [piper_exe, "--model", voz_modelo, "--output_file", archivo_salida],
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

    gesto_puesto = False
    try:
        while True:
            item = cola.get()
            if item is None:
                break
            data, samplerate = item
            if not gesto_puesto:
                animaze_gestos.idle(idle_hablando)
                gesto_puesto = True
            sd.play(data, samplerate, device=indice_cable)
            sd.wait()
    finally:
        animaze_gestos.idle(idle_reposo)
        hilo.join(timeout=30)
