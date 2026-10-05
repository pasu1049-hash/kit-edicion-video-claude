"""SHOWREEL 1% — clips de entrenamiento sin voz, cortados al ritmo del beat.
Entrada LED -> clips (cada corte en el beat, con flash + zoom de impacto + etiqueta) -> cierre LED con CTA.

Uso: python showreel.py <config.json>   (el config define formato, clips, textos y cierre)
"""
import sys, json, subprocess, wave, pathlib
import numpy as np
from PIL import Image
import editar_video as E
import musica as M
import motion

ROOT = pathlib.Path(__file__).resolve().parent
motion.FONTS = E.FONTS


def reader(path, start, n, speed, crop, W, H):
    vf = (f"setpts=PTS/{speed},fps={E.FPS},crop={crop['w']}:{crop['h']}:{crop['x']}:{crop['y']},"
          f"scale={W}:{H}:flags=lanczos,eq=contrast=1.06:saturation=1.12:gamma=0.97")
    p = subprocess.Popen([E.FF, "-loglevel", "error", "-ss", str(start), "-i", path, "-vf", vf,
                          "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    size = W * H * 3
    last = None
    for _ in range(n):
        b = p.stdout.read(size)
        if len(b) < size:
            break
        last = np.frombuffer(b, np.uint8).reshape(H, W, 3)
        yield last
    p.kill(); p.stdout.close(); p.wait()


def zoom(img, z, W, H, cy=0.5):
    if z < 1.002:
        return img
    w, h = W / z, H / z
    x0, y0 = (W - w) / 2, min(max(H * cy - h / 2, 0), H - h)
    return img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + w, y0 + h))


# =====================================================================
# Placa de marca (p. ej. Sportclub rojo/blanco) para entrada y cierre
# =====================================================================
from PIL import ImageDraw, ImageFont


