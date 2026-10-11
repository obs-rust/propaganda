# /// script
# dependencies = ["pillow==11.0.0", "numpy<2.3", "scipy<1.16"]
# ///
"""Render label overlays from data/tracks.json + data/labels.json.

Writes out/overlay.webm (full-length VP9 RGBA, same size/fps/duration as the
source) and out/overlay.mov (ProRes 4444), plus out/preview.mp4 (composite of
the labelled window). The source video is only read.

Rules: labels exist only inside their shot (cleared on the cut), fade in/out
over FADE frames, follow a cubic B-spline fit of the tracked anchor, grow a
little as the enemy gets closer (bigger on screen), and ease apart when they
would overlap.
"""
import json, os, subprocess, pathlib, sys
import numpy as np
from scipy.interpolate import LSQUnivariateSpline
from scipy.optimize import minimize
from scipy.ndimage import gaussian_filter1d
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / os.environ.get("OUT", "out")
FONT = os.environ.get("FONT", str(ROOT / "fonts/Antonio[wght].ttf"))
FONT_WGHT = int(os.environ.get("FONT_WGHT", "600"))  # used when the font is variable
FONT_SCALE = float(os.environ.get("FONT_SCALE", "1"))
PREVIEW_ONLY = os.environ.get("PREVIEW_ONLY") == "1"  # 720p preview only: overlay drawn at 1280 wide, much faster
AVOID_OVERLAP = os.environ.get("AVOID_OVERLAP") == "1"
# Hero occlusion: none | clip (heroes cut the text) | avoid (labels slide off heroes) | blend (avoid, then clip the rest)
OCCLUDE = os.environ.get("OCCLUDE", "fade")  # fade: whole label fades behind heroes (never cuts letters)
ONLY = os.environ.get("ONLY")  # render just this shot (pilots)
AVOID_REACH, AVOID_SIGMA = 0.22, 7  # max sideways slide (fraction of width), smoothing in frames  # solve label offsets so none touch (labels drift off their enemy)
FADE = 8  # frames, title fade
KNOT_EVERY = 12  # spline knot spacing in frames: larger = smoother, less responsive
SIZE_RANGE = (0.85, 1.3)  # label scale for a far .. near enemy
FIG_RANGE = (190, 760)  # figure height in source px mapped onto SIZE_RANGE (vision keyframes)
W_OVL, W_ANCHOR, W_SMOOTH = 2000.0, 0.02, 40.0  # layout solver: overlap, stay-on-enemy, low-acceleration weights
PATH_SIGMA = 4  # frames: Gaussian blur of each label's final on-screen path
GAP = 18
AXIS_FILL = 0.9  # two-point anchors: text spans this fraction of the segment
# Phone legibility: on a 6.1" iPhone in landscape a 2:1 video is ~2.55" (65 mm) tall.
# At scale 1.0 a label's cap height is ~2% of frame height = ~1.3 mm, below the
# ~2.5 mm a caption needs at arm's length (Apple's 11 pt minimum ~ 2.3 mm caps).
# 2.0x puts the mid-size label at ~2.6 mm caps.
LABEL_SCALE = float(os.environ.get("LABEL_SCALE", "2.0"))
HERO_FADE_AT = 0.3  # fraction of the label box covered by a hero before it fades out
VIS_TAU = 2.5  # frames: fade speed for occlusion / de-stacking
DRAW_TAU = 4.0  # frames: zero-lag exponential smoothing of the drawn label position/size
MIN_FRAMES = 15  # labels shorter than 0.5 s are suspect (detection aliasing): dropped
EDGE = 40  # px: labels never go closer than this to the frame edge

def font(px):
    f = ImageFont.truetype(FONT, int(px * FONT_SCALE))
    try:
        axes = f.get_variation_axes()
        f.set_variation_by_axes([FONT_WGHT if ax.get("name", b"") in (b"Weight", "Weight") else ax["default"] for ax in axes])
    except Exception:
        pass  # static font
    return f

