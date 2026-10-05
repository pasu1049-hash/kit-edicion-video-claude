"""Motion graphics de marca 1% sobre el clip principal.
Se definen en el config como lista "motion": cada elemento se dispara en una palabra.

  {"tipo": "calendario", "palabra": "viernes", "n": 1, "hasta": "noche?", "txt": "VIERNES", "sub": "21 HS", "pos": [790, 70]}
  tipos: calendario, sello, envivo, slam, chip, contador, misterio, plataforma, texto
  "n": número de aparición de la palabra (1 = primera). "hasta": palabra en la que termina (+0.5 s) o "dur".
"""
import math, re
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

CORAL = (255, 104, 74, 255)
INK = (17, 17, 17, 255)
WHITE = (255, 255, 255, 255)
FONTS = None  # lo setea editar_video


def f(n, s):
    return ImageFont.truetype(str(FONTS / n), s)


def norm(w):
    return re.sub(r"[^\wáéíóúñü%]", "", w.lower())


def out_back(x):
    x = min(max(x, 0), 1)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ease(x):
    x = min(max(x, 0), 1)
    return x * x * (3 - 2 * x)


def shadowed(img, blur=14, off=(0, 10), alpha=150):
    """Agrega sombra suave debajo de un elemento RGBA."""
    pad = blur * 3
    W, H = img.size
    out = Image.new("RGBA", (W + pad * 2, H + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    a = img.getchannel("A").point(lambda v: v * alpha // 255)
    sh.paste((0, 0, 0, 255), (pad + off[0], pad + off[1]), a)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(sh)
    out.alpha_composite(img, (pad, pad))
    return out, pad


def rounded(size, r, fill, outline=None, width=0):
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), r, fill=fill, outline=outline, width=width)
    return im


def text_img(txt, font, fill, pad=(0, 0)):
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    l, t, r, b = d.textbbox((0, 0), txt, font=font)
    im = Image.new("RGBA", (r - l + pad[0] * 2, b - t + pad[1] * 2), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad[0] - l, pad[1] - t), txt, font=font, fill=fill)
    return im


# ---------------------------------------------------------------------
# Constructores de elementos (devuelven imagen RGBA base)
# ---------------------------------------------------------------------
def el_calendario(e):
    w, h = 250, 250
    im = rounded((w, h), 28, WHITE)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, 78), 28, fill=CORAL)
    d.rectangle((0, 50, w - 1, 78), fill=CORAL)
    ft = f("Poppins-ExtraBold.ttf", 34)
    tw = d.textlength(e.get("txt", "VIERNES"), font=ft)
    d.text(((w - tw) / 2, 16), e.get("txt", "VIERNES"), font=ft, fill=WHITE)
    fb = f("Poppins-Black.ttf", 96)
    big = e.get("big", "21")
    tw = d.textlength(big, font=fb)
    d.text(((w - tw) / 2, 78), big, font=fb, fill=INK)
    fs = f("Poppins-Bold.ttf", 28)
    sub = e.get("sub", "HS · EN VIVO")
    tw = d.textlength(sub, font=fs)
    d.text(((w - tw) / 2, 196), sub, font=fs, fill=(90, 90, 90, 255))
    # anillas
    for x in (70, w - 70):
        d.rounded_rectangle((x - 7, -14, x + 7, 22), 7, fill=INK)
    return im


def el_sello(e):
    ft = f("Poppins-Black.ttf", e.get("size", 64))
    t = text_img(e.get("txt", "NUEVO"), ft, WHITE)
    w, h = t.width + 70, t.height + 44
    im = rounded((w, h), h // 2, CORAL)
    im.alpha_composite(t, (35, 22))
    return im


def el_envivo(e):
    ft = f("Poppins-ExtraBold.ttf", 40)
    t = text_img(e.get("txt", "EN VIVO"), ft, WHITE)
    w, h = t.width + 110, t.height + 40
    im = rounded((w, h), h // 2, (17, 17, 17, 235))
    im.alpha_composite(t, (80, 20))
    return im  # el punto titilante se dibuja aparte


def el_slam(e):
    ft = f("Poppins-Black.ttf", e.get("size", 300))
    txt = e.get("txt", "1%")
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    l, t, r, b = d.textbbox((0, 0), txt, font=ft)
    pad = 40
    im = Image.new("RGBA", (r - l + pad * 2, b - t + pad * 2), (0, 0, 0, 0))
    dd = ImageDraw.Draw(im)
    x = pad - l
    for ch in txt:
        col = CORAL if ch == "%" else WHITE
        dd.text((x, pad - t), ch, font=ft, fill=col, stroke_width=6, stroke_fill=INK)
        x += dd.textlength(ch, font=ft)
    glow = im.filter(ImageFilter.GaussianBlur(22))
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    g = np.asarray(glow).astype(np.float32); g[..., :3] = [255, 104, 74]; g[..., 3] *= 0.6
    out.alpha_composite(Image.fromarray(g.astype(np.uint8)))
    out.alpha_composite(im)
    return out


def el_chip(e):
    ft = f("Poppins-ExtraBold.ttf", e.get("size", 42))
    t = text_img(e.get("txt", ""), ft, INK if e.get("claro", True) else WHITE)
    w, h = t.width + 64, t.height + 34
    im = rounded((w, h), 18, WHITE if e.get("claro", True) else INK)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, 12, h - 1), 6, fill=CORAL)
    im.alpha_composite(t, (38, 17))
    return im


