# /// script
# dependencies = ["numpy<2.3"]
# ///
"""Give the worst bugs to the most violent, longest-on-screen enemies.

First merges tracks that are the same baddie (paths that overlap in time and
stay within MERGE_FRAC of the figure height, or one picks up within 0.35 s of where
the other ended), so one figure keeps one label for its whole time on screen.
Each enemy then gets a score = violence^2 x min(seconds, 1.5).
violence (1-5) is taken from the enemy's "violence" field if set, otherwise
guessed from its note (head bursts, killed, grappled... rank highest). Enemies
under 0.5 s are capped low. Highest score gets label priority 1, and so on.
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORDS = [(5, ("burst", "explod", "severed", "head flying", "flying head", "impaled", "cut down", "shot")),
         (4, ("grappl", "grabbed", "wrestl", "thrown", "dying", "bloody", "held", "hauled")),
         (3, ("brute", "charger", "leaping", "horned", "mutant", "gun", "blade", "axe", "cleaver")),
         (2, ("cultist", "runner", "enemy")),
         (1, ("far", "faint", "small", "edge", "fog", "background"))]

def violence(e):
    if e.get("violence_manual") or e.get("auto"):
        return e.get("violence", 1)
    note = e.get("note", "").lower()
    for v, ws in WORDS:
        if any(w in note for w in ws):
            return v
    return 2

AUTO_MIN_S = 1.0  # after relinking, auto tracks shorter than this are detection noise
RELINK_GAP = 0.7  # s: bridge detector dropouts (figure fading into fog) up to this long
RELINK_FRAC = 0.6  # gate: predicted-position error allowed, as a fraction of figure height
ABSORB_FRAC = 1.0  # auto track within this many figure heights of a hand track is the same figure
MERGE_FRAC = 0.45  # same baddie if paths stay within this fraction of the figure height

def pos(e, t):
    import numpy as np
    k = np.array(e["keys"], float)
    return np.interp(t, k[:, 0], k[:, 1]), np.interp(t, k[:, 0], k[:, 2])

def relink(tracks):
    """Denoise detector output: join fragments of one figure across dropouts using a
    constant-velocity prediction (Kalman-style gate), so fog flicker can't spawn new labels."""
    import numpy as np
    ts = sorted((t for t in tracks), key=lambda t: t["keys"][0][0])
    joined = True
    while joined:
        joined = False
        for a in ts:
            ka = np.array(a["keys"], float)
            v = (ka[-1, 1:3] - ka[max(0, len(ka) - 4), 1:3]) / max(ka[-1, 0] - ka[max(0, len(ka) - 4), 0], 1e-3)
            best = None
            for b in ts:
                if b is a:
                    continue
                kb = np.array(b["keys"], float)
                gap = kb[0, 0] - ka[-1, 0]
                if not (0 < gap <= RELINK_GAP):
                    continue
                pred = ka[-1, 1:3] + v * gap
                err = np.hypot(*(kb[0, 1:3] - pred)) / max(min(ka[-1, 3], kb[0, 3]), 1)
                if err < RELINK_FRAC and (best is None or err < best[0]):
                    best = (err, b)
            if best:
                a["keys"] = a["keys"] + best[1]["keys"]
                ts.remove(best[1])
                joined = True
                break
    return ts

def near(a, b, frac):
    import numpy as np
    a0, a1, b0, b1 = a["keys"][0][0], a["keys"][-1][0], b["keys"][0][0], b["keys"][-1][0]
    lo, hi = max(a0, b0), min(a1, b1)
    h = np.mean([k[3] for k in a["keys"]])
    if hi >= lo:
        ts_ = np.linspace(lo, hi, 6)
        return min(np.hypot(*np.subtract(pos(a, t), pos(b, t))) for t in ts_) < frac * h
    first, second = (a, b) if a1 < b0 else (b, a)
    gap = second["keys"][0][0] - first["keys"][-1][0]
    return gap <= 0.4 and np.hypot(second["keys"][0][1] - first["keys"][-1][1], second["keys"][0][2] - first["keys"][-1][2]) < frac * h

def same(a, b):
    if a.get("no_merge") or b.get("no_merge"):  # user-confirmed distinct figure
        return False
    hand = not (a.get("auto") or b.get("auto"))
    import numpy as np
    a0, a1, b0, b1 = a["keys"][0][0], a["keys"][-1][0], b["keys"][0][0], b["keys"][-1][0]
    lo, hi = max(a0, b0), min(a1, b1)
    if hi >= lo:  # overlap in time: compare paths over the overlap
        ts = np.linspace(lo, hi, 6)
        dist = np.mean([np.hypot(*(np.subtract(pos(a, t), pos(b, t)))) for t in ts])
        h = min(np.mean([k[3] for k in a["keys"]]), np.mean([k[3] for k in b["keys"]]))
        if hand:  # two hand tracks: only true duplicates (same spot, mostly the same time)
            short = min(a1 - a0, b1 - b0)
            return dist < 0.25 * h and (hi - lo) >= 0.6 * short
        return dist < MERGE_FRAC * h
    if hand:
        return False
    first, second = (a, b) if a1 < b0 else (b, a)  # hand-off: one ends, the other picks up nearby
    gap = second["keys"][0][0] - first["keys"][-1][0]
    jump = np.hypot(second["keys"][0][1] - first["keys"][-1][1], second["keys"][0][2] - first["keys"][-1][2])
    return gap <= 0.25 and jump < 0.35 * min(first["keys"][-1][3], second["keys"][0][3])