def spline(frs, v):
    """Least-squares cubic B-spline through noisy per-frame samples."""
    n = len(frs)
    knots = frs[KNOT_EVERY:-KNOT_EVERY:KNOT_EVERY] if n > 3 * KNOT_EVERY else []
    f = LSQUnivariateSpline(frs, v, knots, k=3 if n > 4 else 1)
    return f(np.arange(frs[0], frs[-1] + 1))

# CSS-style text-shadow stack: (x, y, blur, (r, g, b, a)), first entry paints on top,
# exactly like `text-shadow: a, b, c`. Values are px at a 46px font and scale with size.
# Warm off-white keyed to the fog (hue ~45 deg, about 12% sat, 95% value): reads as
# light from the scene instead of a sticker on top of it.
TEXT_RGB = (242, 234, 213)  # #F2EAD5

SHADOWS = [
    (0, 0, 2, (0, 0, 0, 0.95)),
    (2, 2, 0, (0, 0, 0, 0.85)),
    (3, 4, 8, (0, 0, 0, 0.75)),
    (0, 0, 18, (0, 0, 0, 0.6)),
    (0, 0, 36, (0, 0, 0, 0.30)),
]

def load_heroes(shot, a, z):
    """Union of all hero_* masks for this shot, indexed by frame - a; None if the shot has none."""
    names = shot.get("hero_masks")
    if not names:
        return None
    full = np.zeros((z - a + 1, 480, 960), bool)
    for name in [names] if isinstance(names, str) else names:
        zf = np.load(ROOT / "data/masks" / f"{name}.npz")
        m0 = int(zf["first_frame"])
        for k in zf.files:
            if not k.startswith("hero"):
                continue
            m = np.unpackbits(zf[k], axis=-1)[..., :960].astype(bool)
            lo, hi = max(a, m0), min(z, m0 + len(m) - 1)
            if lo <= hi:
                full[lo - a:hi - a + 1] |= m[lo - m0:hi - m0 + 1]
    return full


def avoid_heroes(layout, heroes, a, W, H, label_font):
    """Slide each label sideways (smoothly) to the nearest spot that keeps it off the heroes."""
    mh, mw = heroes.shape[1:]
    sx, sy = mw / W, mh / H
    reach = AVOID_REACH * W
    shifts = np.linspace(-reach, reach, 45)
    for text, frames in layout.items():
        ks = sorted(frames)
        if not ks:
            continue
        best = []
        for fr in ks:
            cx, base, px, lift = frames[fr]
            b = tag(None, text, label_font(px), cx, base - lift, 1)
            y0, y1 = int(max(b[1] * sy, 0)), int(min(b[3] * sy + 1, mh))
            m = heroes[fr - a]
            cost = []
            for d in shifts:
                x0, x1 = int(max((b[0] + d) * sx, 0)), int(min((b[2] + d) * sx + 1, mw))
                cover = m[y0:y1, x0:x1].mean() if x1 > x0 and y1 > y0 else 1.0
                off = (b[0] + d < 24) or (b[2] + d > W - 24)
                cost.append(cover * 4 + abs(d) / reach * 0.6 + off * 10)
            best.append(shifts[int(np.argmin(cost))])
        sm = gaussian_filter1d(np.array(best, float), AVOID_SIGMA, mode="nearest")
        for fr, d in zip(ks, sm):
            frames[fr][0] += d


