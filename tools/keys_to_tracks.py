# /// script
# dependencies = ["numpy<2.3", "scipy<1.16"]
# ///
"""Turn hand-placed vision keyframes (data/keyframes.json) into per-frame tracks.

Positions and figure heights are interpolated with PCHIP, a smooth cubic that
never overshoots between keys, so labels glide without wobbling past a head.
Writes data/tracks.json in the format tools/render.py reads; the point columns
are [frame, head_x, head_y, figure_height] in source pixels.
"""
import json, pathlib
import numpy as np
from scipy.interpolate import PchipInterpolator, make_smoothing_spline

ROOT = pathlib.Path(__file__).resolve().parent.parent
FPS = 30000 / 1001
SRC = (3840, 1920)

LAM = 40.0      # smoothing-spline stiffness (frames^3); higher = smoother, lazier
EMA_TAU = 3.0   # frames; forward-backward exponential smoothing on top


def smooth_path(fk, v, frs, k=1.0):
    """Smoothing cubic spline through the keys (does not pass through every
    noisy key), evaluated per frame, then a zero-lag exponential pass
    (forward then backward EMA) to remove any remaining wobble."""
    fk, idx = np.unique(fk, return_index=True)
    v = v[idx]
    if len(fk) >= 5:
        y = make_smoothing_spline(fk, v, lam=LAM * k)(frs)
    elif len(fk) >= 2:
        y = PchipInterpolator(fk, v)(frs)
    else:
        y = np.full(len(frs), v[0], float)
    y = np.where(frs < fk[0], v[0], np.where(frs > fk[-1], y[np.searchsorted(frs, fk[-1])] if fk[-1] <= frs[-1] else y, y))
    a = 1 - np.exp(-1 / (EMA_TAU * k))
    for seq in (range(1, len(y)), range(len(y) - 2, -1, -1)):
        step = 1 if seq.step == 1 else -1
        for i in seq:
            y[i] = y[i - step] + a * (y[i] - y[i - step])
    return y


def main():
    src = ROOT / "data/keyframes.assigned.json"  # written by tools/assign_labels.py
    k = json.loads((src if src.exists() else ROOT / "data/keyframes.json").read_text())
    s = SRC[0] / k["work_size"][0]
    shots = []
    for shot in k["shots"]:
        f0, f1 = round(shot["start"] * FPS), round(shot["end"] * FPS) - 1
        ox, oy = shot.get("crop_origin", k["crop_origin"])
        tracks = []
        for e in shot["enemies"]:
            if "axis" in e:  # two-point anchor: label lies along the segment p1->p2
                ax = np.array(e["axis"], float)  # [t, x1, y1, x2, y2] work px
                fk = ax[:, 0] * FPS
                frs = np.arange(max(int(np.ceil(fk[0])), f0), min(int(np.floor(fk[-1])), f1) + 1)
                c = [smooth_path(fk, (ax[:, j] + (ox if j % 2 else oy)) * s, frs) for j in range(1, 5)]
                mx, my = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
                ang = -np.degrees(np.arctan2(c[3] - c[1], c[2] - c[0]))  # PIL rotate: counter-clockwise
                ln = np.hypot(c[2] - c[0], c[3] - c[1])
                tracks.append({"label_id": e["label_id"], "fade_in": e.get("fade_in", shot.get("fade_in", 8)),
                               "fade_out": e.get("fade_out", shot.get("fade_out", 8)),
                               "axis_angle": ang.round(2).tolist(), "axis_len": ln.round(1).tolist(),
                               "points": np.column_stack([frs, mx, my, np.zeros(len(frs))]).round(1).tolist()})
                continue
            key = np.array(e["keys"], float)
            fk = key[:, 0] * FPS
            # either hold to the cut (PCHIP extrapolates the last few frames) or end on the last key
            last = f1 if shot.get("hold_to_cut") else min(int(np.floor(fk[-1])), f1)
            frs = np.arange(max(int(np.ceil(fk[0])), f0), last + 1)
            # Stable-anchor policy: keys mark a rigid, slow part (gun muzzle, headlight, neck),
            # and "offset" [dx, dy] (fractions of frame width/height) places the label from it.
            # With an offset the label's bottom sits exactly at anchor+offset (no head-height lift).
            dx, dy = e.get("offset", (0, 0))
            xs_k = (key[:, 1] + ox + dx * k["work_size"][0]) * s
            ys_k = (key[:, 2] + oy + dy * k["work_size"][1]) * s
            if "offset" in e:
                ys_k = ys_k + 0.06 * key[:, 3] * s  # cancel render.py's head lift
            cols = [smooth_path(fk, v, frs, e.get("smooth", 1.0)) for v in (xs_k, ys_k, key[:, 3] * s)]
            tracks.append({"label_id": e["label_id"], "fade_in": e.get("fade_in", shot.get("fade_in", 8)),
                           "fade_out": e.get("fade_out", shot.get("fade_out", 8)), "angle": e.get("angle", 0.0),
                           "points": np.column_stack([frs, *cols]).round(1).tolist()})
        shots.append({"name": shot["name"], "first_frame": f0, "last_frame": f1, "title": shot.get("title"),
                      "labels_from": shot.get("labels_from", shot["start"]), "hero_masks": shot.get("hero_masks"),
                      "tracks": tracks})
    out = {"video": k["video"], "fps": FPS, "size": list(SRC), "source": "keyframes", "shots": shots}
    (ROOT / "data/tracks.json").write_text(json.dumps(out, indent=1) + "\n")

main()
