"""Música de fondo propia (sin derechos) + efectos para la plantilla 1%.

beat(): base de trap/hip-hop suave en La menor (Am-F-C-G) con kick, clap, hats, bajo y colchón.
ducking(): baja la música cuando habla la voz.
Los efectos (whoosh, golpe, riser) marcan los motion graphics y los cortes.
"""
import numpy as np

SR = 48000
PROG = [(55.00, (220.00, 261.63, 329.63)),   # Am
        (43.65, (174.61, 220.00, 261.63)),   # F
        (65.41, (196.00, 261.63, 329.63)),   # C
        (49.00, (196.00, 246.94, 293.66))]   # G


def _add(buf, at, sig, g=1.0):
    j = int(at * SR)
    if j >= len(buf) or j + len(sig) <= 0:
        return
    if j < 0:
        sig, j = sig[-j:], 0
    n = min(len(sig), len(buf) - j)
    buf[j:j + n] += sig[:n] * g


def _kick(rng):
    n = int(SR * 0.4); t = np.arange(n) / SR
    f = 48 + 120 * np.exp(-t * 32)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)


def _clap(rng):
    n = int(SR * 0.25); t = np.arange(n) / SR
    x = rng.normal(0, 1, n)
    x = x - np.convolve(x, np.ones(6) / 6, "same")  # saca graves
    env = np.exp(-t * 22) + 0.6 * np.exp(-((t - 0.012) * 400) ** 2) + 0.5 * np.exp(-((t - 0.024) * 400) ** 2)
    return x * env * 0.8


def _hat(rng, open_=False):
    n = int(SR * (0.18 if open_ else 0.05)); t = np.arange(n) / SR
    x = np.diff(rng.normal(0, 1, n + 1))
    return x * np.exp(-t * (18 if open_ else 90)) * 0.5


def _bass(f0, dur):
    n = int(SR * dur); t = np.arange(n) / SR
    s = np.sin(2 * np.pi * f0 * t) + 0.35 * np.sin(2 * np.pi * 2 * f0 * t)
    env = np.clip(t / 0.01, 0, 1) * np.exp(-t * 1.6)
    return np.tanh(s * 1.4) * env


def _pad(freqs, dur):
    n = int(SR * dur); t = np.arange(n) / SR
    s = sum(np.sin(2 * np.pi * f * t + i) + 0.4 * np.sin(2 * np.pi * f * 1.003 * t) for i, f in enumerate(freqs))
    env = np.clip(t / 0.4, 0, 1) * np.clip((dur - t) / 0.4, 0, 1)
    return s * env / len(freqs)


def _pluck(f, rng):
    n = int(SR * 0.35); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * 2 * f * t)) * np.exp(-t * 11)


def beat(dur, bpm=92, seed=3, energia=1.0):
    """Base loopeable. energia < 1 = más tranqui (menos hats)."""
    rng = np.random.default_rng(seed)
    buf = np.zeros(int(dur * SR))
    beat_s = 60 / bpm
    bar = beat_s * 4
    kick, clap = _kick(rng), _clap(rng)
    hat, ohat = _hat(rng), _hat(rng, True)
    nbars = int(np.ceil(dur / bar)) + 1
    arp = [0, 1, 2, 1, 0, 2, 1, 2]
    for b in range(nbars):
        t0 = b * bar
        root, chord = PROG[b % 4]
        _add(buf, t0, _pad(chord, bar), 0.10)
        # bajo: 1 y "3 y"
        _add(buf, t0, _bass(root, beat_s * 1.8), 0.34)
        _add(buf, t0 + beat_s * 2.5, _bass(root, beat_s * 1.2), 0.26)
        # kick (patrón trap tranqui)
        for k in (0, 1.75, 2.5):
            _add(buf, t0 + k * beat_s, kick, 0.62)
        for k in (1, 3):
            _add(buf, t0 + k * beat_s, clap, 0.30)
        # hats en corcheas (semicorcheas en el último tiempo cada 2 compases)
        step = 0.5
        k = 0.0
        while k < 4:
            if b % 2 == 1 and k >= 3 and energia >= 1:
                for s in range(4):
                    _add(buf, t0 + (k + s * 0.125) * beat_s, hat, 0.10)
                k += 0.5
                continue
            _add(buf, t0 + k * beat_s, hat, 0.12 if k % 1 == 0 else 0.07 * energia)
            k += step
        _add(buf, t0 + 3.5 * beat_s, ohat, 0.06)
        # pluck arpegiado suave
        for i, a in enumerate(arp):
            _add(buf, t0 + i * beat_s / 2, _pluck(chord[a] * 2, rng), 0.045)
    return buf


def ducking(voice, amount=0.72, attack=0.03, release=0.35):
    """Ganancia 0..1 para la música según la energía de la voz (sidechain simple)."""
    hop = int(SR * 0.01)
    n = len(voice)
    rms = np.sqrt(np.convolve(voice ** 2, np.ones(hop * 4) / (hop * 4), "same")[::hop])
    ref = np.percentile(rms, 90) or 1
    lvl = np.clip(rms / ref * 1.6, 0, 1)
    env = np.zeros_like(lvl)
    a_up, a_dn = np.exp(-0.01 / attack), np.exp(-0.01 / release)
    for i, x in enumerate(lvl):
        prev = env[i - 1] if i else 0
        c = a_up if x > prev else a_dn
        env[i] = c * prev + (1 - c) * x
    g = 1 - amount * env
    return np.interp(np.arange(n), np.arange(len(g)) * hop, g)


def whoosh(rng, dur=0.45):
    n = int(SR * dur); t = np.arange(n) / SR
    x = rng.normal(0, 1, n)
    x = np.convolve(x, np.ones(10) / 10, "same")
    env = np.sin(np.pi * t / dur) ** 3
    return x * env * 0.9


def golpe(rng):
    n = int(SR * 0.9); t = np.arange(n) / SR
    s = np.sin(2 * np.pi * (60 - 25 * t) * t) * np.exp(-t * 5)
    s += rng.normal(0, 1, n) * np.exp(-t * 60) * 0.3
    return s


def pop(rng):
    n = int(SR * 0.08); t = np.arange(n) / SR
    return np.sin(2 * np.pi * (900 - 5000 * t) * t) * np.exp(-t * 45) * 0.6


def riser(dur=1.2, rng=None):
    rng = rng or np.random.default_rng(1)
    n = int(SR * dur); t = np.arange(n) / SR
    x = rng.normal(0, 1, n)
    x = x - np.convolve(x, np.ones(30) / 30, "same")
    return x * (t / dur) ** 2.5 * 0.6
