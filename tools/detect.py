# /// script
# dependencies = ["numpy<2.3", "scipy<1.16"]
# ///
"""Auto-detect faint background figures in the fog.

The fog is a smooth gradient; a figure is a patch noticeably darker than the
fog around it. Per frame: local darkness = blur(gray) - gray, threshold,
drop anything under a hero mask, keep figure-shaped blobs (taller than wide,
plausible size), then link blobs frame to frame into tracks. Tracks that last
long enough become candidate enemies (head = top centre of the blob).

Usage: uv run tools/detect.py SHOT START END   -> data/detected_<SHOT>.json
"""
import json, subprocess, sys, pathlib
import numpy as np
from scipy import ndimage as ndi

ROOT = pathlib.Path(__file__).resolve().parent.parent
FPS = 30000 / 1001
W, H = 480, 240          # analysis size; work space is 1920x960 (x4)
DARK = 5                 # grey levels darker than the local fog
MIN_H, MAX_H = 18, 150   # blob height in analysis px
LINK = 14                # max head jump per frame (analysis px)
MIN_LEN = 8              # frames

def heroes(names, f0, n):
    m = np.zeros((n, H, W), bool)
    for name in names:
        z = np.load(ROOT / "data/masks" / f"{name}.npz")
        m0 = int(z["first_frame"])
        for k in z.files:
            if not k.startswith("hero"):
                continue
            hm = np.unpackbits(z[k], axis=-1)[..., :960].astype(bool)[:, ::2, ::2]
            lo, hi = max(f0, m0), min(f0 + n - 1, m0 + len(hm) - 1)
            if lo <= hi:
                m[lo - f0:hi - f0 + 1] |= hm[lo - m0:hi - m0 + 1]
    return ndi.binary_dilation(m, iterations=6, structure=np.ones((1, 3, 3)))

def main(shot, start, end, masks):
    f0 = round(start * FPS)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{start}", "-i", str(ROOT / "marines-fixing-bugs.webm"),
                          "-t", f"{end - start}", "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True, check=True).stdout
    g = np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.float32)
    hm = heroes(masks, f0, len(g))
    dets = []
    for i, fr in enumerate(g):
        keep = (~hm[i]).astype(np.float32)  # estimate the fog from non-hero pixels only
        fog = ndi.gaussian_filter(fr * keep, 12) / np.maximum(ndi.gaussian_filter(keep, 12), 1e-3)
        dark = (fog - fr > DARK) & ~hm[i]
        dark = ndi.binary_opening(dark, iterations=1)
        lab, n = ndi.label(dark)
        out = []
        for sl in ndi.find_objects(lab):
            h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
            if not (MIN_H <= h <= MAX_H) or w > h * 1.1 or w < 4:
                continue
            if sl[0].stop >= H - 2 and sl[0].start < 20:  # full-height column = pillar
                continue
            top = sl[0].start
            row = lab[top:top + max(2, h // 8), sl[1]]
            xs = np.nonzero(row)[1]
            out.append((sl[1].start + xs.mean(), top, h))
        dets.append(out)
    tracks, live = [], []
    for i, out in enumerate(dets):
        used = set()
        nxt = []
        for t in live:
            x, y, h = t["pts"][-1][1:]
            best = min(((abs(d[0] - x) + abs(d[1] - y), j) for j, d in enumerate(out) if j not in used), default=None)
            if best and best[0] < LINK:
                used.add(best[1]); t["pts"].append([i, *out[best[1]]]); nxt.append(t)
            else:
                tracks.append(t)
        for j, d in enumerate(out):
            if j not in used:
                nxt.append({"pts": [[i, *d]]})
        live = nxt
    tracks += live
    res = []
    for t in tracks:
        if len(t["pts"]) < MIN_LEN:
            continue
        p = np.array(t["pts"], float)
        keys = [[round((f0 + q[0]) / FPS, 3), round(q[1] * 4), round(q[2] * 4), round(q[3] * 4)] for q in p[::3]]
        res.append({"note": "auto: fog figure", "auto": True, "keys": keys})
    (ROOT / f"data/detected_{shot}.json").write_text(json.dumps(res, indent=1))
    print(shot, len(res), "candidate tracks")

main(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4].split(","))
