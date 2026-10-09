"""
Prepara el texto de una respuesta para que Piper lo lea bien en voz alta.

Piper lee los números y símbolos "como se ven": "$50.00 USD" sale como
"cinco cero punto cero cero u ese de". Aquí se convierten a palabras ANTES
de mandarlo a Piper: "$50.00 USD" -> "cincuenta dólares".

Probar suelto:   python texto_para_voz.py "La cuota es de $50.00 USD y cubre el 100%"
"""
import re
import sys

# ---------------------------------------------------------------------------
# Números a palabras (español)
# ---------------------------------------------------------------------------
_UNIDADES = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve",
             "diez", "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete",
             "dieciocho", "diecinueve", "veinte", "veintiuno", "veintidós", "veintitrés",
             "veinticuatro", "veinticinco", "veintiséis", "veintisiete", "veintiocho", "veintinueve"]
_DECENAS = ["", "", "", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa"]
_CENTENAS = ["", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos",
             "seiscientos", "setecientos", "ochocientos", "novecientos"]


def _menor_que_mil(n):
    if n < 30:
        return _UNIDADES[n]
    if n < 100:
        d, u = divmod(n, 10)
        return _DECENAS[d] + ("" if u == 0 else " y " + _UNIDADES[u])
    if n == 100:
        return "cien"
    c, resto = divmod(n, 100)
    return _CENTENAS[c] + ("" if resto == 0 else " " + _menor_que_mil(resto))


def numero_a_palabras(n):
    """Entero (0 a 999.999.999) a palabras: 125 -> "ciento veinticinco"."""
    if n < 1000:
        return _menor_que_mil(n)
    if n < 1_000_000:
        miles, resto = divmod(n, 1000)
        texto = "mil" if miles == 1 else _menor_que_mil(miles) + " mil"
    else:
        millones, resto = divmod(n, 1_000_000)
        texto = "un millón" if millones == 1 else numero_a_palabras(millones) + " millones"
    if resto:
        texto += " " + numero_a_palabras(resto)
    # "veintiuno mil" -> "veintiún mil", "uno mil" no ocurre por el caso especial
    return texto.replace("veintiuno mil", "veintiún mil").replace("uno mil", "un mil")


def _apocope(palabras):
    """Delante de un sustantivo "uno" se dice "un": "veintiún módulos", "un dólar"."""
    if palabras.endswith("veintiuno"):
        return palabras[:-len("veintiuno")] + "veintiún"
    if palabras.endswith("uno"):
        return palabras[:-1]
    return palabras


def _entero(texto):
    return int(texto.replace(",", ""))


def _dinero(m):
    entero = _entero(m.group("entero"))
    centavos = int(m.group("centavos") or 0)
    palabras = _apocope(numero_a_palabras(entero))  # "veintiún dólares", "un dólar"
    texto = palabras + (" dólar" if entero == 1 else " dólares")
    if centavos:
        texto += " con " + numero_a_palabras(centavos) + " centavos"
    return texto


def _hora(m):
    """ "7:00 a.m." -> "siete de la mañana", "12:40 p.m." -> "doce y cuarenta del mediodía"."""
    hora, minutos = int(m.group(1)), int(m.group(2))
    sufijo = (m.group(3) or "").lower().replace(" ", "").replace(".", "")
    if hora > 12:  # formato 24 horas: "17:00" -> 5 de la tarde
        hora, sufijo = hora - 12, "pm"
    texto = "una" if hora == 1 else numero_a_palabras(hora)
    if minutos == 15:
        texto += " y cuarto"
    elif minutos == 30:
        texto += " y media"
    elif minutos:
        texto += " y " + numero_a_palabras(minutos)
    if sufijo in ("pm", "m"):
        if hora == 12:
            texto += " del mediodía"
        elif hora <= 6:
            texto += " de la tarde"
        else:
            texto += " de la noche"
    elif sufijo == "am":
        if hora == 12:
            texto += " de la medianoche"
        elif hora <= 4:
            texto += " de la madrugada"
        else:
            texto += " de la mañana"
    # "a las 12:00 m. También...": el punto de "m." también cerraba la oración.
    if (m.group(3) or "").endswith(".") and m.group(4):
        texto += "."
    return texto


def convertir_numeros(texto):
    # Horas: "7:00 a.m.", "12:40 p.m.", "5:00 p. m.", "17:00" (antes que los demás números)
    texto = re.sub(r"\b(\d{1,2}):(\d{2})(?:\s*(a\.?\s?m\.?|p\.?\s?m\.?|m\.)(?=\W|$))?(?=(\s+(?-i:[A-ZÁÉÍÓÚÑ¿¡]))?)", _hora, texto,
                   flags=re.IGNORECASE)
    # Dinero: "$50.00 USD", "$125.00 dólares", "$50", "50 USD", "26 dólares"
    numero = r"(?P<entero>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<centavos>\d{2}))?"
    moneda = r"(?:\s*(?:USD|US\$|dólares|dolares|dólar|dolar)\b)?"
    texto = re.sub(r"(?:US)?\$\s*" + numero + moneda, _dinero, texto)
    texto = re.sub(numero + r"\s*(?:USD|dólares|dolares|dólar|dolar)\b", _dinero, texto)
    # Porcentajes: "100%" -> "cien por ciento"
    texto = re.sub(r"(\d+)\s*%", lambda m: numero_a_palabras(int(m.group(1))) + " por ciento", texto)
    # Decimales: "7.0" -> "siete", "7.5" -> "siete punto cinco"
    texto = re.sub(r"\b(\d+)\.0+\b", lambda m: numero_a_palabras(int(m.group(1))), texto)
    texto = re.sub(r"\b(\d+)[.,](\d+)\b",
                   lambda m: numero_a_palabras(int(m.group(1))) + " punto " + numero_a_palabras(int(m.group(2))),
                   texto)
    # Ciclos en romano: "Ciclo I", "Ciclo II" -> "Ciclo uno", "Ciclo dos"
    romanos = {"I": "uno", "II": "dos", "III": "tres", "IV": "cuatro"}
    texto = re.sub(r"\b([Cc]iclos?)\s+(IV|III|II|I)\b", lambda m: m.group(1) + " " + romanos[m.group(2)], texto)
    # Cualquier otro entero: "21 módulos" -> "veintiún módulos", "ciclo 01" -> "ciclo uno"
    def _numero_suelto(m):
        palabras = numero_a_palabras(_entero(m.group(1)))
        return _apocope(palabras) if m.group(2) else palabras
    texto = re.sub(r"\b(\d{1,3}(?:,\d{3})+|\d+)\b(?=(\s+(?!(?:de|del|y|o|u|a|al|en|por|para|con|que|es|son)\b)[a-záéíóúñ])?)",
                   _numero_suelto, texto)
    return texto


# ---------------------------------------------------------------------------
# Siglas y términos técnicos
# ---------------------------------------------------------------------------
# Se escriben como se PRONUNCIAN. Si Piper dice mal alguna palabra, agrégala
# aquí. Ojo: distinguen mayúsculas, para no cambiar palabras normales.
TERMINOS_TECNICOS = {
    r"\bITCHA[- ]?(?:AGAPE|ÁGAPE)\b": "Itcha Ágape",
    r"\bITCHA\b": "Itcha",
    r"\b(?:AGAPE|ÁGAPE)\b": "Ágape",
    r"\bMINEDUCYT\b": "Minéd",
    r"\bMINED\b": "Minéd",
    r"\bMEGATEC\b": "Megatéc",
    r"\bEDUCAME\b": "Educáme",
    r"\bUES\b": "u e ese",
    r"\bUDB\b": "u de be",
    r"\bSSD\b": "disco sólido",
    r"\bHDD\b": "disco duro",
    r"(?<!memoria )\bRAM\b": "memoria RAM",
    r"\bCPU\b": "procesador",
    r"\b(\d+)\s*GB\b": r"\1 gigabytes",
    r"\b(\d+)\s*TB\b": r"\1 terabytes",
    r"(?i)\bWi-?Fi\b": "wifi",
    r"\bASP\.NET\b": "a ese pe punto net",
    r"\.NET\b": "punto net",
    r"\bC#": "C numeral",
    r"\bSQL\b": "ese cu ele",
    r"\bPHP\b": "pe hache pe",
    r"(?i)(entidad[- ]relaci[oó]n)\s*\(ER\)": r"\1",  # no repetirlo dos veces
    r"\bER\b": "entidad relación",
    r"\bLINUX\b": "Linux",
    r"\bUSD\b": "dólares",
    r"(?i)\bframeworks\b": "marcos de trabajo",
    r"(?i)\bframework\b": "marco de trabajo",
    r"\bJava\b(?!,)": "Java,",  # Piper a veces la dice de forma muy rápida/cortada; una pausa breve ayuda
}


def normalizar_terminos_tecnicos(texto):
    for patron, reemplazo in TERMINOS_TECNICOS.items():
        texto = re.sub(patron, reemplazo, texto)
    return texto


def limpiar_texto_para_voz(texto):
    texto = normalizar_terminos_tecnicos(texto)
    texto = convertir_numeros(texto)
    texto = re.sub(r'\*\*(.*?)\*\*', r'\1', texto)
    texto = re.sub(r'\*(.*?)\*', r'\1', texto)
    texto = re.sub(r'#{1,6}\s*', '', texto)
    texto = re.sub(r'^[-*•]\s+', '', texto, flags=re.MULTILINE)  # bullets con - o *
    texto = re.sub(r'\*', '', texto)         # cualquier asterisco suelto restante
    texto = texto.replace('`', '')          # comillas invertidas de código
    texto = texto.replace('::', ', ')        # doble dos puntos de namespaces PHP
    texto = texto.replace('->', ' ')         # flechas de acceso a métodos/propiedades
    texto = re.sub(r'\s*/\s*', ' o ', texto)  # "MINED / MEGATEC" -> "MINED o MEGATEC"
    texto = re.sub(r'\s*\n\s*', ' ', texto)  # saltos de línea
    texto = re.sub(r'\s{2,}', ' ', texto)    # colapsa espacios dobles que queden
    return texto.strip()


if __name__ == "__main__":
    print(limpiar_texto_para_voz(" ".join(sys.argv[1:]) or
                                 "La cuota es de $50.00 USD, la beca MINED / MEGATEC cubre el 100% "
                                 "y la graduación cuesta $125.00 dólares. Nota mínima 7.0, Ciclo II, "
                                 "16 GB de RAM, 160 horas, 21 módulos, ciclo 01 del año 2026."))