def tag(img, text, f, cx, bottom, alpha, accent=None, line_alpha=None, prefix_alpha=None, angle=0.0):
    """Draw text centred on cx with its baseline box ending at bottom; return its box.

    With img=None only measures. Shadows are blurred copies of the glyph mask,
    composited back-to-front like a browser does.
    """
    _md = ImageDraw.Draw(Image.new("L", (1, 1)))
    ml = dict(spacing=round(f.size * 0.08), align="center")  # "\n" stacks lines, centred
    l, t, r, b = (int(round(v)) for v in _md.multiline_textbbox((0, 0), text, font=f, **ml))
    w, h = r - l, b - t
    x0, y0 = int(cx - w / 2), int(bottom - h)
    box = (x0, y0, x0 + w, y0 + h)
    if img is None or alpha <= 0:
        return box
    k = f.size / 46
    pad = int(max(abs(sx) + bl for sx, sy, bl, _ in SHADOWS) * k * 2) + 4
    mask = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    if prefix_alpha:  # word-by-word on one line: [(prefix, alpha)], laid out in the FULL line's place
        for pre, pa in prefix_alpha:
            if pa > 0:
                m1 = Image.new("L", mask.size, 0)
                ImageDraw.Draw(m1).text((pad - l, pad - t), pre, font=f, fill=round(255 * pa))
                mask = ImageChops.lighter(mask, m1)
    elif line_alpha is None:
        ImageDraw.Draw(mask).multiline_text((pad - l, pad - t), text, font=f, fill=255, **ml)
    else:  # per-line reveal: draw each line alone at its place in the full block
        lines = text.split("\n")
        widths = [_md.textlength(ln, font=f) for ln in lines]
        for i, la in enumerate(line_alpha):
            if la <= 0:
                continue
            solo = "\n".join(ln if j == i else "" for j, ln in enumerate(lines))
            m1 = Image.new("L", mask.size, 0)
            ImageDraw.Draw(m1).multiline_text((pad - l + (max(widths) - widths[i]) / 2, pad - t), solo,
                                              font=f, fill=round(255 * la), spacing=ml["spacing"])
            mask = ImageChops.lighter(mask, m1)
    layer = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    for sx, sy, bl, (cr, cg, cb, ca) in reversed(SHADOWS):
        m = mask.filter(ImageFilter.GaussianBlur(bl * k / 2)) if bl else mask
        m = ImageChops.offset(m, round(sx * k), round(sy * k)).point(lambda v: int(v * ca * alpha))
        sh = Image.new("RGBA", mask.size, (cr, cg, cb, 0))
        sh.putalpha(m)
        layer = Image.alpha_composite(layer, sh)
    fg = Image.new("RGBA", mask.size, (*TEXT_RGB, 0))
    fg.putalpha(mask.point(lambda v: int(v * alpha)))
    layer = Image.alpha_composite(layer, fg)
    if angle:  # align the label with an object's long axis (degrees, counter-clockwise)
        cw, ch = layer.size
        layer = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
        x0 -= (layer.size[0] - cw) // 2
        y0 -= (layer.size[1] - ch) // 2
    img.alpha_composite(layer, (max(x0 - pad, 0), max(y0 - pad, 0)))
    return box

