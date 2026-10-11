# /// script
# dependencies = ["numpy<2.3"]
# ///
"""Find hard cuts in dark, foggy footage.

ffmpeg's scene score barely moves here because every shot is the same murky
brown. Each frame is shrunk to 64x32, its brightness and contrast normalised,
and compared with the previous frame; a cut is a spike well above the local
motion level. Usage: uv run tools/cuts.py START END [THRESH]
"""
import subprocess, sys, pathlib
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
FPS = 30000 / 1001
w, h = 64, 32
s, e = float(sys.argv[1]), float(sys.argv[2])
THRESH = float(sys.argv[3]) if len(sys.argv) > 3 else 0.45
raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(s), "-i", str(ROOT / "marines-fixing-bugs.webm"), "-t", str(e - s),
                      "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
f = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(float)
f = (f - f.mean((1, 2), keepdims=True)) / (f.std((1, 2), keepdims=True) + 1e-3)
d = np.abs(np.diff(f, axis=0)).mean((1, 2))
for i in range(len(d)):
    local = np.median(d[max(0, i - 8):i + 9])
    if d[i] > THRESH and d[i] > 2.5 * local:
        print(f"cut before frame {round(s * FPS) + i + 1}  t={s + (i + 1) / FPS:.3f}s  score={d[i]:.2f} (local {local:.2f})")
