"""El texto del sticker de enlace de cada historia (18/11/2026, pedido de Tomix: "que los
nombres de los links no sean siempre 'ver curso'; que invente títulos teniendo en cuenta mis
títulos ganadores de los ads, que inciten al click, y que sepa cuántos caracteres entran
antes de que se vea '...'").

Medido en el emulador el 18/11:
- Instagram pasa el texto del sticker a MAYÚSCULAS.
- Entran ~37 caracteres (con letras anchas tipo W/M) antes del "...". Tope: MAX = 32.
- El emulador escribe como un teclado básico: sin tildes, sin ñ y sin emojis.

Cómo elige: Gemini inventa uno nuevo para cada historia, con los títulos que más clics
sacaron en los ads como ejemplo (GANADORES). Se valida (largo, solo letras sin tilde,
números y % + - |) y no puede prometer lo que la página no dice (la página muestra 60% OFF
y bonos). Si Gemini no está o falla, sale uno del BANCO del nicho, sin repetir los últimos.
"""
import json, os, re, urllib.request

MAX = 32
PERMITIDO = re.compile(r"^[A-Z0-9 %+\-|!?.,:/]+$")

# Los que más clics por vista sacaron en los ads (CTR, Meta Ads, 18/11).
GANADORES = [
    "80% OFF HOY | +2640 estudiantes ya inscritos (3,7%)",
    "80% de Descuento | ENTRA AHORA (3,6%)",
    "Obten 3 Bonos GRATIS (3,3%)",
    "Oferta Exclusiva HOY | ENTRA YA (2,9%)",
    "Curso 100% Online | HAZ CLICK (2,4%)",
    "Ultimo Dia | HAZ CLICK (2,4%)",
    "Toca Mas Informacion (2,2%)",
    "informacion del curso (2,2%)",
]

TEMA = {"hidroponia": "hidroponia (cultivar sin tierra)", "bonsai": "bonsai",
        "terrarios": "terrarios", "herbologia": "plantas medicinales"}

# Lo único que se puede prometer (lo que dicen las páginas): 60% OFF, bonos, online,
# clases en video + PDF, acceso inmediato, pago único, garantía de 7 días, certificado.
BANCO = {
    "hidroponia": ["60% OFF HOY | ENTRA YA", "QUIERO MI HUERTO", "CULTIVA SIN TIERRA", "VER PRECIO EN TU MONEDA",
                   "CURSO ONLINE | HAZ CLICK", "EMPIEZA HOY | 60% OFF", "QUIERO APRENDER", "CLASES + PDF | ENTRA",
                   "ACCESO INMEDIATO", "MIRA EL CURSO", "60% OFF + BONOS", "QUIERO MI SISTEMA NFT",
                   "HUERTO EN CASA | ENTRA", "GARANTIA 7 DIAS | ENTRA", "OFERTA DE HOY", "INFO DEL CURSO"],
    "bonsai": ["60% OFF HOY | ENTRA YA", "QUIERO MI BONSAI", "APRENDE BONSAI DESDE CERO", "VER PRECIO EN TU MONEDA",
               "CURSO ONLINE | HAZ CLICK", "EMPIEZA HOY | 60% OFF", "QUIERO APRENDER", "60% OFF + BONOS",
               "ACCESO INMEDIATO", "MIRA EL CURSO", "MI PRIMER BONSAI", "OFERTA DE HOY",
               "GARANTIA 7 DIAS | ENTRA", "INFO DEL CURSO", "CLASES + PDF | ENTRA", "QUIERO EL CURSO"],
    "terrarios": ["60% OFF HOY | ENTRA YA", "QUIERO MI TERRARIO", "ARMA TU TERRARIO", "VER PRECIO EN TU MONEDA",
                  "CURSO ONLINE | HAZ CLICK", "EMPIEZA HOY | 60% OFF", "QUIERO APRENDER", "60% OFF + BONOS",
                  "ACCESO INMEDIATO", "MIRA EL CURSO", "MINI JARDIN EN UN FRASCO", "OFERTA DE HOY",
                  "GARANTIA 7 DIAS | ENTRA", "INFO DEL CURSO", "CLASES + PDF | ENTRA", "QUIERO EL CURSO"],
    "herbologia": ["60% OFF HOY | ENTRA YA", "QUIERO APRENDER", "BIENESTAR NATURAL EN CASA", "VER PRECIO EN TU MONEDA",
                   "CURSO ONLINE | HAZ CLICK", "EMPIEZA HOY | 60% OFF", "REMEDIOS NATURALES", "60% OFF + BONOS",
                   "ACCESO INMEDIATO", "MIRA EL CURSO", "MI BOTIQUIN NATURAL", "OFERTA DE HOY",
                   "GARANTIA 7 DIAS | ENTRA", "INFO DEL CURSO", "CLASES + PDF | ENTRA", "QUIERO EL CURSO"],
}