class Placa:
    """cfg["placa"] = {"color": [226,0,26], "marca": "SPORTCLUB", "kicker": "CALISTENIA",
                       "filas": ["LUNES Y JUEVES · 18 HS", "SÁBADOS · 11 HS"], "pie": "..."}"""
    def __init__(self, pc, W, H):
        self.W, self.H = W, H
        self.col = np.array(pc.get("color", [226, 0, 26]), np.float32) / 255
        f = lambda n, s: ImageFont.truetype(str(E.FONTS / n), s)
        cy = H // 2 - 120

        def layer(draw_fn):
            im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); draw_fn(ImageDraw.Draw(im)); return im

        def centered(d, y, txt, fnt, fill, sp=0):
            w = d.textlength(txt, font=fnt) + sp * (len(txt) - 1); x = (W - w) / 2
            for ch in txt:
                d.text((x, y), ch, font=fnt, fill=fill); x += d.textlength(ch, font=fnt) + sp

        fk = f("Poppins-Bold.ttf", pc.get("kicker_size", 44))
        self.kicker = layer(lambda d: centered(d, cy - 190, pc.get("kicker", ""), fk, (255, 255, 255, 235), sp=14))
        # marca grande, inclinada tipo logo deportivo
        fm = f("Poppins-Black.ttf", pc.get("size", 170))
        m = Image.new("RGBA", (W, 260), (0, 0, 0, 0)); dm = ImageDraw.Draw(m)
        tw = dm.textlength(pc["marca"], font=fm) - 4 * (len(pc["marca"]) - 1)
        x = (W - tw) / 2
        for ch in pc["marca"]:
            dm.text((x, 10), ch, font=fm, fill=(255, 255, 255, 255)); x += dm.textlength(ch, font=fm) - 4
        sh = pc.get("inclinacion", 0.2)
        m = m.transform(m.size, Image.AFFINE, (1, sh, -sh * 130, 0, 1, 0), Image.BICUBIC)
        self.marca = Image.new("RGBA", (W, H), (0, 0, 0, 0)); self.marca.alpha_composite(m, (0, cy - 120))
        self.line = layer(lambda d: d.rectangle(((W - 520) / 2, cy + 150, (W + 520) / 2, cy + 160), fill=(255, 255, 255, 255)))
        # horarios: caja blanca con texto en el color de la marca
        fr = f("Poppins-ExtraBold.ttf", 54)
        colt = tuple(int(c * 255) for c in self.col) + (255,)
        self.rows = []
        for i, row in enumerate(pc.get("filas", [])):
            y = cy + 230 + i * 120

            def dr(d, row=row, y=y):
                w = d.textlength(row, font=fr)
                d.rounded_rectangle(((W - w) / 2 - 40, y - 14, (W + w) / 2 + 40, y + 86), 18, fill=(255, 255, 255, 255))
                d.text(((W - w) / 2, y), row, font=fr, fill=colt)
            self.rows.append(layer(dr))
        fp = f("Poppins-SemiBold.ttf", 34)
        ypie = cy + 260 + len(self.rows) * 120
        self.pie = layer(lambda d: centered(d, ypie, pc.get("pie", ""), fp, (255, 255, 255, 220), sp=2))
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        self.stripes = ((((xx + yy * 0.6) / 70).astype(int) % 2) * 0.06 * pc.get("rayas", 1.0))[..., None]
        self.vig = (1 - 0.35 * np.clip(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2, 0, 1))[..., None]
        self.layers = ([(self.kicker, 0.25, 30), (self.marca, 0.35, 0), (self.line, 0.55, 0)]
                       + [(r, 0.7 + i * 0.18, 40) for i, r in enumerate(self.rows)] + [(self.pie, 1.1, 20)])

    def bg(self, t):
        f = np.broadcast_to(self.col, (self.H, self.W, 3)).astype(np.float32)
        st = np.roll(self.stripes, int((t * 40) % 140), axis=1)
        return (f * (1 - st)) * self.vig

    def frame(self, t, under=None, wipe=0.35, out_at=None):
        """t: segundos de la placa. under: cuadro de fondo (float 0..1) para el barrido de entrada."""
        f = self.bg(t)
        if under is not None:
            edge = int(self.H * (1 - E.ease(t / wipe)))
            g = under.copy(); g[edge:] = f[edge:]
            f = g
        img = Image.fromarray((np.clip(f, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
        for lay, t0, rise in self.layers:
            a = E.ease((t - t0) / 0.3)
            if a <= 0:
                continue
            l = lay
            if a < 1:
                l = lay.copy(); l.putalpha(l.getchannel("A").point(lambda v: int(v * a)))
            img.alpha_composite(l, (0, int((1 - a) * rise)))
        out = np.asarray(img.convert("RGB")).astype(np.float32) / 255
        if out_at is not None and t > out_at:
            out = out * (1 - E.ease((t - out_at) / 0.4))
        return out


def main(cfg):
    if cfg.get("formato") == "historia":
        E.W, E.H, E.DY = 1080, 1920, 285
    W, H = E.W, E.H
    bpm = cfg.get("bpm", 100)
    beat = 60 / bpm
    clips = cfg["clips"]
    # tiempos de cada clip (en segundos del tramo principal)
    t = 0.0
    for c in clips:
        c["t0"] = t
        c["dur"] = c["beats"] * beat
        c["n"] = int(round((t + c["dur"]) * E.FPS)) - int(round(t * E.FPS))
        t += c["dur"]
    main_d = t

    # gráficos: etiqueta por clip + textos extra (con tiempos en beats)
    mg = motion.Motion([], [])
    def add(e, t0, t1):
        base = motion.BUILD[e["tipo"]](e)
        img, pad = motion.shadowed(base)
        mg.items.append(dict(e=e, t0=t0, t1=t1, img=img, pad=pad))
    ly = cfg["etiqueta_y"]
    for c in clips:
        if c.get("label"):
            add(dict(tipo="chip", txt=c["label"], size=44, pos=[cfg.get("etiqueta_x", 300), ly], anim="slide",
                     desde=-420, claro=c.get("claro", True)), c["t0"] + beat * 0.5, c["t0"] + c["dur"] - 0.15)
    for x in cfg.get("textos", []):
        e = dict(x); b0, b1 = e.pop("beats")
        add(e, b0 * beat, b1 * beat)

    placa = Placa(cfg["placa"], W, H) if cfg.get("placa") else None
    if placa:
        E.INTRO, E.OUTRO = cfg["placa"].get("entrada", 2.6), cfg["placa"].get("cierre", 4.2)
    else:
        sign_in = E.Sign(1.25, 610 + E.DY)
        outro = E.Outro(cfg)
    total = E.INTRO + main_d + E.OUTRO

    # ---------------- audio: beat + impactos en los cortes
    rng = np.random.default_rng(5)
    n_all = int(total * M.SR)
    audio = np.zeros(n_all)
    if placa:  # la música arranca con la placa
        n0 = 0
        bed = M.beat(total + 1, bpm=bpm, seed=cfg.get("seed", 21))
        M._add(audio, 0.0, M.golpe(rng), 0.4)
        for _, t0, _ in placa.layers:
            M._add(audio, t0, M.pop(rng), 0.10)
            M._add(audio, E.INTRO + main_d + t0, M.pop(rng), 0.10)
        M._add(audio, E.INTRO + main_d - 0.2, M.whoosh(rng, 0.45), 0.2)
    else:
        a_in = E.neon_sfx(E.INTRO, lambda x: 0.7 * E.steps(x, E.IN_O) + 0.3 * E.steps(x, E.IN_W))
        audio[:len(a_in)] += a_in * 0.8
        bed = M.beat(main_d + E.OUTRO + 1, bpm=bpm, seed=cfg.get("seed", 21))
        n0 = int(E.INTRO * M.SR)
    seg = bed[: n_all - n0]
    tt = np.arange(len(seg)) / M.SR
    seg = seg * np.clip(tt / 0.02, 0, 1) * (1 - np.clip((tt - (len(seg) / M.SR - 0.9)) / 0.9, 0, 1))
    audio[n0:n0 + len(seg)] += seg * cfg.get("vol", 0.55)
    M._add(audio, E.INTRO - (0.8 if placa else 1.2), M.riser(0.8 if placa else 1.2, rng), 0.18)
    M._add(audio, E.INTRO, M.golpe(rng), 0.5)
    for c in clips[1:]:
        M._add(audio, E.INTRO + c["t0"] - 0.22, M.whoosh(rng, 0.35), 0.16)
    for it in mg.items:
        M._add(audio, E.INTRO + it["t0"], M.pop(rng), 0.10)
    M._add(audio, E.INTRO + main_d, M.golpe(rng), 0.45)
    peak = np.max(np.abs(audio)) or 1
    audio = np.tanh(audio / peak * 1.2) * 0.89
    out = E.OUT / cfg["salida"]
    wav = E.WORK / f"_mix_{out.stem}.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(M.SR)
        w.writeframes((audio * 32000).astype(np.int16).tobytes())

    enc = subprocess.Popen([E.FF, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(E.FPS), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "slow",
                            "-crf", "14", "-profile:v", "high", "-pix_fmt", "yuv420p", "-colorspace", "bt709",
                            "-color_primaries", "bt709", "-color_trc", "bt709", "-c:a", "aac", "-b:a", "320k",
                            "-ac", "2", "-shortest", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    rg = np.random.default_rng(7)
    for i in range(int(E.INTRO * E.FPS)):
        tq = i / E.FPS
        if placa:
            f = placa.frame(tq)
        else:
            f = sign_in.render(E.steps(tq, E.IN_O), E.steps(tq, E.IN_W), tq)
        f = f * (1 + 1.5 * E.ease((tq - (E.INTRO - 0.1)) / 0.1))
        f = f + rg.normal(0, 0.012, (H, W, 1)).astype(np.float32)
        enc.stdin.write((np.clip(f, 0, 1) * 255).astype(np.uint8).tobytes())

    last = None
    for ci, c in enumerate(clips):
        crop = c.get("recorte", cfg["recorte"])
        k = 0
        for fr in reader(c["src"], c["desde"], c["n"], c.get("vel", 1.0), crop, W, H):
            tl = k / E.FPS                       # tiempo dentro del clip
            tg = c["t0"] + tl                    # tiempo del tramo principal
            # zoom: impacto al entrar (1.14 -> 1.0) + deriva lenta; en el beat, un pulso chico
            z = 1 + 0.14 * (1 - E.ease(tl / 0.28)) + 0.05 * tl / c["dur"]
            ph = (tl % beat) / beat
            z *= 1 + 0.018 * np.exp(-ph * 8)
            img = zoom(Image.fromarray(fr), z, W, H, c.get("cy", 0.55))
            img = mg.draw(img, tg)
            a = np.asarray(img).astype(np.float32)
            if tl < 0.12:                         # flash de corte
                a = a + (1 - tl / 0.12) * 110
            last = np.clip(a, 0, 255).astype(np.uint8)
            enc.stdin.write(last.tobytes()); k += 1
        for _ in range(k, c["n"]):
            enc.stdin.write(last.tobytes())
    lastf = last.astype(np.float32) / 255
    for i in range(int(E.OUTRO * E.FPS)):
        f = placa.frame(i / E.FPS, under=lastf, out_at=E.OUTRO - 0.5) if placa else outro.frame(i / E.FPS, lastf)
        f = f + rg.normal(0, 0.012, (H, W, 1)).astype(np.float32)
        enc.stdin.write((np.clip(f, 0, 1) * 255).astype(np.uint8).tobytes())
    enc.stdin.close(); enc.wait()
    print("ok", out, f"{total:.1f}s")


if __name__ == "__main__":
    main(json.load(open(sys.argv[1], encoding="utf-8")))
