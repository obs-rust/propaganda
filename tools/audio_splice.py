# /// script
# dependencies = ["numpy<2.3"]
# ///
"""Find a score segment to splice in after the picture cut, so the music carries
through the end card. Writes out/audio/analysis.json (all candidates) and
data/audio_mix.json (the chosen plan, read by tools/end_card.py).

Method: decode the soundtrack with ffmpeg; fingerprint the last REF seconds
before the cut (chroma = harmony, onset envelope = rhythm, RMS = level); scan
the soundtrack for the segment whose opening best matches that fingerprint
while having few transients (gunfire/impacts) over its whole length; shift it
by up to half a beat so its onsets line up; measure loudness with ebur128.
"""
import json, pathlib, subprocess, re
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
SR = 22050
END = 68.535          # picture cut (keep in sync with tools/end_card.py)
NEED = 5.6            # seconds of score needed after the cut (black + card)
REF = 1.5
EXCLUDE_BEFORE = 2.5  # the opening helmet hit: never splice from the first shot
HOP, NFFT = 512, 4096

def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768

def stft_mag(x):
    w = np.hanning(NFFT)
    n = 1 + (len(x) - NFFT) // HOP
    fr = np.lib.stride_tricks.as_strided(x, (n, NFFT), (x.strides[0] * HOP, x.strides[0])) * w
    return np.abs(np.fft.rfft(fr, axis=1))

def chroma(mag):
    f = np.fft.rfftfreq(NFFT, 1 / SR)
    ok = (f > 60) & (f < 4000)
    pc = (np.round(12 * np.log2(f[ok] / 440)) % 12).astype(int)
    c = np.zeros((mag.shape[0], 12))
    for k in range(12):
        c[:, k] = mag[:, ok][:, pc == k].sum(1)
    return c / (np.linalg.norm(c, axis=1, keepdims=True) + 1e-9)

def main():
    x = decode(ROOT / "marines-fixing-bugs.webm")
    mag = stft_mag(x)
    fps = SR / HOP
    ch = chroma(mag)
    lmag = np.log1p(mag)
    flux = np.maximum(np.diff(lmag, axis=0), 0).sum(1)
    flux = np.concatenate([[0], flux])
    rms = np.sqrt((mag ** 2).mean(1))
    i_end = int(END * fps)
    i_ref = int((END - REF) * fps)
    ref_ch = ch[i_ref:i_end].mean(0)
    ref_on = flux[i_ref:i_end] - flux[i_ref:i_end].mean()
    ref_rms = rms[i_ref:i_end].mean()
    flux_med = np.median(flux)
    cands = []
    n_need, n_ref = int(NEED * fps), i_end - i_ref
    for i in range(0, len(ch) - n_need, 4):
        t = i / fps
        if abs(t - END) < NEED + 1 or (t < END and t + NEED > END - REF) or t < EXCLUDE_BEFORE:
            continue
        harm = float(ch[i:i + n_ref].mean(0) @ ref_ch)
        trans = float(np.percentile(flux[i:i + n_need], 95) / flux_med)  # spiky = effects
        peak = float(rms[i:i + n_need].max() / (np.median(rms[i:i + n_need]) + 1e-9))  # one big hit
        level = float(abs(np.log(rms[i:i + n_ref].mean() / ref_rms)))
        score = harm - 0.08 * trans - 0.25 * level - 0.05 * max(0.0, peak - 2.5)
        cands.append({"t": round(t, 3), "score": round(score, 4), "harmony": round(harm, 3),
                      "transients": round(trans, 2), "level_diff": round(level, 3)})
    cands.sort(key=lambda c: -c["score"])
    # keep distinct candidates (>= 1 s apart)
    top = []
    for c in cands:
        if all(abs(c["t"] - d["t"]) > 1 for d in top):
            top.append(c)
        if len(top) == 10:
            break
    best = top[0]
    # beat alignment: shift up to +-0.25 s so the onset envelopes line up
    i0 = int(best["t"] * fps)
    lags = [l for l in range(-int(0.25 * fps), int(0.25 * fps) + 1) if i0 + l >= 0 and i0 + l + n_ref <= len(flux)]
    def corr(l):
        seg = flux[i0 + l:i0 + l + n_ref]
        seg = seg - seg.mean()
        return float(ref_on @ seg / (np.linalg.norm(ref_on) * np.linalg.norm(seg) + 1e-9))
    lag = max(lags, key=corr)
    start = round(best["t"] + lag / fps, 3)
    def lufs(s, d):
        out = subprocess.run(["ffmpeg", "-v", "info", "-ss", str(s), "-t", str(d), "-i", str(ROOT / "marines-fixing-bugs.webm"),
                              "-vn", "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
        return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", out)[-1])
    l_ref, l_tail = lufs(END - 2.0, 2.0), lufs(start, NEED)
    gain_db = round(max(-6.0, min(6.0, l_ref - l_tail)), 2)
    analysis = {"end": END, "ref_seconds": REF, "need_seconds": NEED, "top_candidates": top,
                "chosen": best, "beat_lag_s": round(lag / fps, 3), "beat_corr": round(corr(lag), 3),
                "lufs_before_cut": l_ref, "lufs_splice": l_tail}
    (ROOT / "out/audio/analysis.json").write_text(json.dumps(analysis, indent=1) + "\n")
    plan = {"_doc": "Ending audio splice plan (tools/audio_splice.py -> tools/end_card.py). Times in source seconds.",
            "cut": END, "splice_from": start, "splice_gain_db": gain_db,
            "crossfade_s": 0.5, "crossfade_curve": "qsin",
            "outgoing_lowpass_hz": [12000, 900], "fade_out_s": 1.8}
    (ROOT / "data/audio_mix.json").write_text(json.dumps(plan, indent=1) + "\n")
    print(json.dumps(analysis["top_candidates"][:5], indent=0)); print(json.dumps(plan))

main()
