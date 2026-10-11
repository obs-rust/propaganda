"""Find horde members automatically with OWLv2 (open-vocabulary detector).

Frames are contrast-boosted (CLAHE) so figures hidden in the fog stand out,
split into two overlapping crops so far figures stay large, and queried for
humanoid / horned creature silhouettes. Boxes mostly covered by a hero mask
(SAM2, data/masks) are heroes and dropped; huge boxes are dropped. Boxes are
linked across frames into tracks; tracks become candidate enemies in
data/detected_<shot>.json, which tools/assign_labels.py merges with the
hand-placed keyframes (duplicates collapse onto one baddie).

Run with the GPU venv:  <venv>/bin/python tools/detect_owl.py SHOT START END MASK[,MASK]
"""
import json, pathlib, subprocess, sys
import numpy as np, cv2, torch
from PIL import Image
from transformers import Owlv2Processor, Owlv2ForObjectDetection

ROOT = pathlib.Path(__file__).resolve().parent.parent
FPS = 30000 / 1001
W, H = 1920, 960
STEP = 2              # analyse every 2nd frame
MIN_SCORE = 0.25
HERO_COVER = 0.35     # drop boxes this much covered by a hero mask
MAX_H, MAX_W = 0.65 * H, 0.30 * W
LINK_IOU = 0.2
MIN_HITS = 4          # detections per track (x STEP frames)
Q = [["a silhouette of a person in fog", "a horned creature", "a humanoid monster", "a running figure"]]

def hero_masks(names, f0, n):
    m = np.zeros((n, 480, 960), bool)
    for name in names:
        z = np.load(ROOT / "data/masks" / f"{name}.npz")
        m0 = int(z["first_frame"])
        for k in z.files:
            if k.startswith("hero"):
                hm = np.unpackbits(z[k], axis=-1)[..., :960].astype(bool)
                lo, hi = max(f0, m0), min(f0 + n - 1, m0 + len(hm) - 1)
                if lo <= hi:
                    m[lo - f0:hi - f0 + 1] |= hm[lo - m0:hi - m0 + 1]
    return m

def iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    i = max(0, x1 - x0) * max(0, y1 - y0)
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i + 1e-6)

def main(shot, start, end, masks):
    proc = Owlv2Processor.from_pretrained("google/owlv2-base-patch16-ensemble")
    model = Owlv2ForObjectDetection.from_pretrained("google/owlv2-base-patch16-ensemble").cuda().eval()
    f0 = round(start * FPS)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{start}", "-i", str(ROOT / "marines-fixing-bugs.webm"),
                          "-t", f"{end - start}", "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
    hm = hero_masks(masks, f0, len(frames))
    clahe = cv2.createCLAHE(3.0, (8, 8))
    dets = []
    for i in range(0, len(frames), STEP):
        lab = cv2.cvtColor(frames[i], cv2.COLOR_BGR2LAB)
        lab[..., 0] = clahe.apply(lab[..., 0])
        e = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
        boxes = []
        for x_off in (0, 840):
            img = Image.fromarray(e[:, x_off:x_off + 1080])
            inp = proc(text=Q, images=img, return_tensors="pt").to("cuda")
            with torch.no_grad():
                o = model(**inp)
            r = proc.post_process_object_detection(o, threshold=MIN_SCORE, target_sizes=torch.tensor([[1080, 1080]]).cuda())[0]
            for b, sc in zip(r["boxes"].cpu().numpy(), r["scores"].cpu().numpy()):
                x0, y0, x1, y1 = b
                x0, x1 = x0 + x_off, x1 + x_off
                y1 = min(y1, H)
                bh, bw = y1 - y0, x1 - x0
                if bh > MAX_H or bw > MAX_W or bh < 30 or bw > bh * 1.2:
                    continue
                cov = hm[i, int(max(y0, 0)) // 2:int(y1) // 2, int(max(x0, 0)) // 2:int(x1) // 2]
                if cov.size == 0 or cov.mean() > HERO_COVER:
                    continue
                boxes.append([x0, y0, x1, y1, float(sc)])
        boxes.sort(key=lambda b: -b[4])
        kept = []
        for b in boxes:  # NMS across queries and crops
            if all(iou(b, k) < 0.4 for k in kept):
                kept.append(b)
        dets.append((i, kept))
    tracks, live = [], []
    for i, kept in dets:
        used, nxt = set(), []
        for t in live:
            last = t[-1][1]
            cand = [(iou(last, b), j) for j, b in enumerate(kept) if j not in used]
            best = max(cand, default=(0, -1))
            if best[0] >= LINK_IOU:
                used.add(best[1]); t.append((i, kept[best[1]])); nxt.append(t)
            elif i - t[-1][0] <= 2 * STEP:  # tolerate one missed detection
                nxt.append(t)
            else:
                tracks.append(t)
        nxt += [[(i, b)] for j, b in enumerate(kept) if j not in used]
        live = nxt
    tracks += live
    res = []
    for t in tracks:
        if len(t) < MIN_HITS:
            continue
        keys = [[round((f0 + i) / FPS, 3), round((b[0] + b[2]) / 2), round(b[1] + 0.06 * (b[3] - b[1])), round(b[3] - b[1])]
                for i, b in t]
        res.append({"note": f"auto: OWLv2 fog figure (score {np.mean([b[4] for _, b in t]):.2f})", "auto": True,
                    "violence": 1, "keys": keys})
    (ROOT / f"data/detected_{shot}.json").write_text(json.dumps(res, indent=1) + "\n")
    print(shot, len(res), "auto tracks from", sum(len(k) for _, k in dets), "detections")

main(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4].split(","))
