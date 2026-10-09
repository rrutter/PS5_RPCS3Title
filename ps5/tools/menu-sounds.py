#!/usr/bin/env python3
"""PS5 RPCS3 - the menus' sounds, written to ps5/assets/launcher/sounds/.

Synthesised here from sine and saw waves and noise, nothing sampled, in the
intro's voice (intro-sound.py): glassy struck tones, a short room. One file
for each of RPCS3's overlay sounds (rsx::overlays::sound_effect, named as
RPCS3 names them), which the launcher, the pause menu and RPCS3's own dialogs
play:

    snd_cursor      a move: a soft, short tick (heard the most, so the quietest)
    snd_decide      a choice made: two notes rising
    snd_cancel      back: two notes falling
    snd_system_ok   a message: three notes rising
    snd_system_ng   an error: two low knocks
    snd_oskenter    the on-screen keyboard's keys
    snd_oskcancel   the on-screen keyboard closed
    snd_trophy      a trophy: a rising sparkle

A file of the same name in the title's rpcs3/sounds/ folder is played in its
place (ps5_sound.cpp), as RPCS3's own sound folder works on a PC.

48 kHz, 16-bit stereo, as the console's audio output takes it. Needs numpy.
Run once; commit what it writes.
"""

import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "ps5" / "assets" / "launcher" / "sounds"

RATE = 48000
rng = np.random.default_rng(7)


def note(name):
    names = {"C": -9, "D": -7, "E": -5, "F": -4, "F#": -3, "G": -2, "G#": -1, "A": 0, "B": 2}
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[pitch] + 12 * (octave - 4)) / 12)


def timeline(length):
    return np.arange(int(RATE * length)) / RATE


def bell(t, freq, start, decay, level, attack=0.003):
    """A struck glassy tone: a sine and two inharmonic partials, each fading."""
    s = np.clip(t - start, 0, None)
    on = (t >= start).astype(float)
    rise = np.clip(s / attack, 0, 1)
    tone = (np.sin(2 * np.pi * freq * s) * np.exp(-s / decay)
            + 0.30 * np.sin(2 * np.pi * freq * 2.76 * s) * np.exp(-s / (decay * 0.4))
            + 0.08 * np.sin(2 * np.pi * freq * 5.40 * s) * np.exp(-s / (decay * 0.18)))
    return level * on * rise * tone


def tick(t, freq, start, level):
    """A tiny struck tick: a high tone gone in a few milliseconds, a breath of noise."""
    s = np.clip(t - start, 0, None)
    on = (t >= start).astype(float)
    rise = np.clip(s / 0.0008, 0, 1)
    tone = np.sin(2 * np.pi * freq * s) * np.exp(-s / 0.012) + 0.4 * np.sin(2 * np.pi * freq * 1.5 * s) * np.exp(-s / 0.006)
    noise = lowpass(rng.standard_normal(len(t)), 6000) * np.exp(-s / 0.002) * 0.5
    return level * on * rise * (tone + noise)


def knock(t, freq, start, level):
    """A low, muffled knock: a tone that drops a little as it fades, and a soft thud."""
    s = np.clip(t - start, 0, None)
    on = (t >= start).astype(float)
    rise = np.clip(s / 0.002, 0, 1)
    phase = 2 * np.pi * freq * (s - 0.02 * (1 - np.exp(-s / 0.02)))
    tone = (np.sin(phase) + 0.35 * np.sin(2 * phase) + 0.12 * np.sin(3 * phase)) * np.exp(-s / 0.075)
    thud = lowpass(rng.standard_normal(len(t)), 400) * np.exp(-s / 0.01) * 2.0
    return level * on * rise * (tone + thud)


def lowpass(x, cutoff):
    """One-pole lowpass."""
    a = 1 - np.exp(-2 * np.pi * cutoff / RATE)
    y = np.empty_like(x)
    state = 0.0
    for i in range(len(x)):
        state += a * (x[i] - state)
        y[i] = state
    return y


def room(x, spread):
    """A short room: four feedback delays of 11 to 23 ms, side by side."""
    wet = np.zeros_like(x)
    for delay, gain in ((541 + spread, 0.55), (683 + spread, 0.5), (877 + spread, 0.45), (1103 + spread, 0.4)):
        y = x.copy()
        for start in range(delay, len(x), delay):
            end = min(start + delay, len(x))
            y[start:end] += gain * y[start - delay:end - delay]
        wet += y - x
    return lowpass(wet / 4, 5000)


def render(make, length, peak_db, wet=0.25):
    """Both channels (the right a hair sharper), a little room, faded at the end, peaking at peak_db."""
    t = timeline(length)
    channels = []
    for side, spread in ((-1, 0), (1, 37)):
        detune = 1.0 + 0.002 * side
        dry = make(t, detune)
        mixed = dry + wet * room(dry, spread)
        fade = np.clip((length - t) / 0.03, 0, 1)
        channels.append(mixed * fade)
    stereo = np.stack(channels, axis=1)
    stereo *= 10 ** (peak_db / 20) / np.max(np.abs(stereo))
    return stereo


SOUNDS = {
    "snd_cursor": (lambda t, d: tick(t, 2400 * d, 0.0, 1.0) + bell(t, note("E6") * d, 0.0, 0.035, 0.25), 0.16, -20.0, 0.18),
    "snd_decide": (lambda t, d: bell(t, note("E6") * d, 0.0, 0.16, 0.8) + bell(t, note("B6") * d, 0.055, 0.22, 0.9), 0.65, -12.0, 0.3),
    "snd_cancel": (lambda t, d: bell(t, note("B5") * d, 0.0, 0.12, 0.8) + bell(t, note("E5") * d, 0.06, 0.16, 0.85), 0.5, -14.0, 0.25),
    "snd_system_ok": (lambda t, d: sum(bell(t, note(n) * d, 0.07 * k, 0.35, 0.8) for k, n in enumerate(("C6", "E6", "G6"))), 1.1, -12.0, 0.35),
    "snd_system_ng": (lambda t, d: knock(t, note("D3") * d, 0.0, 1.0) + knock(t, note("D3") * d, 0.13, 0.9), 0.45, -12.0, 0.2),
    "snd_oskenter": (lambda t, d: tick(t, 2900 * d, 0.0, 1.0) + bell(t, note("G6") * d, 0.0, 0.05, 0.35), 0.18, -18.0, 0.18),
    "snd_oskcancel": (lambda t, d: tick(t, 1600 * d, 0.0, 1.0) + bell(t, note("C6") * d, 0.0, 0.06, 0.35), 0.2, -18.0, 0.18),
    "snd_trophy": (lambda t, d: sum(bell(t, note(n) * d, 0.06 * k, 0.6, 0.7) for k, n in enumerate(("C6", "E6", "G6", "C7", "E7")))
                   + bell(t, note("C5") * d, 0.0, 0.9, 0.35), 1.8, -10.0, 0.4),
}


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    for name, (make, length, peak_db, wet) in SOUNDS.items():
        samples = (render(make, length, peak_db, wet) * 32767).astype("<i2")
        with wave.open(str(TARGET / f"{name}.wav"), "wb") as out:
            out.setnchannels(2)
            out.setsampwidth(2)
            out.setframerate(RATE)
            out.writeframes(samples.tobytes())
        print(f"{name}.wav: {length:.2f} s, peak {peak_db:.0f} dBFS")


if __name__ == "__main__":
    main()
