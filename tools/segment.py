"""Segment heroes and enemies through a shot with SAM2 (video predictor).

Each object gets clicks picked by eye: [time_s, x, y] (positive) or
[time_s, x, y, 0] (negative, e.g. on fog) in 1920x960 work pixels. SAM2 follows the silhouette through every frame of the
shot. Writes data/masks/<shot>.npz with, per object id, a (frames, 480, 960)
bool stack at half work resolution, plus the first frame number.

Run with the SAM2 environment's python:  <venv>/bin/python tools/segment.py SHOT_NAME
Objects come from data/segments.json.
"""
import json, pathlib, subprocess, sys, tempfile
import numpy as np, torch
from sam2.build_sam import build_sam2_video_predictor_hf

ROOT = pathlib.Path(__file__).resolve().parent.parent
FPS = 30000 / 1001
MW, MH = 960, 480  # mask resolution (half work size)
MODEL = "facebook/sam2.1-hiera-base-plus"

def main(name):
    cfg = json.loads((ROOT / "data/segments.json").read_text())
    shot = next(s for s in cfg["shots"] if s["name"] == name)
    f0, f1 = round(shot["start"] * FPS), round(shot["end"] * FPS) - 1
    with tempfile.TemporaryDirectory() as tmp:
        # SAM2 reads a folder of JPEGs named by index
        subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{f0 / FPS:.4f}", "-i", str(ROOT / cfg["video"]),
                        "-frames:v", str(f1 - f0 + 1), "-vf", f"scale={MW}:{MH}", "-q:v", "2",
                        "-start_number", "0", f"{tmp}/%05d.jpg"], check=True)
        pred = build_sam2_video_predictor_hf(MODEL, device="cuda")
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            state = pred.init_state(tmp, offload_video_to_cpu=True, async_loading_frames=True)
            ids = []
            for oid, obj in enumerate(shot["objects"], 1):
                ids.append(obj["id"])
                by_frame = {}  # all clicks on one frame go in one call (a new call replaces them)
                for c in obj["clicks"]:
                    t, x, y, pos = (*c, 1) if len(c) == 3 else c
                    fi = min(max(round(t * FPS) - f0, 0), f1 - f0)
                    by_frame.setdefault(fi, []).append((x / 2, y / 2, pos))
                for fi, pts in by_frame.items():
                    pred.add_new_points_or_box(state, frame_idx=fi, obj_id=oid,
                                               points=np.array([q[:2] for q in pts], np.float32),
                                               labels=np.array([q[2] for q in pts], np.int32))
            n = f1 - f0 + 1
            out = {i: np.zeros((n, MH, MW), bool) for i in ids}
            for reverse in (False, True):  # propagate both ways from the clicks
                for fi, oids, logits in pred.propagate_in_video(state, reverse=reverse):
                    for k, oid in enumerate(oids):
                        out[ids[oid - 1]][fi] |= (logits[k, 0] > 0).cpu().numpy()
    dst = ROOT / "data/masks"
    dst.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(dst / f"{name}.npz", first_frame=f0, **{k: np.packbits(v, axis=-1) for k, v in out.items()})
    print(name, "frames", f0, f1, "objects", len(ids), file=sys.stderr)

main(sys.argv[1])