def main():
    tr = json.loads((ROOT / "data/tracks.json").read_text())
    labels = {r["id"]: r for r in json.loads((ROOT / "data/labels.json").read_text())}
    W, H = tr["size"]
    fps = tr["fps"]
    OUT.mkdir(exist_ok=True)
    fonts = {}
    label_font = lambda px: fonts.setdefault(px, font(px))
    k_out = 1280 / W if PREVIEW_ONLY else 1  # draw scale for the overlay segments
    f_title = font(round(120 * LABEL_SCALE * k_out))
    title_font = lambda sc: fonts.setdefault(("t", sc), font(round(120 * LABEL_SCALE * k_out * sc)))
    accent = (255, 70, 40)
    segs = []
    for shot in tr["shots"]:
        if ONLY and shot["name"] != ONLY:
            continue
        a, z = shot["first_frame"], shot["last_frame"]
        heroes = load_heroes(shot, a, z)  # (frames, 480, 960) bool or None
        lab_from = round(shot.get("labels_from", a / fps) * fps)
        tracks = []
        fades = {}
        angles = {}
        axes = {}  # label text -> (fade-in frames, fade-out frames); a kill uses a short fade-out
        for t in shot["tracks"]:
            p = np.array(t["points"], float)
            if len(p) < MIN_FRAMES:  # too brief to read: drop, it would only flicker
                continue
            frs = p[:, 0].astype(int)
            fades[labels[t["label_id"]]["short"]] = (t.get("fade_in", 8), t.get("fade_out", 8))
            angles[labels[t["label_id"]]["short"]] = t.get("angle", 0.0)
            if "axis_len" in t:  # two-point anchor: per-frame angle and the length the text should span
                axes[labels[t["label_id"]]["short"]] = (frs[0], np.array(t["axis_angle"]), np.array(t["axis_len"]))
            if tr.get("source") == "keyframes":  # already smooth: interpolated from vision keys
                tracks.append((labels[t["label_id"]]["short"], frs, p[:, 1], p[:, 2] - 0.06 * p[:, 3], p[:, 3]))
            else:  # raw tracker output: fit a spline; box height is too noisy to size by
                tracks.append((labels[t["label_id"]]["short"], np.arange(frs[0], frs[-1] + 1),
                               spline(frs, p[:, 1]), spline(frs, p[:, 2]) + 20, np.full(frs[-1] - frs[0] + 1, FIG_RANGE[0])))
        # Smooth each enemy path first, so layout works on the motion that is drawn.
        tracks = [(t[0], t[1], gaussian_filter1d(t[2], PATH_SIGMA, mode="nearest"),
                   gaussian_filter1d(t[3], PATH_SIGMA, mode="nearest"), t[4]) for t in tracks]
        title = shot.get("title")
        t0 = t1 = None
        if title:
            t0, t1 = round(title["from"] * fps), round(title["to"] * fps)
        frames_of = {}
        geo = {}  # (text, fr) -> (cx, base, px)
        for text, frs, xs, ys, hs in tracks:
            fs = [f for f in range(max(frs[0], lab_from, a), min(frs[-1], z) + 1)]
            frames_of[text] = fs
            for fr in fs:
                i = fr - frs[0]
                k = np.clip((hs[i] - FIG_RANGE[0]) / (FIG_RANGE[1] - FIG_RANGE[0]), 0, 1)
                px = round(56 * LABEL_SCALE * (SIZE_RANGE[0] + k * (SIZE_RANGE[1] - SIZE_RANGE[0])))
                if text in axes:  # size the text to span AXIS_FILL of the anchor segment
                    px = max(12, round(100 * AXIS_FILL * axes[text][2][i] / label_font(100).getlength(text)))
                box = tag(None, text, label_font(px), xs[i], ys[i], 1)
                half = (box[2] - box[0]) / 2 + 24  # keep the whole label on screen
                base = ys[i] + max(0, EDGE - box[1])  # heads at the top of frame: label sits just inside
                geo[text, fr] = (min(max(xs[i], half), W - half), base, px)
        # Solve every label's vertical offset over the whole shot at once:
        # minimise overlap (heavily), distance from its enemy, and acceleration.
        names = list(frames_of)
        n, nf = len(names), z - a + 1
        act = np.zeros((n, nf), bool)
        cx_, y0, hw, hh = (np.zeros((n, nf)) for _ in range(4))
        for i, t in enumerate(names):
            for fr in frames_of[t]:
                cx, base, px = geo[t, fr]
                bx = tag(None, t, label_font(px), cx, base, 1)
                j = fr - a
                act[i, j] = True
                cx_[i, j], y0[i, j] = cx, (bx[1] + bx[3]) / 2
                hw[i, j], hh[i, j] = (bx[2] - bx[0]) / 2, (bx[3] - bx[1]) / 2
        pairs = [(i, k) for i in range(n) for k in range(i)]
        # a pair only interacts on frames where their x extents come within GAP
        xo = {(i, k): act[i] & act[k] & (np.abs(cx_[i] - cx_[k]) < hw[i] + hw[k] + GAP) for i, k in pairs}
        sep = {(i, k): hh[i] + hh[k] + GAP + 2 for i, k in pairs}
        if title:
            tb = tag(None, title["text"], f_title, W / 2, H * title.get("y", 0.2), 1)
            tact = np.array([t0 <= fr <= t1 for fr in range(a, z + 1)])
            txo = act & tact & (np.abs(cx_ - W / 2) < hw + (tb[2] - tb[0]) / 2 + GAP)
            tcy, tsep = (tb[1] + tb[3]) / 2, hh + (tb[3] - tb[1]) / 2 + GAP + 2

        def cost(v):
            d = v.reshape(n, nf) * act  # downward shift of each label centre
            y = y0 + d
            c = W_ANCHOR * (d ** 2).sum()
            g = 2 * W_ANCHOR * d
            for i, k in pairs:
                m = xo[i, k]
                if not m.any():
                    continue
                dy = y[i] - y[k]
                sgn = np.where(dy >= 0, 1.0, -1.0)
                viol = np.where(m, np.maximum(sep[i, k] - np.abs(dy), 0), 0)
                c += W_OVL * (viol ** 2).sum()
                g[i] -= 2 * W_OVL * viol * sgn
                g[k] += 2 * W_OVL * viol * sgn
            if title:
                dy = y - tcy
                sgn = np.where(dy >= 0, 1.0, -1.0)
                viol = np.where(txo, np.maximum(tsep - np.abs(dy), 0), 0)
                c += W_OVL * (viol ** 2).sum()
                g -= 2 * W_OVL * viol * sgn
            over = np.where(act, EDGE + hh - y, 0).clip(0)  # stay below the top edge
            c += W_OVL * (over ** 2).sum()
            g -= 2 * W_OVL * over
            for i in range(n):  # acceleration over each label's active span
                js = np.flatnonzero(act[i])
                if len(js) < 3:
                    continue
                s_ = d[i, js[0]:js[-1] + 1]
                acc = s_[2:] - 2 * s_[1:-1] + s_[:-2]
                c += W_SMOOTH * (acc ** 2).sum()
                ga = 2 * W_SMOOTH * acc
                gg = np.zeros_like(s_)
                gg[2:] += ga
                gg[1:-1] -= 2 * ga
                gg[:-2] += ga
                g[i, js[0]:js[-1] + 1] += gg
            return c, (g * act).ravel()

        if AVOID_OVERLAP:
            res = minimize(cost, np.zeros(n * nf), jac=True, method="L-BFGS-B", options={"maxiter": 5000})
            shift = res.x.reshape(n, nf)
            print(f"layout solved: cost {res.fun:.0f} after {res.nit} iterations", file=sys.stderr)
        else:  # labels ride exactly on their (smoothed) enemy; overlaps are allowed
            shift = np.zeros((n, nf))
        lift = {t: -shift[i, [fr - a for fr in frames_of[t]]] for i, t in enumerate(names)}
        layout = {t: {fr: [*geo[t, fr][:2], geo[t, fr][2], lift[t][fr - fs[0]]] for fr in fs} for t, fs in frames_of.items()}
        for t_, fr_map in layout.items():  # final zero-lag exponential pass on what is drawn (after edge clamps)
            ks = sorted(fr_map)
            if len(ks) < 3:
                continue
            xs_ = np.array([fr_map[f][0] for f in ks], float)
            tops = np.array([fr_map[f][1] - fr_map[f][3] for f in ks], float)
            pxs = np.array([fr_map[f][2] for f in ks], float)
            a_ = 1 - np.exp(-1 / DRAW_TAU)
            for arr in (xs_, tops, pxs):
                for i in range(1, len(arr)):
                    arr[i] = arr[i - 1] + a_ * (arr[i] - arr[i - 1])
                for i in range(len(arr) - 2, -1, -1):
                    arr[i] = arr[i + 1] + a_ * (arr[i] - arr[i + 1])
            for f, x_, tp, px_ in zip(ks, xs_, tops, pxs):
                fr_map[f][0], fr_map[f][3], fr_map[f][2] = x_, fr_map[f][1] - tp, px_
        if heroes is not None and OCCLUDE in ("avoid", "blend"):
            avoid_heroes(layout, heroes, a, W, H, label_font)
        bad = []
        for fr in range(a, z + 1):
            bx = [tag(None, title["text"], f_title, W / 2, H * title.get("y", 0.2), 1)] if title and t0 <= fr <= t1 else []
            names = ["TITLE"] * len(bx)
            for t, fs in frames_of.items():
                if (t, fr) in geo:
                    cx, base, px = geo[t, fr]
                    bx.append(tag(None, t, label_font(px), cx, base - lift[t][fr - fs[0]], 1)); names.append(t)
            bad += [(fr, names[i], names[k]) for i in range(len(bx)) for k in range(i) if
                    not (bx[i][2] < bx[k][0] or bx[i][0] > bx[k][2] or bx[i][3] < bx[k][1] or bx[i][1] > bx[k][3])]
        print(f"touching label pairs (no gap) in {len({b[0] for b in bad})} of {z - a + 1} frames: {sorted({b[1:] for b in bad})}", file=sys.stderr)
        layout = {t: {f: [v[0], v[1], v[2], v[3]] for f, v in d.items()} for t, d in layout.items()}
        (OUT / f"layout_{shot['name']}.json").write_text(json.dumps({t: {str(f): v for f, v in fs.items()} for t, fs in layout.items()}))
        prio = {t[0]: next((l["priority"] for l in labels.values() if l["short"] == t[0]), 999) for t in tracks}
        vis = {t: {} for t in layout}
        for fr in range(a, z + 1):
            kept = []
            for t in sorted(layout, key=lambda t: prio[t]):  # worst bug wins a contested spot
                if fr not in layout[t]:
                    continue
                cx, base, px, lift = layout[t][fr]
                b = tag(None, t, label_font(max(8, round(px))), cx, base - lift, 1)
                target = 1.0
                if heroes is not None and OCCLUDE == "fade":
                    mh, mw = heroes.shape[1:]
                    sub = heroes[fr - a, int(max(b[1], 0) * mh / H):int(min(b[3], H) * mh / H) + 1,
                                 int(max(b[0], 0) * mw / W):int(min(b[2], W) * mw / W) + 1]
                    if sub.size and sub.mean() > HERO_FADE_AT:
                        target = 0.0
                if target and any(not (b[2] + 8 < c[0] or b[0] - 8 > c[2] or b[3] + 4 < c[1] or b[1] - 4 > c[3]) for c in kept):
                    target = 0.0
                if target:
                    kept.append(b)
                vis[t][fr] = target
        k_ = 1 - np.exp(-1 / VIS_TAU)
        for t, m in vis.items():  # smooth on/off so labels fade instead of popping
            ks = sorted(m)
            v = 1.0 if not ks else m[ks[0]]
            for f in ks:
                v += k_ * (m[f] - v)
                m[f] = v
        seg = OUT / f"seg_{shot['name']}.mov"
        OW, OH = round(W * k_out), round(H * k_out)
        enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{OW}x{OH}",
                                "-r", "30000/1001", "-i", "-", "-c:v", "qtrle", str(seg)], stdin=subprocess.PIPE)
        for fr in range(a, z + 1):
            img = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
            if title and t0 <= fr <= t1:
                # the title is on at full strength from its first frame (the cut) unless it asks to fade in
                fade_in = (fr - t0) / FADE if title.get("fade_in", True) else 1
                la = None
                if title.get("reveal"):  # [[seconds, line_count], ...]: lines appear in beats
                    la = [0.0] * len(title["text"].split("\n"))
                    for ts, nl in title["reveal"]:
                        a_ = min(1, max(0, (fr - round(ts * fps)) / FADE))
                        for i in range(nl):
                            la[i] = max(la[i], a_)
                pa = None
                fo = title.get("fade_frames", FADE)
                if title.get("beats"):  # [[seconds, prefix], ...]: words land on beats, centred as the full line
                    pa = [(pre, min(1, max(0, (fr - round(ts * fps)) / fo))) for ts, pre in title["beats"]]
                if title.get("fade_in_frames"):  # slow, eased fade (e.g. timed to a breath)
                    fade_in = min(1, (fr - t0) / title["fade_in_frames"])
                    fade_in = fade_in * fade_in * (3 - 2 * fade_in)
                fout = min(1, (t1 - fr) / title.get("fade_out_frames", fo))
                if title.get("fade_frames"):
                    fout = fout * fout * (3 - 2 * fout)
                ft = f_title if "scale" not in title else title_font(title["scale"])
                tag(img, title["text"], ft, OW * title.get("x", 0.5), OH * title.get("y", 0.2),
                    min(1, fade_in if not title.get("beats") else 1, fout), line_alpha=la, prefix_alpha=pa)
            labels_img = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
            for text, frs, xs, ys, hs in tracks:
                if fr not in layout[text]:
                    continue
                cx, base, px, lift = layout[text][fr]
                start = max(frs[0], lab_from)
                fin, fout = fades[text]
                al = min(1, (fr - start + 1) / fin, (frs[-1] - fr + 1) / fout) * vis[text].get(fr, 1.0)
                tag(labels_img, text, label_font(max(8, round(px * k_out))), cx * k_out, (base - lift) * k_out, al,
                    angle=axes[text][1][fr - axes[text][0]] if text in axes else angles.get(text, 0.0))
            if heroes is not None and OCCLUDE in ("clip", "blend"):
                # heroes stand in front: cut the labels out where a hero is, with a soft edge
                m = Image.fromarray((heroes[fr - a] * 255).astype(np.uint8)).resize((OW, OH), Image.BILINEAR)
                m = m.filter(ImageFilter.GaussianBlur(2 * OW / 1280))
                keep = ImageChops.invert(m)
                labels_img.putalpha(ImageChops.multiply(labels_img.getchannel("A"), keep))
            img.alpha_composite(labels_img)
            enc.stdin.write(img.tobytes())
        enc.stdin.close()
        enc.wait()
        segs.append((seg, a / fps))
        print("rendered", shot["name"], a, z, file=sys.stderr)

    src = ROOT / tr["video"]
    if PREVIEW_ONLY:
        shots = [s for s in tr["shots"] if not ONLY or s["name"] == ONLY]
        t_in = min(s["first_frame"] for s in shots) / fps if ONLY else 0
        end = max(s["last_frame"] for s in shots) / fps + (0.05 if ONLY else 0.5)
        segs = [(sg, st - t_in) for sg, st in segs]
        ins, chain, last = ["-ss", f"{t_in}", "-t", f"{end - t_in}", "-i", str(src)], f"[0:v]scale={OW}:{OH}[src];", "src"
        for i, (seg, start) in enumerate(segs, 1):
            ins += ["-itsoffset", f"{start}", "-i", str(seg)]
            chain += f"[{last}][{i}:v]overlay=eof_action=pass:format=auto[v{i}];"
            last = f"v{i}"
        subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", chain + f"[{last}]null[v]",
                        "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "aac",
                        str(OUT / "preview.mp4")], check=True)
        return
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)]))
    inputs, chain, last = [], f"color=c=black@0:s={W}x{H}:r=30000/1001:d={dur},format=rgba[b0]", "b0"
    for i, (seg, start) in enumerate(segs, 1):
        inputs += ["-i", str(seg)]
        chain += f";[{i - 1}:v]setpts=PTS+{start}/TB[s{i}];[{last}][s{i}]overlay=eof_action=pass:format=auto[b{i}]"
        last = f"b{i}"
    base = ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", chain, "-map", f"[{last}]"]
    subprocess.run(base + ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "30", "-deadline", "realtime",
                           "-cpu-used", "8", "-row-mt", "1", "-auto-alt-ref", "0", str(OUT / "overlay.webm")], check=True)
    if "--prores" in sys.argv:  # ~20 min for the full 4K length
        subprocess.run(base + ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", str(OUT / "overlay.mov")], check=True)
    # composite preview through the last labelled shot (source stays untouched)
    end = max(s["last_frame"] for s in tr["shots"]) / fps + 0.5
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-t", f"{end}", "-i", str(src), "-t", f"{end}",
                    "-c:v", "libvpx-vp9", "-i", str(OUT / "overlay.webm"),
                    "-filter_complex", "[0:v][1:v]overlay=format=auto,scale=1920:-2[v]", "-map", "[v]", "-map", "0:a?",
                    "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "aac", str(OUT / "preview.mp4")], check=True)

main()
