"""El texto del sticker de enlace de cada historia (18/11/2026, pedidos de Tomix: "que los
nombres de los links no sean siempre 'ver curso'"; "que invente títulos teniendo en cuenta
mis títulos ganadores de los ads"; "que empiecen o terminen con algún emoji llamativo").

Medido en el emulador el 18/11:
- Instagram pasa el texto del sticker a MAYÚSCULAS.
- Entran ~37 caracteres (con letras anchas tipo W/M) antes del "...". Tope: MAX = 32
  (un emoji ocupa como 2 letras, se cuenta doble).

Cómo elige: el MISMO formato de los títulos de los ads que más clics sacaron
(gancho | llamado: HAZ CLICK, ENTRA YA, ENTRA AHORA...), con el descuento que muestra la
página de ESE curso (las 4 en 60% desde el 19/11). Gemini hace variantes en ese formato; si no
está o falla, sale uno de PLANTILLAS. Siempre con un emoji de los que usan los ads ganadores
al principio o al final. Sin tildes ni ñ si el emulador no tiene el teclado ADB (EMOJIS=False).
"""
import json, os, re, urllib.request

MAX = 32

# Títulos de los ads con más clics por vista (Meta Ads, 18/11; CTR entre paréntesis).
GANADORES = [
    "🎁80% OFF HOY 👉 (3,7%)",
    "💥80% de Descuento | ENTRA AHORA 👉 (3,6%)",
    "🎁 Obtén Bonos 👉 (3,3%)",
    "⏳ Oferta Exclusiva HOY | ENTRA YA 👉 (2,9%)",
    "🎓 Curso 100% Online | HAZ CLICK 👉 (2,4%)",
    "🔥Último Día | HAZ CLICK 👉 (2,4%)",
    "🔗Toca \"Más Información\" 👉 (2,2%)",
    "🌐informacion del curso (2,2%)",
]
# Los emojis de esos títulos (los que traccionan).
EMOJIS_GANADORES = ["🎁", "💥", "⏳", "🎓", "🔥", "🔗", "👉", "🌐"]

# Lo que muestra la página de cada curso (revisado en la página en vivo, 18/11).
DESCUENTO = {"hidroponia": "60%", "bonsai": "60%", "terrarios": "60%", "herbologia": "60%"}   # 19/11: las 4 en 60%

# Las mismas estructuras de los ganadores, con el descuento de cada curso.
PLANTILLAS = [
    "{d} OFF HOY | HAZ CLICK",
    "{d} DE DESCUENTO | ENTRA YA",
    "OFERTA EXCLUSIVA | ENTRA YA",
    "CURSO 100% ONLINE | HAZ CLICK",
    "{d} OFF + BONOS | ENTRA YA",
    "TOCA MAS INFORMACION",
    "INFORMACION DEL CURSO",
    "{d} OFF ESTA SEMANA | ENTRA",
    "CURSO ONLINE {d} OFF | ENTRA",
    "OBTEN TUS BONOS | HAZ CLICK",
]

# Promesas que la página NO hace: no pueden salir en el botón.
PROHIBIDO = re.compile(r"GRATIS|PLAZAS|CUPOS|INSCRITOS|ESTUDIANTES|ALUMNOS|\+\d{3}|\d+ BONO|"
                       r"CURA|SANA|DOLOR|ENFERMEDAD")
_SIN_TILDE = str.maketrans("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNaeiouun")


def _emojis_ok() -> bool:
    """El emulador escribe emojis y tildes solo con el teclado ADB instalado (ver
    historia_emulador.escribir). Sin él, el texto sale sin emojis ni tildes."""
    return os.getenv("TECLADO_ADB", "") == "1"


def largo(t: str) -> int:
    return sum(2 if ord(c) > 0x2000 else 1 for c in t)


