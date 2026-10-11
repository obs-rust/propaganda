# /// script
# dependencies = ["opencv-contrib-python-headless==4.10.0.84", "numpy<2.3"]
# ///
"""Track seeded enemies inside each shot and write data/tracks.json.

Each enemy is seeded on a clear frame (seed_time) and tracked with CSRT both
backward to the shot start and forward to the shot end. A track ends early when
the tracker fails or the box gets too small to read (enemy lost in the fog).
Output anchors are in source pixels: x = box centre, y = box top.
"""
import json, subprocess, sys, pathlib
import cv2, numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
W, H = 1920, 960
MIN_H = 45  # boxes shorter than this are unreadable silhouettes

def frames(video, start, end):
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start}", "-i", str(ROOT / video), "-t", f"{end - start}",
           "-vf", f"scale={W}:{H},eq=brightness=0.08:contrast=1.6", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)

def run(fr, i0, box, step):
    t = cv2.TrackerCSRT_create()
    t.init(fr[i0], tuple(box))
    out = {i0: box}
    i = i0 + step
    while 0 <= i < len(fr):
        ok, b = t.update(fr[i])
        if not ok or b[3] < MIN_H:
            break
        out[i] = [int(v) for v in b]
        i += step
    return out

def main():
    seeds = json.loads((ROOT / "data/pilot_seeds.json").read_text())
    fps = 30000 / 1001
    scale = 2  # tracking space -> source pixels
    result = {"video": seeds["video"], "fps": fps, "size": [W * scale, H * scale], "shots": []}
    for shot in seeds["shots"]:
        fr = frames(seeds["video"], shot["start"], shot["end"])
        f0 = round(shot["start"] * fps)
        i0 = min(len(fr) - 1, round((shot["seed_time"] - shot["start"]) * fps))
        tracks = []
        for e in shot["enemies"]:
            pts = run(fr, i0, e["box"], -1) | run(fr, i0, e["box"], +1)
            keys = sorted(pts)
            tracks.append({"label_id": e["label_id"], "points": [
                [f0 + i, (pts[i][0] + pts[i][2] / 2) * scale, pts[i][1] * scale, pts[i][3] * scale] for i in keys]})
            print(f"{shot['name']} id={e['label_id']}: frames {f0+keys[0]}..{f0+keys[-1]}", file=sys.stderr)
        result["shots"].append({"name": shot["name"], "first_frame": f0, "last_frame": f0 + len(fr) - 1,
                                "title": shot.get("title"), "tracks": tracks})
    (ROOT / "data/tracks.json").write_text(json.dumps(result, indent=1) + "\n")

main()