def el_plataforma(e):
    colors = {"TIKTOK": ((17, 17, 17, 255), WHITE), "YOUTUBE": ((230, 33, 23, 255), WHITE),
              "KICK": ((83, 252, 24, 255), INK)}
    bg, fg = colors.get(e["txt"].upper(), (INK, WHITE))
    ft = f("Poppins-Black.ttf", 44)
    t = text_img(e["txt"].upper(), ft, fg)
    w, h = t.width + 64, t.height + 36
    im = rounded((w, h), h // 2, bg, outline=(255, 255, 255, 90), width=3)
    im.alpha_composite(t, (32, 18))
    return im


def el_texto(e):
    ft = f(e.get("font", "Poppins-Black.ttf"), e.get("size", 60))
    col = CORAL if e.get("coral") else WHITE
    t = text_img(e["txt"], ft, col, pad=(10, 10))
    st = Image.new("RGBA", t.size, (0, 0, 0, 0))
    ImageDraw.Draw(st)
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    l, tp, r, b = d.textbbox((0, 0), e["txt"], font=ft)
    im = Image.new("RGBA", (r - l + 30, b - tp + 30), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((15 - l, 15 - tp), e["txt"], font=ft, fill=col, stroke_width=5, stroke_fill=INK)
    return im


def el_misterio(e):
    w, h = 300, 330
    im = rounded((w, h), 30, (17, 17, 17, 240), outline=CORAL, width=4)
    d = ImageDraw.Draw(im)
    # silueta
    cx = w // 2
    d.ellipse((cx - 52, 40, cx + 52, 144), fill=(60, 60, 60, 255))
    d.rounded_rectangle((cx - 95, 150, cx + 95, 250), 60, fill=(60, 60, 60, 255))
    fq = f("Poppins-Black.ttf", 120)
    tw = d.textlength("?", font=fq)
    d.text((cx - tw / 2, 30), "?", font=fq, fill=CORAL)
    fs = f("Poppins-ExtraBold.ttf", 30)
    for i, line in enumerate(e.get("lineas", ["INVITADO", "ESPECIAL"])):
        tw = d.textlength(line, font=fs)
        d.text((cx - tw / 2, 252 + i * 34), line, font=fs, fill=WHITE)
    return im


def el_contador(e):
    w, h = 470, 190
    im = rounded((w, h), 26, (17, 17, 17, 235))
    return im  # contenido animado se dibuja en draw()


BUILD = {"calendario": el_calendario, "sello": el_sello, "envivo": el_envivo, "slam": el_slam, "chip": el_chip,
         "plataforma": el_plataforma, "texto": el_texto, "misterio": el_misterio, "contador": el_contador}


class Motion:
    def __init__(self, events, words_out):
        """events: config; words_out: palabras con tiempos del clip editado."""
        self.items = []
        for e in events:
            t0 = self._find(words_out, e["palabra"], e.get("n", 1), "s") + e.get("offset", 0)
            if "hasta" in e:
                t1 = self._find(words_out, e["hasta"], e.get("n_hasta", 1), "e") + e.get("extra", 0.5)
            else:
                t1 = t0 + e.get("dur", 1.6)
            base = BUILD[e["tipo"]](e)
            img, pad = shadowed(base)
            self.items.append(dict(e=e, t0=t0, t1=t1, img=img, pad=pad))

    @staticmethod
    def _find(words, w, n, key):
        k = 0
        for x in words:
            if norm(x["w"]) == norm(w):
                k += 1
                if k == n:
                    return x[key]
        raise ValueError(f"palabra no encontrada: {w} #{n}")

    def draw(self, frame, t):
        """frame: PIL RGB -> PIL RGB"""
        act = [it for it in self.items if it["t0"] - 0.05 <= t <= it["t1"] + 0.3]
        if not act:
            return frame
        base = frame.convert("RGBA")
        for it in act:
            e, img = it["e"], it["img"]
            p_in = (t - it["t0"]) / 0.35
            p_out = 1 - ease((t - it["t1"]) / 0.3)
            if p_out <= 0 or p_in <= 0:
                continue
            anim = e.get("anim", "pop")
            s = out_back(p_in) if anim == "pop" else 1.0
            dx = dy = 0
            rot = e.get("rot", 0)
            if anim == "slide":
                dx = (1 - out_back(p_in)) * e.get("desde", 400)
            if anim == "slam":
                s = 1 + 1.4 * (1 - ease(p_in * 1.4)) if p_in < 0.72 else 1.0
                if 0.5 < p_in < 1.3:  # sacudida
                    dx = math.sin(t * 90) * 10 * (1.3 - p_in)
                    dy = math.cos(t * 77) * 8 * (1.3 - p_in)
            a = min(1.0, max(0.0, p_in * 2.5)) * p_out
            im = img
            if e["tipo"] in ("envivo", "contador"):
                im = img.copy()
                d = ImageDraw.Draw(im)
                pad = it["pad"]
                if e["tipo"] == "envivo":
                    on = (int(t * 2.4) % 2 == 0)
                    r = 11
                    cy = pad + (img.height - 2 * pad) // 2
                    d.ellipse((pad + 34 - r, cy - r, pad + 34 + r, cy + r), fill=CORAL if on else (120, 40, 30, 255))
                else:
                    self._draw_counter(d, pad, t - it["t0"], e)
            s *= e.get("escala", 1.0)
            if abs(s - 1) > 0.01 or rot:
                im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BICUBIC)
                if rot:
                    im = im.rotate(rot, Image.BICUBIC, expand=True)
            if a < 1:
                im = im.copy()
                im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
            cx, cy = e["pos"]
            x = int(cx + dx - im.width / 2)
            y = int(cy + dy - im.height / 2)
            sx, sy = max(0, -x), max(0, -y)
            x, y = max(0, x), max(0, y)
            wv, hv = min(im.width - sx, base.width - x), min(im.height - sy, base.height - y)
            if wv > 0 and hv > 0:
                base.alpha_composite(im.crop((sx, sy, sx + wv, sy + hv)), (x, y))
        return base.convert("RGB")

    @staticmethod
    def _draw_counter(d, pad, tt, e):
        x0, y0 = pad, pad
        w, h = 470, 190
        prog = ease(tt / 1.6)
        fl = f("Poppins-Bold.ttf", 26)
        d.text((x0 + 28, y0 + 22), "CADA DÍA", font=fl, fill=(200, 200, 200, 255))
        fb = f("Poppins-Black.ttf", 70)
        val = f"+{prog * 1:.0f}%" if prog >= 0.99 else f"+{prog:.2f}%".replace("0.", ".")
        val = "+1%" if prog > 0.97 else val
        d.text((x0 + 26, y0 + 50), val, font=fb, fill=CORAL)
        # gráfico que sube
        gx0, gy0, gx1, gy1 = x0 + 250, y0 + 40, x0 + w - 30, y0 + h - 34
        pts = []
        n = 24
        for i in range(n + 1):
            u = i / n
            if u > prog:
                break
            yy = gy1 - (gy1 - gy0) * (u ** 1.8)
            pts.append((gx0 + (gx1 - gx0) * u, yy))
        d.line((gx0, gy1, gx1, gy1), fill=(80, 80, 80, 255), width=2)
        if len(pts) > 1:
            d.line(pts, fill=CORAL, width=7, joint="curve")
            ex, ey = pts[-1]
            d.ellipse((ex - 9, ey - 9, ex + 9, ey + 9), fill=WHITE)
        # barra de progreso
        d.rounded_rectangle((x0 + 28, y0 + h - 30, x0 + 230, y0 + h - 20), 5, fill=(60, 60, 60, 255))
        d.rounded_rectangle((x0 + 28, y0 + h - 30, x0 + 28 + max(10, 202 * prog), y0 + h - 20), 5, fill=CORAL)
