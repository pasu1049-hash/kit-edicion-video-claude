"""PLANTILLA 1% — edición de video para feed (1080x1350) o historia ("formato": "historia", 1080x1920).
Entrada LED + video con subtítulos de marca + cierre LED con textos + portada.

Uso:
  1) python editar_video.py transcribir <config.json>   -> genera words.json (revisar/corregir a mano)
  2) python editar_video.py render <config.json>        -> video final + portada
  3) python editar_video.py preview <config.json> <seg> -> un cuadro suelto (segundos del video final)

El config.json define: video, recorte, textos de cierre, palabras clave, cuadro de portada.
"""
import sys, os, json, re, subprocess, pathlib, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg

ROOT = pathlib.Path(__file__).resolve().parent
OUT = pathlib.Path.cwd()                              # salidas: carpeta desde donde se corre
WORK = OUT / "work"
WORK.mkdir(exist_ok=True)
FONTS = ROOT / "fonts"
LOGO_LED = None   # foto del logo en cartel de neon (config "logo_led"); sin esto se usa "placa"
FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H, FPS, SR = 1080, 1350, 30, 48000
DY = 0  # corrimiento vertical de cartel/cierre (historia 9:16 = 285)
CORAL = (255, 104, 74)
INTRO, OUTRO = 2.2, 5.0


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


# =====================================================================
# Cartel LED (misma técnica que el teaser)
# =====================================================================
class Sign:
    def __init__(self, scale, cy):
        src = Image.open(LOGO_LED).convert("RGB")
        src = src.resize((round(src.width * scale), round(src.height * scale)), Image.LANCZOS)
        cv = Image.new("RGB", (W, H))
        cv.paste(src, (W // 2 - round(675 * scale), cy - round(590 * scale)))
        self.cy = cy
        on = np.asarray(cv).astype(np.float32) / 255
        hsv = np.asarray(cv.convert("HSV")).astype(np.float32) / 255
        hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]

        def thin(m, size=27):
            pm = Image.fromarray((m * 255).astype(np.uint8))
            op = pm.filter(ImageFilter.MinFilter(size)).filter(ImageFilter.MaxFilter(size))
            return np.clip(m - np.asarray(op).astype(np.float32) / 255, 0, 1)

        def soft(m, r):
            return np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))).astype(np.float32) / 255

        white = thin(((sat < 0.28) & (val > 0.86)).astype(np.float32))
        orange = thin(((sat >= 0.28) & (sat < 0.85) & (hue > 21 / 255) & (val > 0.9)).astype(np.float32))
        self.wo = np.clip(soft(orange, 2) * 1.6, 0, 1)[..., None]
        self.ww = np.clip(soft(white, 2) * 1.6, 0, 1)[..., None]
        self.wh = np.clip(soft(np.maximum(white, orange), 50) * 5.0, 0, 1)[..., None]
        off = on * 0.05
        tube = np.clip(self.wo + self.ww, 0, 1)
        self.off = off * (1 - tube) + tube * np.array([0.16, 0.15, 0.14], np.float32)
        self.on = on
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        self.vig = (1 - 0.6 * np.clip(((xx - W / 2) / (W * 0.72)) ** 2 + ((yy - cy) / (H * 0.62)) ** 2, 0, 1))[..., None]

    def render(self, ko, kw, t=0.0, floor_y=None):
        kh = 0.65 * ko + 0.35 * kw
        hum = 1 + 0.025 * np.sin(t * 2 * np.pi * 7.3)
        mix = np.clip(self.wo * ko + self.ww * kw + self.wh * kh * (1 - self.wo - self.ww).clip(0, 1), 0, 1) * hum
        f = (self.off + (self.on - self.off) * mix) * self.vig
        if floor_y is not None:
            yy = np.arange(H, dtype=np.float32)[:, None, None]
            f = f * np.clip(1 - (yy - floor_y) / 200, 0, 1)
        return f


def steps(t, events, default=0.0):
    k = default
    for a, b, lv in events:
        if a <= t < b:
            k = lv
    return k


# encendido de la entrada (dura INTRO segundos)
IN_O = [(0.20, 0.26, 1), (0.26, 0.40, 0), (0.40, 0.44, .8), (0.44, 0.80, 0), (0.80, 0.92, 1),
        (0.92, 1.00, .2), (1.00, 1.06, 1), (1.06, 1.14, .1), (1.14, 99, 1)]