def merge_duplicates(shot):
    es = shot["enemies"]
    merged = True
    while merged:
        merged = False
        for i in range(len(es)):
            for j in range(i + 1, len(es)):
                if same(es[i], es[j]):
                    a, b = sorted((es[i], es[j]), key=lambda e: (bool(e.get("auto")), -(e["keys"][-1][0] - e["keys"][0][0])))
                    bk = b["keys"]
                    if b.get("auto") and not a.get("auto"):  # auto only extends a hand track, never jiggles it
                        t0, t1 = a["keys"][0][0] - 0.05, a["keys"][-1][0] + 0.05
                        bk = [k for k in bk if k[0] < t0 or k[0] > t1]
                    keys = {round(k[0], 2): k for k in bk}
                    keys.update({round(k[0], 2): k for k in a["keys"]})  # the longer track wins on clashes
                    a["keys"] = [keys[t] for t in sorted(keys)]
                    a["note"] = a.get("note", "") + " + " + b.get("note", "")
                    for f in ("fade_out", "fade_in"):
                        if f in b and f not in a:
                            a[f] = b[f]
                    if not a.get("auto"):
                        a.pop("auto", None)
                    if not a.get("violence_manual"):
                        a.pop("violence", None)
                    es.remove(b)
                    merged = True
                    break
            if merged:
                break

def main():
    p = ROOT / "data/keyframes.json"
    d = json.loads(p.read_text())
    labels = sorted(json.loads((ROOT / "data/labels.json").read_text()), key=lambda r: r["priority"])
    for s in d["shots"]:  # add OWLv2 detections (tools/detect_owl.py); hand tracks win on merge
        det = ROOT / f"data/detected_{s['name']}.json"
        if det.exists() and not s.get("no_auto"):
            auto = json.loads(det.read_text())
            auto = [e for e in relink(auto) if s["start"] <= e["keys"][0][0] and e["keys"][-1][0] <= s["end"] + 0.05
                    and e["keys"][-1][0] - e["keys"][0][0] >= AUTO_MIN_S]
            pinned = [e for e in s["enemies"] if e.get("no_merge") or e.get("feature")]
            s["enemies"] = relink([e for e in s["enemies"] if e not in pinned]) + pinned
            hand = [e for e in s["enemies"]]
            for e in auto:  # an auto track near any hand track IS that figure: absorb, never relabel
                host = next((h for h in hand if near(h, e, ABSORB_FRAC)), None)
                if host is None:
                    s["enemies"].append(e)
                else:
                    t0, t1 = host["keys"][0][0] - 0.05, host["keys"][-1][0] + 0.05
                    host["keys"] = sorted(host["keys"] + [k for k in e["keys"] if k[0] < t0 or k[0] > t1])
    before = sum(len(s["enemies"]) for s in d["shots"])
    for s in d["shots"]:
        merge_duplicates(s)
    enemies = [e for s in d["shots"] for e in s["enemies"]]
    print(f"merged {before - len(enemies)} duplicate tracks; {len(enemies)} baddies")
    for e in enemies:
        dur = e["keys"][-1][0] - e["keys"][0][0]
        e["violence"] = violence(e)
        e["score"] = round(e["violence"] ** 2 * (min(dur, 1.5) if dur >= 0.5 else dur * 0.3), 3)
    # close-up "feature" baddies get the very worst bugs, in their feature order
    order = sorted(enemies, key=lambda e: (e.get("feature") is None, e.get("feature", 0), -e["score"]))
    by_short = {l["short"]: l for l in labels}
    # Label lock: once a baddie has a bug it keeps it across re-runs, so adding or
    # merging other tracks never reshuffles labels you already approved.
    lock_p = ROOT / "data/label_lock.json"
    if lock_p.exists():
        lock_p.chmod(0o644)
    lock = json.loads(lock_p.read_text()) if lock_p.exists() else {}
    def key(e):
        if e.get("auto"):  # detector tracks: id from shot + start time
            return f"auto/{e['keys'][0][0]:.2f}"
        return e["id"]
    for e in enemies:
        if not e.get("label") and lock.get(key(e)) in by_short:
            e["label"] = lock[key(e)]
    forced = [e for e in enemies if e.get("label")]  # hand-tuned: same figure across cuts keeps one bug
    taken = {by_short[e["label"]]["id"] for e in forced}
    for e in forced:
        e["label_id"] = by_short[e["label"]]["id"]
    labels = [l for l in labels if l["id"] not in taken and l["origin"] != "finale"]
    order = [e for e in order if not e.get("label")]
    for rank, e in enumerate(order):
        e["label_id"] = labels[rank]["id"]
    for e in enemies:
        lock.setdefault(key(e), next(l["short"] for l in json.loads((ROOT / "data/labels.json").read_text()) if l["id"] == e["label_id"]))
    # Only NEW baddies are appended; an existing entry changes only by editing this file by hand.
    lock_p.write_text(json.dumps(lock, indent=1, sort_keys=True) + "\n")
    lock_p.chmod(0o444)
    # never rewrite the hand annotations: tools/keys_to_tracks.py reads this file instead
    (ROOT / "data/keyframes.assigned.json").write_text(json.dumps(d, indent=1) + "\n")
    for e in order[:12]:
        print(f'{e["score"]:5.2f}  v{e["violence"]}  {next(l["short"] for l in labels if l["id"] == e["label_id"]):40s} {e.get("note", "")}')

main()
