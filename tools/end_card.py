# /// script
# dependencies = ["pillow==11.0.0", "numpy<2.3", "scipy<1.16"]
# ///
"""Cliffhanger ending: cut to black mid-action, duck the score, end card.

Takes out/preview.mp4 (720p) or, with --4k, the source + out/overlay.webm,
cuts at END (the grenade leaves his hand, before it lands), and appends an
end card drawn with the same font, colour and shadow stack as the labels.
Audio keeps playing under the card (the unseen blast) but is ducked hard on
the cut and faded out with the card.

Writes out/final_preview.mp4 (or out/final_4k.mp4 with --4k).
"""
import json, pathlib, subprocess, sys, os
ROOT = pathlib.Path(__file__).resolve().parent.parent
src = (ROOT / "tools/render.py").read_text().replace("\nmain()\n", "\n")
ns = {"__file__": str(ROOT / "tools/render.py"), "__name__": "render_lib"}
exec(compile(src, "render", "exec"), ns)
from PIL import Image

END = 68.535         # money shot: marine leaps at the gatling; last frame before the 1:08.543 cut
CARD = 6.0           # black tail + status line           # seconds of end card
NO_TEXT = False      # status-line end card (strategy 2)
BLACK = 1.2          # hold on pure black after the cut, then hard-cut to the text
OUT_FADE = 0.9       # card text fades out over the last OUT_FADE seconds
DUCK_DB = 0            # no duck: the score carries across the cut        # score drops this much on the cut
FPS = 30000 / 1001
# Musical splice: the film's own audio stops ~0.6 s after the cut (before the battle
# sounds at 1:05.6) and crossfades into the pensive score from the breathing-space
# scene, which carries under the black and the message, then fades with the card.
import json as _json
MIX = _json.loads((ROOT / "data/audio_mix.json").read_text())  # from tools/audio_splice.py
SPLICE_FROM = MIX["splice_from"]
XFADE = MIX["crossfade_s"]
four_k = "--4k" in sys.argv
W, H = (3840, 1920) if four_k else (1280, 640)
k = W / 3840

# Strategy 2: an in-world status line, the war's own language.
BUGS_REMAINING = 750  # fixed by the user: the real size of the job, not today's issue count
line1, line2 = f"BUGS REMAINING: {BUGS_REMAINING}", "github.com/obs-rust"
print(line1)
f1 = ns["font"](round(120 * ns["LABEL_SCALE"] * k * 0.62))
f2 = ns["font"](round(120 * ns["LABEL_SCALE"] * k * 0.52))
tmp = ROOT / "out/card"
tmp.mkdir(parents=True, exist_ok=True)
n = round(CARD * FPS)
# Feature-film end card conventions: true black (no vignette, no grain), small
# type with wide tracking, no drop shadow (a shadow on black only adds a murky
# halo), a clear size/brightness hierarchy, and slow, unhurried fades.
from PIL import ImageDraw
TEXT = ns["TEXT_RGB"]

def tracked(img, text, f, cx, cy, alpha, track):
    """Centre one line at (cx, cy) with extra letter spacing (track, in px)."""
    if alpha <= 0:
        return
    widths = [f.getlength(c) for c in text]
    total = sum(widths) + track * (len(text) - 1)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x = cx - total / 2
    asc = f.getbbox("H")
    y = cy - (asc[1] + asc[3]) / 2
    for c, w in zip(text, widths):
        d.text((x, y), c, font=f, fill=(*TEXT, round(255 * alpha)))
        x += w + track
    img.alpha_composite(layer)

ease = lambda x: max(0.0, min(1.0, x)) ** 2 * (3 - 2 * max(0.0, min(1.0, x)))
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                        "-r", "30000/1001", "-i", "-", "-c:v", "libx264", "-crf", "12", "-tune", "film",
                        "-pix_fmt", "yuv420p", str(tmp / "card.mp4")], stdin=subprocess.PIPE)
for i in range(n):
    t = i / FPS
    out = min(1.0, (CARD - t) / OUT_FADE)
    a1 = 0.0 if NO_TEXT else ease((t - BLACK) / 0.8) * ease(out)               # slow, unhurried
    a2 = 0.0 if NO_TEXT else ease((t - BLACK - 0.9) / 0.8) * ease(out) * 0.9   # second line, still clearly readable
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    tracked(img, line1, f1, W / 2, H * 0.44, a1, f1.size * 0.12)
    tracked(img, line2, f2, W / 2, H * 0.44 + f1.size * 1.55, a2, f2.size * 0.08)
    enc.stdin.write(img.tobytes())
enc.stdin.close(); enc.wait()

dst = ROOT / ("out/final_4k.mp4" if four_k else "out/final_preview.mp4")
video_in = ["-t", f"{END}", "-i", str(ROOT / "out/preview.mp4")] if not four_k else \
           ["-t", f"{END}", "-i", str(ROOT / "marines-fixing-bugs.webm"), "-t", f"{END}", "-c:v", "libvpx-vp9", "-i", str(ROOT / "out/overlay.webm")]
vchain = "[0:v]setsar=1[base]" if not four_k else "[0:v][1:v]overlay=format=auto,setsar=1[base]"
ai = 1 if not four_k else 2
duck = 10 ** (DUCK_DB / 20)
filt = (f"{vchain};[base][{ai}:v]concat=n=2:v=1:a=0[v];"
        f"[{ai + 1}:a]asplit=3[s1][s2][s3];"
        f"[s1]atrim=0:{END},asetpts=PTS-STARTPTS[body];"
        # the battle audio after the cut recedes (low-pass) while the score swells in
        f"[s2]atrim={END}:{END + XFADE},asetpts=PTS-STARTPTS,lowpass=f={MIX['outgoing_lowpass_hz'][1]}[muffle];"
        f"[body][muffle]concat=n=2:v=0:a=1[head];"
        f"[s3]atrim={SPLICE_FROM}:{SPLICE_FROM + CARD + 2},asetpts=PTS-STARTPTS,volume={MIX['splice_gain_db']}dB[tail];"
        f"[head][tail]acrossfade=d={XFADE}:c1={MIX['crossfade_curve']}:c2={MIX['crossfade_curve']},"
        f"afade=t=out:st={END + CARD - MIX['fade_out_s']}:d={MIX['fade_out_s']}[a]")
cmd = ["ffmpeg", "-v", "error", "-y", *video_in, "-i", str(tmp / "card.mp4"),
       "-i", str(ROOT / "marines-fixing-bugs.webm"),
       "-filter_complex", filt, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18", "-preset", "fast",
       "-c:a", "aac", "-b:a", "192k", "-shortest", str(dst)]
subprocess.run(cmd, check=True)
print("wrote", dst)