IN_W = [(0.82, 0.88, .7), (0.88, 1.40, 0), (1.40, 1.46, 1), (1.46, 1.56, 0), (1.56, 99, 1)]


# =====================================================================
# Subtítulos
# =====================================================================
def norm(w):
    return re.sub(r"[^\wáéíóúñü%]", "", w.lower())


def group_words(words, max_words=4, max_chars=20, gap=0.35):
    groups, cur = [], []
    for i, w in enumerate(words):
        if cur:
            chars = sum(len(x["w"]) + 1 for x in cur) + len(w["w"])
            brk = (len(cur) >= max_words or chars > max_chars or w["s"] - cur[-1]["e"] > gap
                   or re.search(r"[.,;:!?…]$", cur[-1]["w"]))
            if brk:
                groups.append(cur); cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    out = []
    for g in groups:
        out.append({"words": g, "s": g[0]["s"], "e": g[-1]["e"]})
    # cada grupo queda en pantalla hasta que empieza el siguiente (máx +0.5 s)
    for a, b in zip(out, out[1:]):
        a["e"] = min(b["s"], a["e"] + 0.5)
    if out:
        out[-1]["e"] += 0.4
    return out


class Captions:
    def __init__(self, words, keywords, y_center, size=70):
        self.groups = group_words(words)
        self.kw = {norm(k) for k in keywords}
        self.f = font("Poppins-ExtraBold.ttf", size)
        self.size = size
        self.y = y_center
        self.cache = {}

    def _layout(self, g):
        d = ImageDraw.Draw(Image.new("L", (1, 1)))
        toks = [re.sub(r"[.,;:…]+$", "", w["w"].upper().strip()) for w in g["words"]]
        sp = d.textlength(" ", font=self.f)
        widths = [d.textlength(t, font=self.f) for t in toks]
        # 1 o 2 líneas
        lines = [list(range(len(toks)))]
        if sum(widths) + sp * (len(toks) - 1) > 940 and len(toks) > 1:
            best, cut = 1e9, 1
            for c in range(1, len(toks)):
                a = sum(widths[:c]) + sp * (c - 1); b = sum(widths[c:]) + sp * (len(toks) - c - 1)
                if max(a, b) < best:
                    best, cut = max(a, b), c
            lines = [list(range(cut)), list(range(cut, len(toks)))]
        pos = {}
        lh = self.size * 1.12
        y0 = self.y - lh * len(lines) / 2
        for li, idxs in enumerate(lines):
            lw = sum(widths[i] for i in idxs) + sp * (len(idxs) - 1)
            x = (W - lw) / 2
            for i in idxs:
                pos[i] = (x, y0 + li * lh)
                x += widths[i] + sp
        return toks, pos

    def draw(self, img, t):
        """img: PIL RGB. t: segundos dentro del clip principal."""
        g = next((g for g in self.groups if g["s"] - 0.05 <= t < g["e"]), None)
        if g is None:
            return img
        key = id(g)
        if key not in self.cache:
            self.cache[key] = self._layout(g)
        toks, pos = self.cache[key]
        pop = ease((t - g["s"] + 0.05) / 0.12)
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d, ds = ImageDraw.Draw(lay), ImageDraw.Draw(sh)
        for i, tok in enumerate(toks):
            w = g["words"][i]
            said = t >= w["s"] - 0.03
            is_kw = norm(w["w"]) in self.kw
            if said:
                col = CORAL + (255,) if is_kw else (255, 255, 255, 255)
            else:
                col = (255, 255, 255, 165)
            x, y = pos[i]
            y += (1 - pop) * 14
            ds.text((x, y + 6), tok, font=self.f, fill=(0, 0, 0, 255), stroke_width=8, stroke_fill=(0, 0, 0, 255))
            d.text((x, y), tok, font=self.f, fill=col, stroke_width=5, stroke_fill=(0, 0, 0, 255))
        sh = sh.filter(ImageFilter.GaussianBlur(10))
        a = pop
        base = img.convert("RGBA")
        if a < 1:
            sh.putalpha(sh.getchannel("A").point(lambda v: int(v * a)))
            lay.putalpha(lay.getchannel("A").point(lambda v: int(v * a)))
        base.alpha_composite(sh)
        base.alpha_composite(lay)
        return base.convert("RGB")


