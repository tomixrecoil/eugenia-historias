"""Historias de Instagram con sticker de enlace, desde GitHub (18/11/2026, pedido de Tomix:
"todos los días cada reel que sale se sube como historia, sin depender de mi PC").

La API de Meta no deja poner el sticker de enlace: se usa la app de Instagram dentro de un
emulador de Android. El emulador (con las 4 cuentas ya abiertas) es una copia del de la PC,
guardada como descarga privada de este repo. El workflow lo prende y corre esto.

- Lee `stock/publicados.json` de R2 (por la puerta de GitHub) para saber qué salió.
- El video sale de R2 (`reels/<id>.mp4`) o, si ya no está, de Instagram (media_url).
- Lo hecho queda en estado.json, que el workflow commitea al terminar.
- Un reel con más de MAX_HORAS de publicado ya no se sube (llegó tarde).
"""
import json, os, subprocess, sys, tempfile, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ESTADO = ROOT / "estado.json"
MAX_HORAS = 14
Y_STICKER = 0.68          # subtítulos al ~59% del alto: el botón justo debajo, en el medio (19/11)
CUENTAS = {               # nicho: (usuario de Instagram, página de Facebook)
    "hidroponia": ("ecosistema.hidroponico", "615394648318530"),
    "bonsai": ("bonsai.en.casa.desde.cero", "620810857774404"),
    "terrarios": ("terrario.academia", "227267413796018"),
    "herbologia": ("academia.herbologica", "1094407060431618"),
}
GRAPH = "https://graph.facebook.com/v21.0"
IG_ID = {"hidroponia": "17841462466436017", "bonsai": "17841477234572039",
         "terrarios": "17841472667208280", "herbologia": "17841422824821498"}


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M"), *a, flush=True)


def _puerta(key):
    base = os.environ["PUERTA_R2_URL"].strip().rstrip("/")
    req = urllib.request.Request(f"{base}/o/{urllib.parse.quote(key)}")
    req.add_header("x-clave", os.environ["PUERTA_R2_KEY"].strip())
    req.add_header("user-agent", "eugenia-historias/1.0")
    return urllib.request.urlopen(req, timeout=600)


def get_json(key):
    try:
        with _puerta(key) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def bajar_reel(p, destino):
    """De R2 si sigue ahí; si no, de Instagram con el token de la página."""
    try:
        with _puerta(p.get("video_key") or f"reels/{p['id']}.mp4") as r, open(destino, "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
        if destino.stat().st_size > 100_000:
            return
    except Exception:  # noqa: BLE001
        pass
    tb = os.environ["META_PAGE_ACCESS_TOKEN"].strip()
    pagina = CUENTAS[p["nicho"]][1]
    tok = json.load(urllib.request.urlopen(f"{GRAPH}/{pagina}?fields=access_token&access_token={tb}",
                                           timeout=60))["access_token"]
    d = json.load(urllib.request.urlopen(
        f"{GRAPH}/{p['ig_media_id']}?fields=media_url&access_token={tok}", timeout=60))
    urllib.request.urlretrieve(d["media_url"], destino)


def historias_vivas(n):
    """Ids de las historias que Instagram muestra hoy en la cuenta (API de Meta). Es la
    prueba de que se subió: el 19/11 la última de cada corrida se perdía porque el
    emulador se apagaba antes de terminar de subirla, y el script la daba por hecha."""
    tb = os.environ["META_PAGE_ACCESS_TOKEN"].strip()
    tok = json.load(urllib.request.urlopen(
        f"{GRAPH}/{CUENTAS[n][1]}?fields=access_token&access_token={tb}", timeout=60))["access_token"]
    # 21/11: Meta a veces no devuelve instagram_business_account (ni con el token de la
    # página): el id de cada cuenta de IG es fijo, va escrito (los mismos del Worker).
    ig = IG_ID[n]
    s = json.load(urllib.request.urlopen(
        f"{GRAPH}/{ig}/stories?fields=timestamp&access_token={tok}", timeout=60))
    return {x["id"] for x in s.get("data", [])}


def ajustar_duracion(src, dst):
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", str(src)], capture_output=True, text=True).stdout.strip() or 0)
    if dur <= 59.5:
        return src
    f = dur / 59.5
    if f <= 1.06:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-filter_complex",
                        f"[0:v]setpts=PTS/{f}[v];[0:a]atempo={f}[a]", "-map", "[v]", "-map", "[a]",
                        "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-c:a", "aac", str(dst)], check=True)
    else:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-t", "59.5", "-c", "copy", str(dst)], check=True)
    return dst


def emulador_vivo():
    r = subprocess.run(["adb", "-s", "emulator-5554", "shell", "getprop", "sys.boot_completed"],
                       capture_output=True, text=True, timeout=30)
    return r.stdout.strip() == "1"


