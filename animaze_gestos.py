"""
Le manda órdenes a Animaze por su API local (WebSocket).

- Usa casi nada de memoria: solo abre una conexión y envía mensajes cortos.
- Si Animaze no está abierto o su API está apagada, no pasa nada:
  el script sigue normal y simplemente no hay gestos.

Necesita:   pip install websocket-client
Para ver la lista de tus animaciones de reposo:     python animaze_gestos.py
Para probar una por su número (mira Animaze):       python animaze_gestos.py 3
"""
import json
import sys

import websocket  # paquete "websocket-client"

URL = "ws://localhost:9000"   # puerto por defecto de la API de Animaze
ID = "AliceScript"            # nombre cualquiera con el que se identifica el script

_ws = None


def _conectar():
    global _ws
    try:
        _ws = websocket.create_connection(URL, timeout=0.5)
    except Exception:
        _ws = None
    return _ws


def _vaciar():
    """Descarta respuestas viejas que hayan quedado sin leer."""
    try:
        _ws.settimeout(0.02)
        while True:
            _ws.recv()
    except Exception:
        pass


def _enviar(comando, espera=0.3, vaciar=False):
    """Envía el comando y devuelve la respuesta (o None). Nunca lanza errores."""
    global _ws
    for _ in range(2):  # un reintento por si la conexión se había caído
        if _ws is None and _conectar() is None:
            return None
        try:
            if vaciar:
                _vaciar()
            _ws.settimeout(espera)
            _ws.send(json.dumps(comando))
        except Exception:
            _ws = None
            continue
        try:
            return _ws.recv()
        except Exception:
            return None  # Animaze no respondió a tiempo; la orden ya se envió
    return None


def idle(indice):
    """Cambia la animación de reposo. Si indice es None, no hace nada."""
    if indice is None:
        return
    _enviar({"action": "TriggerIdle", "id": ID, "index": indice})


def _buscar_lista(dato):
    """Busca dentro de la respuesta una lista de animaciones. Devuelve [(numero, nombre), ...] o None."""
    if isinstance(dato, list) and dato:
        if all(isinstance(x, str) for x in dato):
            return list(enumerate(dato))
        if all(isinstance(x, dict) for x in dato):
            for clave in ("name", "Name", "itemName", "title"):
                if all(clave in x for x in dato):
                    return [(x.get("index", i), x[clave]) for i, x in enumerate(dato)]
        for x in dato:
            r = _buscar_lista(x)
            if r:
                return r
    elif isinstance(dato, dict):
        for v in dato.values():
            r = _buscar_lista(v)
            if r:
                return r
    return None


def accion_especial(indice):
    """Dispara una animación de la pestaña "Animaciones" (Hello, Ok, Shrug...),
    la que en Animaze se activa con teclas como Q, W, E. Se reproduce una vez
    y el avatar vuelve solo a su animación de reposo. Si indice es None, no hace nada."""
    if indice is None:
        return
    _enviar({"action": "TriggerSpecialAction", "id": ID, "index": indice})


def listar_acciones_especiales():
    """Devuelve la respuesta cruda de Animaze con la lista de animaciones especiales
    (las de la pestaña "Animaciones", no las de "Inactivos")."""
    return _enviar({"action": "GetSpecialActions", "id": ID}, espera=2.0, vaciar=True)


def listar_idles():
    """Devuelve la respuesta cruda de Animaze con la lista de animaciones de reposo."""
    return _enviar({"action": "GetIdleAnims", "id": ID}, espera=2.0, vaciar=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "especial":
        if len(sys.argv) == 2:
            respuesta = listar_acciones_especiales()
        else:
            numero = int(sys.argv[2])
            respuesta = _enviar({"action": "TriggerSpecialAction", "id": ID, "index": numero}, espera=2.0, vaciar=True)
            print(f"Orden enviada: animación especial número {numero}. Respuesta de Animaze: {respuesta}")
            sys.exit()
    elif len(sys.argv) > 1:
        # Modo prueba: dispara la animación de reposo con ese número y muestra la respuesta.
        numero = int(sys.argv[1])
        respuesta = _enviar({"action": "TriggerIdle", "id": ID, "index": numero}, espera=2.0, vaciar=True)
        print(f"Orden enviada: animación número {numero}. Respuesta de Animaze: {respuesta}")
        sys.exit()
    else:
        respuesta = listar_idles()
    if respuesta is None:
        print("No hubo respuesta. Revisa que Animaze esté abierto y que su API esté activada")
        print("(Ajustes > Animaze API) y que el puerto sea el de la constante URL.")
    else:
        try:
            datos = json.loads(respuesta)
        except ValueError:
            print(respuesta)
            sys.exit()
        lista = _buscar_lista(datos)
        if lista:
            print("Animaciones de reposo (número: nombre):")
            for numero, nombre in lista:
                print(f"  {numero}: {nombre}")
            print("\nProbar una:  python animaze_gestos.py NUMERO")
        else:
            print(json.dumps(datos, indent=2, ensure_ascii=False))