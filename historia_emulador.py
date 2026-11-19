"""Sube una HISTORIA de Instagram con sticker de link usando el emulador de Android
(14/11/2026, pedido de Tomix). La API de Meta no deja poner el sticker de link: por eso se
maneja la app de Instagram dentro del emulador (AVD eugenia_ig), tocando la pantalla.

Requisitos: el emulador prendido (o lo prende este script) y la sesión de Instagram de la
cuenta abierta en la app (la abre Tomix a mano; nunca se escriben contraseñas).

Uso:
    python historia_emulador.py --nicho terrarios --imagen foto.jpg|reel.mp4 [--cuenta terrario.academia] [--y 0.70]
    ... --sin-publicar   # deja todo listo sin publicar

--y es la altura del sticker (0 arriba, 1 abajo). En los reels va DEBAJO de los
subtítulos (que están al 59%): logo, mockup, subtítulos, link (pedido de Tomix, 14/11).
"""
import argparse, os, re, subprocess, sys, time
from pathlib import Path

SDK = Path(os.environ.get("ANDROID_SDK_ROOT", r"C:/Users/Tomix/Android/Sdk"))
# Corre en la PC (Windows) y en GitHub (Linux, historias en la nube, 18/11).
_EXE = ".exe" if os.name == "nt" else ""
ADB = str(SDK / "platform-tools" / f"adb{_EXE}")
EMU = str(SDK / "emulator" / f"emulator{_EXE}")
AVD = "eugenia_ig"
BASE = "https://conocimientosdigital.pages.dev/"


def adb(*a, salida=True):
    r = subprocess.run([ADB, "-s", "emulator-5554", *a], capture_output=True, text=True, encoding="utf-8", errors="ignore")
    return r.stdout if salida else r.returncode


def prender():
    if "emulator-5554\tdevice" in subprocess.run([ADB, "devices"], capture_output=True, text=True).stdout:
        return
    env = dict(os.environ, ANDROID_SDK_ROOT=str(SDK), ANDROID_HOME=str(SDK))
    subprocess.Popen([EMU, "-avd", AVD, "-no-snapshot-load"], env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=0x00000008 if os.name == "nt" else 0)
    for _ in range(60):
        time.sleep(5)
        if adb("shell", "getprop", "sys.boot_completed").strip() == "1":
            time.sleep(10)
            return
    raise SystemExit("el emulador no terminó de prender")


def nodos():
    adb("shell", "uiautomator", "dump", "/sdcard/ui.xml")
    x = adb("shell", "cat", "/sdcard/ui.xml")
    out = []
    for n in re.finditer(r"<node [^>]*>", x):
        s = n.group(0)
        b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', s)
        if not b:
            continue
        t, dsc = re.search(r' text="([^"]*)"', s), re.search(r'content-desc="([^"]*)"', s)
        out.append({"text": t.group(1) if t else "", "desc": dsc.group(1) if dsc else "",
                    "edit": "EditText" in s, "b": tuple(map(int, b.groups()))})
    return out


def buscar(patron, ns=None):
    for n in ns or nodos():
        if re.search(patron, n["text"], re.I) or re.search(patron, n["desc"], re.I):
            return n
    return None


