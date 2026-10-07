#!/usr/bin/env python3
"""PS5 RPCS3 - the launcher intro's sound, written to ps5/assets/launcher/intro.wav.

Synthesised here from sine and saw waves and noise, nothing sampled: a swell
that rises while the white screen's shards fly in, a bell shimmer as they lock
into the diamond, then on the black screen a low hum and a two-note chime. It
follows the launcher's timeline (ps5_launcher.cpp, "Its timeline"); move both
together.

48 kHz, 16-bit stereo, as the console's audio output takes it. Needs numpy.
Run once; commit what it writes.
"""

import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "ps5" / "assets" / "launcher" / "intro.wav"

RATE = 48000
LENGTH = 7.0

# The timeline's moments, in seconds (the launcher's c_intro_* constants)
SWELL = 0.15      # the shards set off
LOCK = 1.5        # they lock into the diamond
WHITE_OUT = 3.5   # the white screen fades
BLACK = 4.2       # the logo comes up on black

t = np.arange(int(RATE * LENGTH)) / RATE
rng = np.random.default_rng(3)


def note(name):
    names = {"C": -9, "D": -7, "E": -5, "F": -4, "F#": -3, "G": -2, "A": 0, "B": 2}
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[pitch] + 12 * (octave - 4)) / 12)


def saw(freq, phase=0.0):
    x = (t * freq + phase) % 1.0
    return 2.0 * x - 1.0


def window(start, attack, end, release, curve=1.0):
    """0 before start, rising over attack, 1 until end, falling over release."""
    up = np.clip((t - start) / attack, 0, 1) ** curve
    down = np.clip(1 - (t - end) / release, 0, 1)
    return up * down


def lowpass(x, cutoff):
    """One-pole lowpass with a cutoff that may change sample by sample."""
    a = 1 - np.exp(-2 * np.pi * np.broadcast_to(cutoff, x.shape) / RATE)
    y = np.empty_like(x)
    state = 0.0
    for i in range(len(x)):
        state += a[i] * (x[i] - state)
        y[i] = state
    return y


def bell(freq, start, decay, level):
    """A struck glassy tone: a sine and two inharmonic partials, each fading."""
    s = np.clip(t - start, 0, None)
    on = (t >= start).astype(float)
    attack = np.clip(s / 0.004, 0, 1)
    tone = (np.sin(2 * np.pi * freq * s) * np.exp(-s / decay)
            + 0.35 * np.sin(2 * np.pi * freq * 2.76 * s) * np.exp(-s / (decay * 0.45))
            + 0.12 * np.sin(2 * np.pi * freq * 5.40 * s) * np.exp(-s / (decay * 0.2)))
    return level * on * attack * tone


def comb(x, delay, gain):
    y = x.copy()
    for start in range(delay, len(x), delay):
        end = min(start + delay, len(x))
        y[start:end] += gain * y[start - delay:end - delay]
    return y


def allpass(x, delay, gain):
    y = np.zeros_like(x)
    padded = np.concatenate([np.zeros(delay), x])
    for start in range(0, len(x), delay):
        end = min(start + delay, len(x))
        back = y[start - delay:end - delay] if start >= delay else np.zeros(end - start)
        y[start:end] = -gain * x[start:end] + padded[start:end] + gain * back
    return y


def reverb(x, spread):
    """Schroeder's: four combs side by side, then two allpasses."""
    combs = [1557, 1617, 1491, 1422]
    wet = sum(comb(x, d + spread, 0.82) for d in combs) / 4
    for d in (225, 556):
        wet = allpass(wet, d + spread // 2, 0.5)
    return wet


def channel(side):
    detune = 1.0 + 0.0035 * side

    # The swell: a wide chord of detuned saws opening up through a lowpass,
    # with a rising breath of noise, until the shards lock
    chord = [note(n) for n in ("D3", "A3", "D4", "E4", "F#4", "A4")]
    pad = sum(saw(f * detune, phase=0.17 * k) + saw(f / detune, phase=0.41 * k) for k, f in enumerate(chord)) / (2 * len(chord))
    swell = window(SWELL, LOCK - SWELL, LOCK, 2.2, curve=1.4)
    cutoff = 180 + 4200 * np.clip((t - SWELL) / (LOCK - SWELL), 0, 1) ** 2
    cutoff = np.where(t > LOCK, 4380 * np.exp(-(t - LOCK) / 0.9) + 300, cutoff)
    pad = lowpass(pad, cutoff) * swell * 0.8

    noise = lowpass(rng.standard_normal(len(t)), 300 + 5000 * np.clip((t - SWELL) / (LOCK - SWELL), 0, 1) ** 3)
    breath = noise * window(SWELL + 0.3, LOCK - SWELL - 0.3, LOCK, 0.12, curve=3) * 0.18

    # The lock: a soft low thump and a quick rising shimmer of bells
    s = np.clip(t - LOCK, 0, None)
    thump = np.sin(2 * np.pi * (48 * s + 30 * (1 - np.exp(-s / 0.05)) * 0.05)) * np.exp(-s / 0.28) * (t >= LOCK) * 0.5
    shimmer = sum(bell(note(n) * detune, LOCK + 0.055 * k, 1.6, 0.16)
                  for k, n in enumerate(("D6", "F#6", "A6", "D7")))
    shimmer += bell(note("A5") / detune, LOCK, 2.2, 0.12)

    # The black screen: a low hum, and a two-note chime
    hum = (np.sin(2 * np.pi * note("D2") * t) + 0.6 * np.sin(2 * np.pi * note("A2") * detune * t)) \
        * window(BLACK, 0.45, BLACK + 1.4, 1.3) * 0.22
    chime = bell(note("A5") * detune, BLACK + 0.05, 1.5, 0.2) + bell(note("D6") / detune, BLACK + 0.38, 1.9, 0.22)

    dry = pad + breath + thump + shimmer + hum + chime
    dry *= np.clip(1 - (t - (LENGTH - 0.4)) / 0.4, 0, 1)
    return dry + 0.35 * reverb(dry, 23 if side > 0 else 0)


def main():
    left, right = channel(-1), channel(1)
    stereo = np.stack([left, right], axis=1)
    stereo *= 0.5 / np.max(np.abs(stereo))  # peaks at -6 dBFS
    samples = (stereo * 32767).astype("<i2")

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(TARGET), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(samples.tobytes())
    print(f"wrote {TARGET.relative_to(ROOT)} ({LENGTH:.1f} s, {TARGET.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    main()