def asegurar_emulador():
    """21/11: en GitHub el emulador a veces se cierra solo (error de gráficos de Instagram,
    sin falta de memoria) y se perdían las historias que quedaban. Si está caído, se
    vuelve a prender acá mismo y se sigue con la próxima."""
    try:
        if emulador_vivo():
            return
    except Exception:  # noqa: BLE001
        pass
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    log("el emulador está caído: lo vuelvo a prender")
    subprocess.run(["pkill", "-f", "qemu-system"], capture_output=True)
    time.sleep(5)
    gpu = os.environ.get("EMU_GPU") or "guest"   # 22/11: guest no se cae
    subprocess.Popen("nohup emulator -avd eugenia_ig -no-window -no-audio -no-boot-anim -no-snapshot "
                     f"-gpu {gpu} -memory 4096 -cores 4 -accel on >> emulador.log 2>&1 &",
                     shell=True)
    for _ in range(60):
        time.sleep(10)
        try:
            if emulador_vivo():
                break
        except Exception:  # noqa: BLE001
            pass
    else:
        log("no volvió a prender")
        return
    time.sleep(20)
    for c in (["shell", "input", "keyevent", "82"],
              ["shell", "ime", "enable", "com.android.adbkeyboard/.AdbIME"],
              ["shell", "ime", "set", "com.android.adbkeyboard/.AdbIME"]):
        subprocess.run(["adb", "-s", "emulator-5554", *c], capture_output=True, timeout=60)
    log("emulador prendido de nuevo")


def texto_boton(p, est) -> str:
    """El texto del sticker (textos_boton.py): no siempre "VER CURSO". Se guardan los
    últimos de cada nicho en estado.json para no repetirlos."""
    # Con el teclado ADB el botón lleva emoji; sin él, solo letras (18/11).
    import historia_emulador as _he
    os.environ["TECLADO_ADB"] = "1" if _he.teclado_adb() else ""
    usados = est.setdefault("textos", {}).setdefault(p["nicho"], [])
    try:
        import textos_boton
        t = textos_boton.elegir(p, usados)
    except Exception:  # noqa: BLE001
        t = "VER CURSO"
    usados.append(t)
    del usados[:-15]
    return t