def tocar(n, dx=None):
    a, b, c, d = n["b"]
    x = c - dx if dx else (a + c) // 2
    adb("shell", "input", "tap", str(x), str((b + d) // 2))


def tocar_texto(patron, espera=20):
    for _ in range(espera):
        n = buscar(patron)
        if n:
            tocar(n); return True
        time.sleep(1)
    return False


def escribir(t):
    # Entre comillas simples: si no, el shell del Android corta en | & ; ( ) (18/11: con
    # "60% OFF HOY | HAZ CLICK" quedaba solo "60% OFF HOY").
    t = t.replace("'", "").replace(" ", "%s")
    adb("shell", f"input text '{t}'")


def _icono_color(st) -> bool:
    """True si el ícono de la cadena del sticker está en los colores de Instagram
    (naranja/rosa). Se mira el cuadrado del ícono, a la izquierda del sticker."""
    import io
    from PIL import Image
    png = subprocess.run([ADB, "-s", "emulator-5554", "exec-out", "screencap", "-p"],
                         capture_output=True).stdout
    im = Image.open(io.BytesIO(png)).convert("RGB")
    a, b, c, d = st["b"]
    caja = im.crop((a + 5, b + 10, a + (d - b), d - 10))
    rosas = sum(1 for r, g, bl in caja.getdata() if r > 200 and g < 120 and bl > 90)
    naranjas = sum(1 for r, g, bl in caja.getdata() if r > 220 and 70 < g < 170 and bl < 90)
    return rosas > 20 and naranjas > 10


def estilo_color(st):
    """El sticker de enlace cambia de aspecto cada vez que se toca (4 estilos: azul,
    transparente, negro, y con la cadena en colores de Instagram). Tomix (18/11) quiere el de
    colores de Instagram: se toca hasta llegar a ese, comprobándolo por el color del ícono."""
    for _ in range(5):
        if _icono_color(st):
            return True
        a, b, c, d = st["b"]
        adb("shell", "input", "tap", str((a + c) // 2), str((b + d) // 2))
        time.sleep(1.5)
        st = buscar(r"^Sticker\. ") or st
    return _icono_color(st)


# la ubicación se rechaza siempre ("Don’t allow"): no hace falta para las historias
CARTELES = r"^(OK|Not now|Ahora no|Aceptar|Entendido|Got it|Dismiss|Cerrar|Continue|Continuar|Don.t allow|No permitir|Skip|Omitir)$"


def cerrar_carteles(ns=None):
    """Cierra los avisos que Instagram muestra a veces (archivo de historias, guardar
    sesión, etc.). True si cerró alguno."""
    n = buscar(CARTELES, ns)
    if n:
        tocar(n); time.sleep(1.5); return True
    return False


def _lista_cuentas():
    """Abre la lista de cuentas (mantener apretado el ícono del perfil) y la devuelve:
    el primer usuario es la cuenta activa."""
    for _ in range(25):
        ns = nodos()
        if cerrar_carteles(ns):
            continue
        tab = next((n for n in ns if n["desc"] in ("Profile", "Perfil")), None)
        if tab:
            a, b, c, d = tab["b"]
            x, y = (a + c) // 2, (b + d) // 2
            adb("shell", "input", "swipe", str(x), str(y), str(x), str(y), "1200")
            time.sleep(2.5)
            ns = nodos()
            us = [n for n in ns if re.fullmatch(r"[a-z0-9._]+", n["text"])]
            if us:
                return us, ns
        time.sleep(1)
    raise SystemExit("no pude abrir la lista de cuentas de Instagram")


def cambiar_cuenta(usuario):
    """Pasa a la cuenta pedida. Las 4 cuentas están abiertas en la app del emulador
    (Tomix, 14/11). Si Instagram pide la contraseña, se corta: la pone Tomix."""
    adb("shell", "am", "force-stop", "com.instagram.android")
    adb("shell", "monkey", "-p", "com.instagram.android", "-c", "android.intent.category.LAUNCHER", "1")
    time.sleep(6)
    us, ns = _lista_cuentas()
    if us[0]["text"] == usuario:
        adb("shell", "input", "keyevent", "4"); time.sleep(1)
        return
    destino = next((n for n in us if n["text"] == usuario), None)
    if not destino:
        adb("shell", "input", "keyevent", "4")
        raise SystemExit(f"la cuenta {usuario} no está en el Instagram del emulador")
    tocar(destino); time.sleep(6)
    if buscar(r"^(Password|Contraseña)$"):
        raise SystemExit(f"Instagram pide la contraseña de {usuario}: hay que entrar a mano")
    us, ns = _lista_cuentas()
    activa = us[0]["text"]
    adb("shell", "input", "keyevent", "4"); time.sleep(1)
    if activa != usuario:
        raise SystemExit(f"no cambió de cuenta (quedó {activa})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nicho", required=True)
    ap.add_argument("--imagen", required=True)
    ap.add_argument("--texto", default="VER CURSO")
    ap.add_argument("--sck", default="historia")
    ap.add_argument("--sin-publicar", action="store_true")
    ap.add_argument("--cuenta", default="")
    ap.add_argument("--y", type=float, default=0.0, help="altura del sticker, 0-1 (0 = donde lo deja Instagram)")
    a = ap.parse_args()

    return publicar(a.nicho, a.imagen, a.texto, a.sck, a.cuenta, a.y, a.sin_publicar)


def publicar(nicho, archivo, texto="VER CURSO", sck="historia", cuenta="", y=0.0, sin_publicar=False):
    url = f"{BASE}{nicho}?sck={sck}"
    prender()
    if cuenta:
        cambiar_cuenta(cuenta)
    es_video = Path(archivo).suffix.lower() in (".mp4", ".mov")
    tipo = "video" if es_video else "images"
    nombre = f"historia_{int(time.time())}{Path(archivo).suffix.lower()}"
    adb("push", archivo, f"/sdcard/Pictures/{nombre}")
    adb("shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
        "-d", f"file:///sdcard/Pictures/{nombre}")
    mid = None
    for _ in range(10):
        time.sleep(1)
        m = re.search(r"_id=(\d+), _display_name=" + re.escape(nombre),
                      adb("shell", "content", "query", "--uri", f"content://media/external/{tipo}/media",
                          "--projection", "_id:_display_name"))
        if m:
            mid = m.group(1); break
    if not mid:
        raise SystemExit("la imagen no apareció en la galería del emulador")

    adb("shell", "am", "start", "-a", "com.instagram.share.ADD_TO_STORY", "-t", "video/mp4" if es_video else "image/jpeg",
        "-d", f"content://media/external/{tipo}/media/{mid}", "--grant-read-uri-permission",
        "-p", "com.instagram.android")
    # editor listo (y permisos que la app pida la primera vez)
    for _ in range(30):
        ns = nodos()
        p = buscar(r"^(While using the app|Allow all|Mientras la app está en uso|Permitir todo)$", ns)
        if p:
            tocar(p); time.sleep(1); continue
        if buscar(r"^(Stickers)$", ns):
            break
        time.sleep(1)
    else:
        raise SystemExit("no abrió el editor de historias (¿la sesión de Instagram está abierta?)")

    # sacar la música sugerida (la cruz está en la punta derecha del recuadro de la canción)
    ns = nodos()
    sug = buscar(r"^(Suggested audio|Audio sugerido)$", ns)
    if sug:
        chips = [n for n in ns if n["b"][3] <= sug["b"][1] + 5 and n["b"][1] < sug["b"][1] and
                 n["b"][2] - n["b"][0] > 250 and n["b"][0] > 200 and n["b"][2] < 900]
        if chips:
            tocar(max(chips, key=lambda n: n["b"][2] - n["b"][0]), dx=36); time.sleep(1)

    if not tocar_texto(r"^Stickers$") or not tocar_texto(r"^Link Sticker$|^Sticker de enlace$"):
        raise SystemExit("no encontré el sticker de link")
    time.sleep(2)
    campos = [n for n in nodos() if n["edit"]]
    tocar(campos[0]); time.sleep(0.5); escribir(url); time.sleep(1)
    # a veces se pierde la última letra al escribir: se revisa y se reescribe (14/11)
    for _ in range(3):
        c0 = [n for n in nodos() if n["edit"]]
        if c0 and c0[0]["text"].strip() == url:
            break
        if c0:
            tocar(c0[0]); adb("shell", "input", "keyevent", "KEYCODE_MOVE_END")
            adb("shell", "input", "keyevent", "--longpress", *(["KEYCODE_DEL"] * 1))
            for _ in range(len(c0[0]["text"]) + 5):
                adb("shell", "input", "keyevent", "KEYCODE_DEL")
            escribir(url); time.sleep(1)
    tocar_texto(r"^(Customize sticker text|Personalizar texto del sticker)$")
    time.sleep(1)
    campos = [n for n in nodos() if n["edit"]]
    if len(campos) > 1:
        tocar(campos[1]); time.sleep(0.5); escribir(texto)
    if not tocar_texto(r"^(Done|Listo)$", 3):
        # con algunos videos el botón es un ✓ sin texto, arriba a la derecha de "Add link" (14/11)
        t = buscar(r"^(Add link|Agregar enlace)$")
        y = (t["b"][1] + t["b"][3]) // 2 if t else 593
        adb("shell", "input", "tap", "1005", str(y))
    time.sleep(2)
    st = buscar(r"^Sticker\. ")
    if not st:
        raise SystemExit("el sticker no quedó puesto")
    if not estilo_color(st):
        print("aviso: no pude dejar el sticker en colores de Instagram; sale como está")
    st = buscar(r"^Sticker\. ") or st
    if y:
        # se arrastra manteniendo apretado; la historia ocupa el ancho entero (alto = ancho*16/9)
        # el arrastre no es exacto: se mide dónde quedó y se corrige (hasta 4 veces)
        meta = int(1080 * 16 / 9 * y)
        for _ in range(4):
            a_, b_, c_, d_ = st["b"]
            x0, y0 = (a_ + c_) // 2, (b_ + d_) // 2
            if abs(y0 - meta) < 30:
                break
            adb("shell", "input", "swipe", str(x0), str(y0), str(x0), str(y0 + (meta - y0)), "1800")
            time.sleep(1.5)
            st = buscar(r"^Sticker\. ") or st
    adb("exec-out", "screencap", "-p")  # deja la pantalla viva
    if sin_publicar:
        print("listo para publicar (no se publicó)"); return 0
    if not tocar_texto(r"^(Your story|Your stories|Tu historia|Tus historias)$"):
        raise SystemExit("no encontré el botón de publicar")
    time.sleep(12)
    cerrar_carteles()
    print(f"historia publicada con link {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