_SIN_TILDE = str.maketrans("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNaeiouun")
# Promesas que la página NO hace: no pueden salir en el botón.
PROHIBIDO = re.compile(r"80|GRATIS|PLAZAS|CUPOS|ULTIMO|ULTIMAS|INSCRITOS|ESTUDIANTES|\+\d{3}|\d+ BONO|CURA|SANA|DOLOR|ENFERMEDAD")

# Un estilo distinto por historia, para que no salga siempre "60% OFF | ENTRA YA".
ESTILOS = [
    "un beneficio concreto del tema (lo que la persona va a lograr), sin hablar de descuento",
    "el descuento de 60% con urgencia de hoy",
    "curiosidad: que den ganas de ver qué hay del otro lado",
    "una acción en primera persona, como si la dijera quien toca (ej. QUIERO ...)",
    "los bonos y el acceso inmediato",
]


def limpiar(t: str) -> str:
    t = (t or "").strip().strip('"').translate(_SIN_TILDE).upper()
    t = re.sub(r"[^A-Z0-9 %+\-|!?.,:/]", "", t)
    return re.sub(r"\s+", " ", t).strip(" |-")


def valido(t: str) -> bool:
    return bool(t) and 6 <= len(t) <= MAX and bool(PERMITIDO.match(t)) and not PROHIBIDO.search(t)


def _gemini(nicho: str, evitar: list[str], estilo: str) -> str | None:
    claves = [os.getenv(k, "").strip() for k in ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3")]
    pedido = (
        f"Escribe UN texto para el botón de enlace de una historia de Instagram que vende un curso online de "
        f"{TEMA.get(nicho, nicho)}. Tiene que dar ganas de tocar el enlace. Enfoque: {estilo}.\n"
        f"Inspírate en estos títulos de anuncios que más clics sacaron (CTR entre paréntesis):\n- "
        + "\n- ".join(GANADORES) +
        f"\n\nReglas: máximo {MAX} caracteres; sin tildes, sin ñ y sin emojis; solo letras, números, espacios y % + - |. "
        "Lo único que puedes prometer: 60% OFF, bonos, curso online, clases en video y PDF, acceso inmediato, "
        "pago único, garantía de 7 días. NO digas 80%, gratis, plazas, cupos, último día, cantidades de alumnos "
        "ni cuántos bonos son. No prometas curar, sanar ni aliviar enfermedades o dolores. "
        f"No repitas ninguno de estos: {', '.join(evitar[-8:]) or 'ninguno'}.\n"
        "Responde SOLO con el texto."
    )
    # Como mucho 4 intentos cortos: si Gemini está saturado, sale uno del banco enseguida
    # (antes: 3 claves x 3 modelos x 40 s = minutos por historia).
    intentos = [(k, m) for k in claves if k
                for m in ("gemini-flash-lite-latest", "gemini-flash-latest")][:4]
    for k, modelo in intentos:
            try:
                req = urllib.request.Request(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={k}",
                    data=json.dumps({"contents": [{"parts": [{"text": pedido}]}],
                                     "generationConfig": {"temperature": 1.1}}).encode(),
                    headers={"Content-Type": "application/json"})
                d = json.load(urllib.request.urlopen(req, timeout=15))
                t = limpiar(d["candidates"][0]["content"]["parts"][0]["text"].splitlines()[0])
                if valido(t) and t not in evitar:
                    return t
            except Exception:  # noqa: BLE001
                continue
    return None


def elegir(p: dict, usados: list[str] | None = None) -> str:
    """Texto para la historia del reel `p` (dict de publicados.json). `usados`: los últimos
    textos de ese nicho, para no repetir."""
    nicho = p.get("nicho", "")
    usados = usados or []
    estilo = ESTILOS[(len(usados) + sum(map(ord, p.get("id", "")))) % len(ESTILOS)]
    t = _gemini(nicho, usados, estilo)
    if t:
        return t
    banco = BANCO.get(nicho) or BANCO["hidroponia"]
    libres = [x for x in banco if x not in usados[-len(banco) + 1:]] or banco
    # Determinístico por reel: el mismo reel da el mismo texto si se reintenta.
    return libres[sum(map(ord, p.get("id", ""))) % len(libres)]


if __name__ == "__main__":
    for n in BANCO:
        assert all(valido(x) for x in BANCO[n]), [x for x in BANCO[n] if not valido(x)]
    print("banco ok;", {n: len(v) for n, v in BANCO.items()})
    print("ejemplo:", elegir({"nicho": "hidroponia", "id": "stk-hidro-1"}))
