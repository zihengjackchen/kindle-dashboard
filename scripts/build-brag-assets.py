"""Prepare public launch assets and an original deterministic soundtrack."""
from pathlib import Path
import math
import shutil
import struct
import urllib.request
import wave

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "brag-output/composition/assets"
OUT.mkdir(parents=True, exist_ok=True)
for name in ("overview", "weather", "markdown", "home-server", "editor-widgets", "kindle-app"):
    shutil.copyfile(ROOT / f"docs/showcase/{name}.png", OUT / f"{name}.png")
with urllib.request.urlopen("https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js", timeout=30) as r:
    (OUT / "gsap.min.js").write_bytes(r.read())
rate = 22050
notes = [130.8128, 164.8138, 195.9977, 246.9417, 146.8324, 174.6141, 220.0, 261.6256]
frames = bytearray()
for n in range(rate * 20):
    t = n / rate
    beat = int(t / .625)
    phase = t - beat * .625
    freq = notes[(beat // 8 * 4 + beat % 4) % len(notes)]
    envelope = (1 - math.exp(-phase * 100)) * math.exp(-phase * 5)
    tone = (math.sin(2*math.pi*freq*2*phase) + .25*math.sin(2*math.pi*freq*4*phase)) * envelope * .15
    tone += .035 * math.sin(2*math.pi*notes[(beat//8*4)%8]*t)
    for at in (4.375, 13.125):
        d = t-at
        if 0 <= d < .08: tone += .12*math.sin(2*math.pi*720*d)*math.exp(-d*65)
    fade = min(1, t/.3, (20-t)/1.2)
    frames.extend(struct.pack('<h', round(max(-1,min(1,tone*fade))*32767)))
with wave.open(str(OUT / "paper-notes.wav"), 'wb') as w:
    w.setparams((1,2,rate,0,'NONE','not compressed')); w.writeframes(frames)
print('Copied public screenshots and generated original 20-second soundtrack.')