def limpiar(t: str) -> str:
    t = (t or "").strip().strip('"').upper()
    t = re.sub(r"[^\w %+\-|!?.,:/\"]", "", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip(" |-")


def valido(t: str, nicho: str) -> bool:
    if not t or not (6 <= largo(t) <= MAX) or PROHIBIDO.search(t.translate(_SIN_TILDE)):
        return False
    # Un descuento que no es el de la página de este curso no puede salir.
    for pct in re.findall(r"(?<!\d)\d{2}%", t):     # "100% ONLINE" no es un descuento
        if pct != DESCUENTO.get(nicho, "60%"):
            return False
    return True


def con_emoji(t: str, i: int) -> str:
    if not _emojis_ok():
        return t.translate(_SIN_TILDE)
    e = EMOJIS_GANADORES[i % len(EMOJIS_GANADORES)]
    # Al final va 👉 (como los ads); al principio, el resto.
    t2 = f"{t} 👉" if e == "👉" else f"{e} {t}"
    return t2 if largo(t2) <= MAX else t


def _gemini(nicho: str, evitar: list[str]) -> str | None:
    claves = [os.getenv(k, "").strip() for k in ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3")]
    d = DESCUENTO.get(nicho, "60%")
    pedido = (
        "Estos son los títulos de anuncios que más clics sacaron (CTR entre paréntesis):\n- "
        + "\n- ".join(GANADORES) +
        f"\n\nEscribe UNA variante con EXACTAMENTE ese estilo (gancho corto | llamado a la acción en "
        f"mayúsculas como HAZ CLICK, ENTRA YA, ENTRA AHORA), para el botón de enlace de una historia de "
        f"Instagram del curso online de {nicho}. Sin emojis (los pongo yo). Máximo {MAX - 3} caracteres. "
        f"El único descuento que existe es {d} OFF. NO digas gratis, plazas, cupos, cantidades de alumnos "
        "ni cuántos bonos son. "
        f"No repitas ninguno de estos: {', '.join(evitar[-8:]) or 'ninguno'}.\n"
        "Responde SOLO con el texto."
    )
    intentos = [(k, m) for k in claves if k
                for m in ("gemini-flash-lite-latest", "gemini-flash-latest")][:4]
    for k, modelo in intentos:
        try:
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={k}",
                data=json.dumps({"contents": [{"parts": [{"text": pedido}]}],
                                 "generationConfig": {"temperature": 1.0}}).encode(),
                headers={"Content-Type": "application/json"})
            r = json.load(urllib.request.urlopen(req, timeout=15))
            t = limpiar(r["candidates"][0]["content"]["parts"][0]["text"].splitlines()[0])
            if valido(t, nicho) and largo(t) <= MAX - 3 and t not in evitar:
                return t
        except Exception:  # noqa: BLE001
            continue
    return None


def elegir(p: dict, usados: list[str] | None = None) -> str:
    """Texto para la historia del reel `p` (dict de publicados.json). `usados`: los últimos
    textos de ese nicho, para no repetir."""
    nicho = p.get("nicho", "")
    usados = usados or []
    semilla = len(usados) + sum(map(ord, p.get("id", "")))
    # Mitad plantilla de los ganadores, mitad variante de Gemini (si está).
    t = _gemini(nicho, usados) if semilla % 2 else None
    if not t:
        d = DESCUENTO.get(nicho, "60%")
        base = [x.format(d=d) for x in PLANTILLAS]
        libres = [x for x in base if not any(x in u for u in usados[-6:])] or base
        t = libres[semilla % len(libres)]
    return con_emoji(t, semilla)


if __name__ == "__main__":
    for n in DESCUENTO:
        for x in PLANTILLAS:
            assert valido(x.format(d=DESCUENTO[n]), n), (n, x)
            # que siempre entre el emoji (un emoji ocupa ~3 con el espacio)
            assert largo(x.format(d=DESCUENTO[n])) <= MAX - 3, ("sin lugar para el emoji", x)
    print("plantillas ok")