# =====================================================================
# Cierre
# =====================================================================
def text_rgba(lines, fnt, size, color, y, sp=0, lh=1.05, glow=0.45, highlight=None):
    """highlight: {caracter: color} para pintar p. ej. el % en coral."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for n, txt in enumerate(lines):
        tw = d.textlength(txt, font=fnt) + sp * (len(txt) - 1)
        x = (W - tw) / 2
        for ch in txt:
            c = (highlight or {}).get(ch, color)
            d.text((x, y + n * size * lh), ch, font=fnt, fill=c)
            x += d.textlength(ch, font=fnt) + sp
    g = lay.filter(ImageFilter.GaussianBlur(14))
    return np.asarray(lay).astype(np.float32) / 255, np.asarray(g).astype(np.float32) / 255 * glow


def over(f, layer, a):
    if a <= 0:
        return f
    rgba, glow = layer
    f = f + glow[..., :3] * glow[..., 3:] * a
    al = rgba[..., 3:] * a
    return f * (1 - al) + rgba[..., :3] * al


class Outro:
    def __init__(self, cfg):
        o = cfg["cierre"]
        self.sign = Sign(1.1, 395 + DY)
        white = (255, 255, 255, 255)
        y = 790 + DY
        big = font("Poppins-Black.ttf", 76)
        self.layers = []
        l1 = text_rgba(o["titulo"], big, 76, white, y, sp=-1)
        y += 76 * 1.05 * len(o["titulo"]) + 4
        by = text_rgba([o["by"]], font("Poppins-Black.ttf", 96), 96, white, y, sp=-2, highlight={"%": CORAL + (255,)})
        y += 96 + 40
        # bloque coral de la fecha
        fd = font("Poppins-ExtraBold.ttf", 50)
        d = ImageDraw.Draw(Image.new("L", (1, 1)))
        tw = d.textlength(o["fecha"], font=fd)
        box = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        bd = ImageDraw.Draw(box)
        bx0, by0 = (W - tw) / 2 - 28, y - 6
        bd.rectangle((bx0, by0, bx0 + tw + 56, by0 + 50 * 1.45), fill=CORAL + (255,))
        bd.text(((W - tw) / 2, y), o["fecha"], font=fd, fill=(255, 255, 255, 255))
        fecha = (np.asarray(box).astype(np.float32) / 255, np.zeros((H, W, 4), np.float32))
        y += 50 * 1.45 + 30
        plat = text_rgba([o["plataformas"]], font("Poppins-SemiBold.ttf", 28), 28, (255, 255, 255, 220), y, sp=3, glow=0)
        y += 28 + 24
        handle = text_rgba([o["handle"]], font("Poppins-SemiBold.ttf", 26), 26, (255, 255, 255, 140), y, sp=2, glow=0)
        self.layers = [(l1, 0.35), (by, 0.9), (fecha, 1.45), (plat, 1.95), (handle, 2.25)]

    def frame(self, t, last_clip):
        # 0-0.45: el último cuadro del video se oscurece mientras se prende el cartel
        ko = steps(t, [(0.25, 0.31, 1), (0.31, 0.42, 0), (0.42, 99, 1), (4.05, 4.11, 0.25)], 0)
        ko = 0.25 if 4.05 <= t < 4.11 else ko
        kw = steps(t, [(0.30, 0.36, 1), (0.36, 0.48, 0), (0.48, 99, 1)], 0)
        kw = 0.3 if 4.07 <= t < 4.13 else kw
        f = self.sign.render(ko, kw, t, floor_y=760 + DY)
        a = 1 - ease(t / 0.45)
        if a > 0:
            f = f * (1 - a) + last_clip * a * (0.4 + 0.6 * a)
        for layer, t0 in self.layers:
            f = over(f, layer, ease((t - t0) / 0.45))
        f = f * (1 - ease((t - (OUTRO - 0.6)) / 0.6))
        return f


# =====================================================================
# Audio
# =====================================================================
def neon_sfx(dur, k_fn, hits=()):
    t = np.arange(int(SR * dur)) / SR
    step = SR // 100
    k = np.array([k_fn(x) for x in t[::step]]).repeat(step)[: len(t)]
    k = np.pad(k, (0, len(t) - len(k)), mode="edge")
    hum = sum(np.sin(2 * np.pi * 100 * h * t) / h for h in (1, 2, 3, 5)) * 0.08
    sig = (hum + np.sign(np.sin(2 * np.pi * 100 * t)) * 0.018) * k
    idx = np.where(np.abs(np.diff(k, prepend=0)) > 0.3)[0]
    noise = np.random.default_rng(2).normal(0, 1, len(t))
    for j in idx:
        n = min(int(SR * 0.03), len(t) - j)
        sig[j:j + n] += noise[j:j + n] * np.exp(-np.arange(n) / (SR * 0.006)) * 0.45
    for h0 in hits:
        j = int(h0 * SR); n = min(int(SR * 0.9), len(t) - j)
        tt = np.arange(n) / SR
        sig[j:j + n] += np.sin(2 * np.pi * (55 - 20 * tt) * tt) * np.exp(-tt * 4) * 0.5
    return sig


def load_voice(cfg, start, dur):
    tmp = WORK / f"_voice_{pathlib.Path(cfg['salida']).stem}.wav"
    subprocess.run([FF, "-y", "-loglevel", "error", "-ss", str(start), "-t", str(dur), "-i", cfg["video"],
                    "-vn", "-af", "highpass=f=70,loudnorm=I=-14:TP=-1.5:LRA=9", "-ac", "1", "-ar", str(SR), str(tmp)],
                   check=True)
    with wave.open(str(tmp)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    n = int(dur * SR)
    return np.pad(a, (0, max(0, n - len(a))))[:n]



# =====================================================================
# Zoom: empuje lento + salto de encuadre en cada corte + punch-in por palabra
# =====================================================================
class Zoomer:
    """cfg["zoom"] = {"push": 0.05, "cortes": 0.09, "cara": [540, 700],
                      "punch": [{"palabra": "x", "n": 1, "hasta": "y", "z": 1.18}]}"""
    def __init__(self, cfg, segs, words, main_d):
        z = cfg.get("zoom")
        self.on = bool(z)
        if not self.on:
            return
        self.push, self.cut = z.get("push", 0.05), z.get("cortes", 0.09)
        self.cx, self.cy = z.get("cara", [W / 2, H * 0.4])
        self.main_d = main_d
        self.bounds, acc = [], 0.0
        for a, b in segs:
            acc += b - a; self.bounds.append(acc)
        self.punches = []
        for pch in z.get("punch", []):
            t0 = self._find(words, pch["palabra"], pch.get("n", 1), "s")
            t1 = self._find(words, pch["hasta"], pch.get("n_hasta", 1), "e") if "hasta" in pch else t0 + pch.get("dur", 0.9)
            self.punches.append((t0 - 0.04, t1 + pch.get("extra", 0.25), pch.get("z", 1.18)))

    @staticmethod
    def _find(words, w, n, key):
        k = 0
        for x in words:
            if norm(x["w"]) == norm(w):
                k += 1
                if k == n:
                    return x[key]
        raise ValueError(f"zoom: palabra no encontrada: {w} #{n}")

    def factor(self, t):
        z = 1 + self.push * t / max(self.main_d, 1e-6)
        seg = next((i for i, b in enumerate(self.bounds) if t < b), len(self.bounds) - 1)
        if seg % 2 == 1:
            z *= 1 + self.cut
        for t0, t1, zp in self.punches:
            p = ease((t - t0) / 0.12) * (1 - ease((t - t1) / 0.25))
            if p > 0:
                z *= 1 + (zp - 1) * p
        return z

    def apply(self, img, t):
        if not self.on:
            return img
        z = self.factor(t)
        if z < 1.002:
            return img
        w, h = W / z, H / z
        x0 = min(max(self.cx - w / 2, 0), W - w)
        y0 = min(max(self.cy - h / 2, 0), H - h)
        return img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + w, y0 + h))


# =====================================================================
# Música de fondo + efectos (musica.py)
# =====================================================================
def add_music(cfg, audio, voice, mg, main_d):
    mc = cfg.get("musica")
    if not mc:
        return audio
    import musica as M
    rng = np.random.default_rng(11)
    n_in = 0 if cfg.get("placa") else int(INTRO * SR)
    total = len(audio) / SR
    bed = M.beat(total + 0.5, bpm=mc.get("bpm", 92), seed=mc.get("seed", 3),
                 energia=mc.get("energia", 1.0))[: len(audio) - n_in]
    duck = M.ducking(voice, amount=mc.get("ducking", 0.72))
    g = np.ones(len(bed))
    off = int(INTRO * SR) - n_in
    g[off: off + len(duck)] = duck
    tt = np.arange(len(bed)) / SR
    g *= np.clip(tt / 0.05, 0, 1)
    # en el cierre la música sube y después se apaga con el cartel
    out_t = tt - main_d - off / SR
    g = np.where(out_t > 0, np.minimum(1.0, g + out_t / 0.6), g)
    g *= 1 - np.clip((tt - (total - n_in / SR - 0.8)) / 0.8, 0, 1)
    mus = np.zeros(len(audio))
    mus[n_in:n_in + len(bed)] = bed * g * mc.get("vol", 0.22)
    sfx = np.zeros(len(audio))
    M._add(sfx, INTRO - 1.2, M.riser(1.2, rng), 0.10)
    M._add(sfx, INTRO, M.golpe(rng), 0.35)
    if mg:
        for it in mg.items:
            a = it["e"].get("anim", "pop")
            at = INTRO + it["t0"]
            if a == "slam":
                M._add(sfx, at, M.golpe(rng), 0.30)
            elif a == "slide":
                M._add(sfx, at - 0.15, M.whoosh(rng, 0.4), 0.10)
            else:
                M._add(sfx, at, M.pop(rng), 0.12)
    M._add(sfx, INTRO + main_d - 0.3, M.whoosh(rng, 0.5), 0.14)
    return audio + mus + sfx * mc.get("sfx", 1.0)

# =====================================================================
# Render
# =====================================================================
def clip_reader(cfg, start, dur):
    c = cfg["recorte"]
    if cfg.get("mejora"):  # videos chicos o comprimidos (WhatsApp/Drive): limpiar, escalar y afilar
        vf = (f"crop={c['w']}:{c['h']}:{c['x']}:{c['y']},hqdn3d=2.2:1.8:5:5,"
              f"scale={W}:{H}:flags=lanczos+accurate_rnd+full_chroma_int,fps={FPS},"
              f"unsharp=5:5:0.9:3:3:0.3,eq=contrast=1.07:saturation=1.1:gamma=0.97")
    else:
        vf = (f"crop={c['w']}:{c['h']}:{c['x']}:{c['y']},scale={W}:{H}:flags=lanczos,fps={FPS},"
              f"eq=contrast=1.04:saturation=1.06:gamma=0.98")
    filt = ["-vf", vf]
    if cfg.get("layout") == "podcast":  # video horizontal adentro de 9:16, con fondo difuminado
        pc = cfg.get("podcast", {})
        cx, cy, cw, ch = pc.get("crop", [0, 32, 1280, 664])
        fy = pc.get("y", 600)
        fc = (f"[0:v]crop={cw}:{ch}:{cx}:{cy},split[a][b];"
              f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=28:2,"
              f"eq=brightness=-0.22:saturation=0.85[bg];"
              f"[b]scale={W}:-2:flags=lanczos,unsharp=5:5:0.6:3:3:0.2,eq=contrast=1.06:saturation=1.1:gamma=0.97[fg];"
              f"[bg][fg]overlay=0:{fy},fps={FPS}")
        filt = ["-filter_complex", fc]
    p = subprocess.Popen([FF, "-loglevel", "error", "-ss", str(start), "-t", str(dur), "-i", cfg["video"],
                          *filt, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    size = W * H * 3
    try:
        while True:
            b = p.stdout.read(size)
            if len(b) < size:
                break
            yield np.frombuffer(b, np.uint8).reshape(H, W, 3)
    finally:
        p.kill(); p.stdout.close(); p.wait()


def timeline(cfg):
    """Devuelve palabras, inicio, fin y los tramos que se conservan (en segundos del video original).
    cfg["cortes"] = [[desde, hasta], ...] pausas a eliminar."""
    words = json.load(open(cfg["words"], encoding="utf-8"))
    start = max(0.0, words[0]["s"] - cfg.get("pre", 0.15))
    end = words[-1]["e"] + cfg.get("post", 0.45)
    segs, cur = [], start
    for a, b in sorted(cfg.get("cortes", [])):
        if a > cur:
            segs.append((cur, a))
        cur = max(cur, b)
    segs.append((cur, end))
    return words, start, end, segs


def src_to_out(t, segs):
    """Segundo del original -> segundo del clip editado (None si cae en un corte)."""
    acc = 0.0
    for a, b in segs:
        if a <= t <= b:
            return acc + t - a
        acc += b - a
    return None


def out_to_src(t, segs):
    acc = 0.0
    for a, b in segs:
        if t < acc + (b - a):
            return a + t - acc
        acc += b - a
    return segs[-1][1]


def seg_frames(segs):
    """Cantidad de cuadros por tramo, sin acumular error de redondeo."""
    out, acc = [], 0.0
    for a, b in segs:
        n = round((acc + b - a) * FPS) - round(acc * FPS)
        out.append(n); acc += b - a
    return out


def render(cfg, only_t=None):
    words, start, end, segs = timeline(cfg)
    rel = []
    for w in words:
        s0, e0 = src_to_out(w["s"], segs), src_to_out(w["e"], segs)
        if s0 is None and e0 is None:
            continue
        rel.append(dict(w, s=s0 if s0 is not None else e0, e=e0 if e0 is not None else s0))
    caps = Captions(rel, cfg.get("claves", []), cfg.get("subs_y", 1060))
    mg = None
    if cfg.get("motion"):
        import motion
        motion.FONTS = FONTS
        motion.CORAL = CORAL + (255,) if len(CORAL) == 3 else CORAL
        mg = motion.Motion(cfg["motion"], rel)
    main_d = sum(b - a for a, b in segs)
    zs = Zoomer(cfg, segs, rel, main_d)
    placa = None
    if cfg.get("placa"):
        import showreel
        placa = showreel.Placa(cfg["placa"], W, H)
    else:
        sign_in = Sign(1.25, 610 + DY)
        outro = Outro(cfg)
    total = INTRO + main_d + OUTRO
    nfr = int(total * FPS)
    rng = np.random.default_rng(7)
    out = OUT / cfg["salida"]

    def grain(f):
        return f + rng.normal(0, 0.012, (H, W, 1)).astype(np.float32)

    if only_t is not None:
        t = only_t
        if t < INTRO:
            f = placa.frame(t) if placa else sign_in.render(steps(t, IN_O), steps(t, IN_W), t)
        elif t < INTRO + main_d:
            fr = next(clip_reader(cfg, out_to_src(t - INTRO, segs), 0.2))
            im0 = zs.apply(Image.fromarray(fr), t - INTRO)
            if mg: im0 = mg.draw(im0, t - INTRO)
            f = np.asarray(caps.draw(im0, t - INTRO)).astype(np.float32) / 255
        else:
            fr = next(clip_reader(cfg, end - 0.1, 0.2)).astype(np.float32) / 255
            f = placa.frame(t - INTRO - main_d, under=fr) if placa else outro.frame(t - INTRO - main_d, fr)
        Image.fromarray((np.clip(f, 0, 1) * 255).astype(np.uint8)).save(WORK / f"_prev_{t}.jpg")
        return

    # ---- audio ----
    if INTRO <= 0:
        a_in = np.zeros(0)
    elif placa:
        import musica as _M
        _r = np.random.default_rng(4)
        a_in = np.zeros(int(INTRO * SR))
        _M._add(a_in, 0.0, _M.golpe(_r), 0.35)
        for _, t0, _ in placa.layers:
            _M._add(a_in, t0, _M.pop(_r), 0.12)
    else:
        a_in = neon_sfx(INTRO, lambda x: 0.7 * steps(x, IN_O) + 0.3 * steps(x, IN_W))
    a_in *= 1 - np.clip((np.arange(len(a_in)) / SR - (INTRO - 0.25)) / 0.25, 0, 1) * 0.7
    full = load_voice(cfg, start, end - start)
    parts, fade = [], int(SR * 0.012)
    for a, b in segs:
        p = full[int((a - start) * SR):int((b - start) * SR)].copy()
        if len(p) > 2 * fade:
            p[:fade] *= np.linspace(0, 1, fade); p[-fade:] *= np.linspace(1, 0, fade)
        parts.append(p)
    voice = np.concatenate(parts)
    voice = np.pad(voice, (0, max(0, int(round(main_d * FPS)) * SR // FPS - len(voice))))
    kf = lambda x: 0.7 * (1 if x >= 0.42 else 0) + 0.3 * (1 if x >= 0.48 else 0)
    if placa:
        a_out = np.zeros(int(OUTRO * SR))
        for _, t0, _ in placa.layers:
            _M._add(a_out, t0, _M.pop(_r), 0.12)
        _M._add(a_out, 0.0, _M.whoosh(_r, 0.4), 0.18)
    else:
        a_out = neon_sfx(OUTRO, kf, hits=(0.35,)) * 0.9
    a_out *= 1 - np.clip((np.arange(len(a_out)) / SR - (OUTRO - 0.6)) / 0.6, 0, 1)
    audio = np.concatenate([a_in, voice, a_out])
    audio = add_music(cfg, audio, voice, mg, main_d)
    audio = np.clip(audio, -1, 1)
    wav = WORK / f"_mix_{out.stem}.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((audio * 32000).astype(np.int16).tobytes())

    enc = subprocess.Popen([FF, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "slow",
                            "-crf", "14", "-profile:v", "high", "-pix_fmt", "yuv420p", "-colorspace", "bt709",
                            "-color_primaries", "bt709", "-color_trc", "bt709", "-c:a", "aac", "-b:a", "320k",
                            "-ac", "2", "-shortest", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    n_in = int(INTRO * FPS)
    for i in range(n_in):
        t = i / FPS
        f = placa.frame(t) if placa else sign_in.render(steps(t, IN_O), steps(t, IN_W), t)
        f = f * (1 + 1.5 * ease((t - (INTRO - 0.1)) / 0.1))  # destello antes del corte
        enc.stdin.write((np.clip(grain(f), 0, 1) * 255).astype(np.uint8).tobytes())
    last = None
    n_main = int(round(main_d * FPS))

    def main_frames():
        for (a, b), n in zip(segs, seg_frames(segs)):
            k = 0
            for fr in clip_reader(cfg, a, b - a + 0.1):
                if k >= n:
                    break
                yield fr; k += 1
            for _ in range(k, n):
                yield fr

    for j, fr in enumerate(main_frames()):
        if j >= n_main:
            break
        t = j / FPS
        img = zs.apply(Image.fromarray(fr), t)
        if mg: img = mg.draw(img, t)
        img = caps.draw(img, t)
        arr = np.asarray(img)
        if j < 3:  # flash de corte
            arr = np.clip(arr.astype(np.float32) + (3 - j) * 60, 0, 255).astype(np.uint8)
        last = fr
        enc.stdin.write(arr.tobytes())
    for _ in range(j + 1, n_main):  # por si faltan cuadros
        enc.stdin.write(last.tobytes())
    lastf = last.astype(np.float32) / 255
    for i in range(int(OUTRO * FPS)):
        f = placa.frame(i / FPS, under=lastf, out_at=OUTRO - 0.5) if placa else outro.frame(i / FPS, lastf)
        enc.stdin.write((np.clip(grain(f), 0, 1) * 255).astype(np.uint8).tobytes())
    enc.stdin.close(); enc.wait()
    print("ok", out, f"{INTRO + main_d + OUTRO:.1f}s")


def portada(cfg):
    p = cfg["portada"]
    fr = next(clip_reader(cfg, p["segundo"], 0.2))
    img = Image.fromarray(fr).convert("RGBA")
    # degradado inferior
    g = np.zeros((H, W, 4), np.uint8)
    ys = np.arange(H)
    g[..., 3] = (np.clip((ys - 620) / 520, 0, 1) ** 1.3 * 245).astype(np.uint8)[:, None]
    img.alpha_composite(Image.fromarray(g))
    d = ImageDraw.Draw(img)
    # logo chico arriba
    if cfg.get("logo") and os.path.exists(cfg["logo"]):
        logo = Image.open(cfg["logo"]).convert("RGBA").resize((86, 86), Image.LANCZOS)
        mask = Image.new("L", (86, 86), 0); ImageDraw.Draw(mask).ellipse((0, 0, 85, 85), fill=255)
        img.paste(logo, (56, 56), mask)
    d.text((158, 80), cfg.get("marca", ""), font=font("Poppins-Bold.ttf", 28), fill=(255, 255, 255, 255))
    y = H - 60 - 70
    fk = font("Poppins-SemiBold.ttf", 26)
    kick = p.get("kicker", "")
    ft = font("Poppins-Black.ttf", p.get("size", 104))
    lines = p["titulo"]
    lh = p.get("size", 104) * 0.98
    ytitle = H - 250 - lh * len(lines)
    d.text((64, ytitle - 50), kick, font=fk, fill=CORAL + (255,), spacing=6)
    for n, ln in enumerate(lines):
        x = 60
        for ch in ln:
            col = CORAL + (255,) if ch == "%" else (255, 255, 255, 255)
            d.text((x, ytitle + n * lh), ch, font=ft, fill=col)
            x += d.textlength(ch, font=ft) - 2
    fb = font("Poppins-ExtraBold.ttf", 40)
    tw = d.textlength(p["fecha"], font=fb)
    yb = H - 200
    d.rectangle((60, yb, 60 + tw + 48, yb + 64), fill=CORAL + (255,))
    d.text((84, yb + 6), p["fecha"], font=fb, fill=(255, 255, 255, 255))
    d.text((64, H - 100), p["pie"], font=font("Poppins-SemiBold.ttf", 24), fill=(255, 255, 255, 170))
    out = OUT / cfg["salida"].replace(".mp4", "_PORTADA.png")
    img.convert("RGB").save(out)
    print("ok", out)


def transcribir(cfg):
    from faster_whisper import WhisperModel
    tmp = WORK / "_a16.wav"
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", cfg["video"], "-vn", "-ac", "1", "-ar", "16000", str(tmp)], check=True)
    m = WhisperModel("medium", device="cpu", compute_type="int8")
    segs, _ = m.transcribe(str(tmp), language="es", word_timestamps=True, vad_filter=False,
                           initial_prompt=cfg.get("vocabulario", "TikTok, YouTube, Instagram, reels."))
    words = []
    for s in segs:
        print(f"[{s.start:.2f}-{s.end:.2f}] {s.text}")
        words += [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)} for w in s.words]
    json.dump(words, open(cfg["words"], "w", encoding="utf-8"), ensure_ascii=False, indent=0)


if __name__ == "__main__":
    cmd, cfgp = sys.argv[1], sys.argv[2]
    cfg = json.load(open(cfgp, encoding="utf-8"))
    if cfg.get("formato") == "historia":  # 1080x1920 para historias / reels
        W, H, DY = 1080, 1920, 285
    if cfg.get("logo_led") and os.path.exists(cfg["logo_led"]):
        LOGO_LED = cfg["logo_led"]
    elif not cfg.get("placa") and cmd != "transcribir":
        # sin foto de cartel LED: entrada y cierre con placa del color de la marca
        ci = cfg.get("cierre", {})
        _m = cfg.get("marca", "MI MARCA")
        cfg["placa"] = {"marca": _m, "size": min(170, int(1300 / max(len(_m), 1))), "color": list(cfg.get("acento", [255, 104, 74])),
                        "kicker": ci.get("by", ""), "filas": [ci["fecha"]] if ci.get("fecha") else [],
                        "pie": ci.get("handle", "")}
        print("aviso: sin 'logo_led' -> uso placa de marca para entrada y cierre")
    if cfg.get("placa"):  # placa de marca en lugar del cartel LED
        INTRO, OUTRO = cfg["placa"].get("entrada", 2.2), cfg["placa"].get("cierre", 3.6)
    if cfg.get("acento"):
        CORAL = tuple(cfg["acento"])
    if cfg.get("sin_intro"):
        INTRO = 0.0
    if cfg.get("cierre_seg"):
        OUTRO = float(cfg["cierre_seg"])
    if cmd == "transcribir":
        transcribir(cfg)
    elif cmd == "preview":
        render(cfg, only_t=float(sys.argv[3]))
    elif cmd == "portada":
        portada(cfg)
    elif cmd == "render":
        render(cfg)
        portada(cfg)