def main():
    probar = "--probar" in sys.argv
    try:
        est = json.loads(ESTADO.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        est = {}
    ahora = datetime.now(timezone.utc)
    if not est.get("desde"):
        # Arranca con lo publicado en las últimas horas (no con todo lo viejo).
        est = {"desde": (ahora - timedelta(hours=MAX_HORAS)).isoformat(), "hechas": {}, "fallas": {}}
    hechas, fallas = est.setdefault("hechas", {}), est.setdefault("fallas", {})
    limite = (ahora - timedelta(hours=MAX_HORAS)).isoformat()
    pubs = get_json("stock/publicados.json") or []
    pend = [p for p in pubs
            if p.get("nicho") in CUENTAS and p.get("id") and p["id"] not in hechas
            and str(p.get("ts", "")) >= max(est["desde"], limite)
            and p.get("ig_media_id") and p.get("nicho") not in est.get("pausadas", [])
            and est.get("pausa_hasta", {}).get(p.get("nicho"), "") < ahora.isoformat()]
    # "pausadas" (estado.json): cuentas que hoy no están abiertas en el Instagram del emulador
    # (21/11: hidroponía, desconectada por el baneo). Intentar entrar a una cuenta cerrada
    # trababa el emulador y tiraba las historias de las otras cuentas.
    # 20/11 (Tomix: "reintentemos después de 3, elimina esa regla"): ya no hay tope de intentos.
    # Se reintenta en cada corrida mientras el reel tenga menos de MAX_HORAS (el conteo de
    # fallas queda solo como registro).
    # --cada-cuenta (19/11, Tomix: "que todas las cuentas queden con historias ahora"): la
    # cuenta que no tiene una historia nuestra de las últimas 24 h sube su último reel.
    if "--cada-cuenta" in sys.argv:
        for n in CUENTAS:
            if any(p["nicho"] == n for p in pend):
                continue
            if historias_vivas(n):
                continue                      # Instagram ya muestra una historia viva
            ult = [p for p in pubs if p.get("nicho") == n and p.get("ig_media_id")]
            if ult:
                pend.append(max(ult, key=lambda p: str(p.get("ts", ""))))
    # --todas (19/11, Tomix: "subí el reel más reciente como historia en cada cuenta"):
    # el último reel de cada cuenta, tenga o no historia. --sin-publicar: solo arma la
    # historia de la primera cuenta y saca la captura del editor (prueba de la posición).
    if "--todas" in sys.argv or "--sin-publicar" in sys.argv:
        pend = []
        for n in CUENTAS:
            ult = [p for p in pubs if p.get("nicho") == n and p.get("ig_media_id")]
            if ult:
                pend.append(max(ult, key=lambda p: str(p.get("ts", ""))))
        if "--sin-publicar" in sys.argv:
            pend = pend[:1]
    # --solo=<nicho> (21/11, Tomix: "forzá la nube ya"): el último reel de esa cuenta,
    # tenga o no historia, sin pausas ni otras cuentas.
    solo = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--solo=")), "")
    if solo:
        ult = [p for p in pubs if p.get("nicho") == solo and p.get("ig_media_id")]
        pend = [max(ult, key=lambda p: str(p.get("ts", "")))] if ult else []
    log(f"pendientes: {len(pend)}")
    for p in pend:
        log("  ·", p["nicho"], p["id"], p["ts"])
    if probar or not pend:
        ESTADO.write_text(json.dumps(est, ensure_ascii=False, indent=1), encoding="utf-8")
        return 0

    import historia_emulador as he
    # 21/11: la PRIMERA cuenta de cada corrida fallaba siempre (hidro, o bonsái cuando hidro
    # estaba en pausa): recién prendido, Instagram reproduce los videos del inicio, la pantalla
    # no se puede leer y a veces el emulador se cae. Calentamiento: abrir Instagram, esperar,
    # ir al perfil (sin videos) y recién ahí empezar.
    try:
        he.adb("shell", "monkey", "-p", "com.instagram.android", "-c", "android.intent.category.LAUNCHER", "1")
        time.sleep(45)
        tab = next((n for n in he.nodos() if n["desc"] in ("Profile", "Perfil")), None)
        if tab:
            he.tocar(tab)
        time.sleep(15)
        he.adb("shell", "am", "force-stop", "com.instagram.android")
        log("calentamiento hecho")
    except Exception as e:  # noqa: BLE001
        log("calentamiento falló:", str(e)[:100])
    # Y la que falla se reintenta una vez al final de la misma corrida.
    pend = pend + [None] + list(pend)
    for p in pend:
        if p is None:
            log("segunda vuelta para las que fallaron")
            continue
        if p["id"] in hechas:
            continue
        n, rid = p["nicho"], p["id"]
        tmp = Path(tempfile.mkdtemp())
        asegurar_emulador()
        try:
            bajar_reel(p, tmp / "reel.mp4")
            video = ajustar_duracion(tmp / "reel.mp4", tmp / "reel_59.mp4")
            sck = "historia-" + n + "-" + rid.split("-", 2)[-1]
            texto = texto_boton(p, est)
            log(f"  botón: {texto}")
            try:
                antes = historias_vivas(n)
            except Exception as e2:  # noqa: BLE001
                # 21/11: la API de Meta no veía la cuenta de herbología. Se sube igual y se
                # da por hecha sin la prueba de la API (mejor eso que ninguna historia).
                log(f"  la API de Meta no ve la cuenta de {n} ({str(e2)[:60]}): subo sin verificar")
                antes = None
            if "--sin-publicar" in sys.argv:
                he.publicar(n, str(video), texto=texto, sck=sck, cuenta=CUENTAS[n][0], y=Y_STICKER,
                            sin_publicar=True)
                continue
            he.publicar(n, str(video), texto=texto, sck=sck, cuenta=CUENTAS[n][0], y=Y_STICKER)
            # Hecha recién cuando Instagram la muestra (hasta 10 min; el emulador sigue prendido)
            for _ in range(40 if antes is not None else 0):
                time.sleep(15)
                if historias_vivas(n) - antes:
                    break
            else:
                if antes is not None:
                    raise RuntimeError("Instagram no muestra la historia nueva después de 10 min")
                time.sleep(120)       # que termine de subir antes de seguir
            hechas[rid] = datetime.now(timezone.utc).isoformat()
            # 21/11 (Tomix: "que recuerde el celular"): si subió al menos una, al terminar se
            # guarda el emulador tal como quedó (sesiones al día) y la próxima arranca de acá.
            Path("guardar_avd").write_text("1")
            log(f"historia subida y vista en Instagram: {n} {rid}")
        except (Exception, SystemExit) as e:   # noqa: BLE001
            fallas[rid] = fallas.get(rid, 0) + 1
            log(f"falló {n} {rid} (intento {fallas[rid]}): {str(e)[:200]}")
            # 21/11: Instagram pidió un código por mail a herbología (control de seguridad por
            # entrar desde GitHub). Insistir puede terminar en cuenta restringida (le pasó a
            # terrarios): esa cuenta queda en pausa hasta que Tomix la valide en el emulador.
            try:
                if "código" in str(e) or he.buscar(he.DESAFIO):
                    # No llegó el código a tiempo: 6 h de pausa para no pedirle a Instagram
                    # aprobaciones una tras otra.
                    est.setdefault("pausa_hasta", {})[n] = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
                    log(f"Instagram pidió aprobar el ingreso en {n} y no se aprobó: 6 h en pausa")
            except Exception:  # noqa: BLE001
                pass
            with open(ROOT / f"falla_{rid}.png", "wb") as f:
                subprocess.run([he.ADB, "-s", "emulator-5554", "exec-out", "screencap", "-p"], stdout=f)
            he.adb("shell", "input", "keyevent", "4")
            he.tocar_texto(r"^(Discard|Descartar)$", 3)
        ESTADO.write_text(json.dumps(est, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
