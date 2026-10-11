"""Build data/labels.json: hardcore C/C++ bug names for the on-screen enemies.

Only real low-level defects (memory, UB, races, overflows, crashes) qualify;
CI, docs, ports and tooling never become labels. Order = priority: bugs we
fixed in obs-rust first, then upstream OBS crash reports, then illustrative
names distilled from the general pile of OBS crash reports. Names are meant to
read instantly to a C programmer, not to be exact.
"""
import json, pathlib

D = pathlib.Path(__file__).resolve().parent.parent / "data"
UP = "obsproject/obs-studio"
OURS = "obs-rust/obs-studio"
# Ordered most severe first: priority = position (1 = worst). Severity means
# memory corruption an attacker can drive > crashes on the hot path > races >
# UB > leaks. Weak "forgot to check a return value" items are excluded.
LABELS = [
    ("kernel driver crash (BSOD)", "upstream", UP, [11921, 13779]),
    ("graphics driver crash", "upstream", UP, [11921]),
    ("read after free", "fixed", OURS, [93]),
    ("server crash: stack overflow", "fixed", OURS, [99]),
    ("heap overflow from crafted LUT file", "fixed", OURS, [94]),
    ("string insert buffer overrun", "fixed", OURS, [46, 53]),
    ("free of uninitialized pointer", "fixed", OURS, [101]),
    ("unbounded recursion on server data", "fixed", OURS, [102]),
    ("use of freed video_t", "upstream", UP, [12213]),
    ("double free", "illustrative", None, []),
    ("heap corruption", "illustrative", None, []),
    ("NULL deref after session freed", "upstream", UP, [13809]),
    ("use of destroyed GL display", "upstream", UP, [13934]),
    ("array index overflow in audio capture", "fixed", OURS, [92]),
    ("out-of-bounds read+write (no wide NUL)", "fixed", OURS, [95]),
    ("data race on audio buffer", "sanitizer", OURS, [130]),
    ("NULL xcb reply SEGV in hotkey thread", "sanitizer", OURS, [126]),
    ("NULL outputHandler deref on quit", "sanitizer", OURS, [127]),
    ("null pointer crash", "fixed", OURS, [57, 64]),
    ("shift-by-32 undefined behavior", "fixed", OURS, [11, 17]),
    ("unwind across FFI boundary", "fixed", OURS, [80, 81]),
    ("stack buffer overflow", "illustrative", None, []),
    ("integer overflow crash", "illustrative", None, []),
    ("out-of-bounds memcpy", "illustrative", None, []),
    ("heap buffer underflow", "illustrative", None, []),
    ("use-after-free in callback", "illustrative", None, []),
    ("dangling this in worker thread", "illustrative", None, []),
    ("refcount underflow", "illustrative", None, []),
    ("ABA in lock-free queue", "illustrative", None, []),
    ("deadlock: lock order inversion", "illustrative", None, []),
    ("data race on refcount", "illustrative", None, []),
    ("race on shutdown", "illustrative", None, []),
    ("callback after API teardown", "sanitizer", OURS, [156]),
    ("unlocked read in VolumeMeter", "sanitizer", OURS, [131]),
    ("non-reentrant localtime() race", "sanitizer", OURS, [132]),
    ("data race in output list", "upstream", UP, [11645]),
    ("double start race condition", "upstream", UP, [13283]),
    ("strlen(NULL) segfault", "upstream", UP, [13905]),
    ("EXC_BAD_ACCESS null write", "upstream", UP, [13624]),
    ("glGetString returned NULL", "upstream", UP, [7481]),
    ("illegal instruction 0xC000001D", "upstream", UP, [13704]),
    ("dangling display handle", "upstream", UP, [11929]),
    ("GPU hard lock on resize", "upstream", UP, [13779]),
    ("D3D device removed", "illustrative", None, []),
    ("SIGSEGV in audio thread", "illustrative", None, []),
    ("pure virtual call", "illustrative", None, []),
    ("null vtable call", "illustrative", None, []),
    ("use-after-move", "illustrative", None, []),
    ("stale pointer after realloc", "illustrative", None, []),
    ("dangling reference", "illustrative", None, []),
    ("iterator invalidation", "illustrative", None, []),
    ("format string vulnerability", "illustrative", None, []),
    ("uninitialized stack read", "illustrative", None, []),
    ("off-by-one write", "illustrative", None, []),
    ("negative array index", "illustrative", None, []),
    ("signed/unsigned wraparound", "illustrative", None, []),
    ("64-to-32-bit truncation", "illustrative", None, []),
    ("TOCTOU race", "illustrative", None, []),
    ("atomic missing barrier", "illustrative", None, []),
    ("double unlock", "illustrative", None, []),
    ("lock held across callback", "illustrative", None, []),
    ("misaligned pointer access", "illustrative", None, []),
    ("unaligned SIMD load", "illustrative", None, []),
    ("SIGBUS on truncated mmap", "illustrative", None, []),
    ("division by zero", "illustrative", None, []),
    ("buffer over-read in OBU parser", "fixed", OURS, [103]),
    ("UTF-8 split mid-codepoint", "fixed", OURS, [21, 23, 26]),
    ("infinite loop on empty pattern", "fixed", OURS, [47]),
    ("zero chunk size hang", "fixed", OURS, [100]),
    ("off-by-one quote parse", "fixed", OURS, [48, 54]),
    ("wide string conversion returns 0", "fixed", OURS, [84, 85]),
    ("silent data loss on save", "fixed", OURS, [35, 36, 37, 71]),
    ("memory leak in hot loop", "illustrative", None, []),
    ("sink name memory leak", "sanitizer", OURS, [158]),
    ("encoder memory leak", "upstream", UP, [13803]),
    # finale: hand-assigned by the user, pinned with label= in tools/restore_keyframes.py
    ("audio stutter", "finale", None, []),
    ("uint8_t overflow", "finale", None, []),
    ("anti ai policy", "finale", None, []),
    ("unit test", "finale", None, []),
    ("e2e tests", "finale", None, []),
    ("Address Sanitizer", "finale", None, []),
]

raw = {(k, x["number"]): x for k, f in (("pr", "raw_prs.json"), ("issue", "raw_issues.json"))
       for x in json.loads((D / f).read_text(encoding="utf-8"))}
out = []
for i, (short, origin, repo, nums) in enumerate(LABELS, 1):
    refs = []
    for n in nums:
        hit = raw.get(("issue", n)) or raw.get(("pr", n)) if repo == OURS else None
        refs.append({"repo": repo, "number": n, "title": hit["title"] if hit else None,
                     "url": hit["url"] if hit else f"https://github.com/{repo}/issues/{n}"})
    out.append({"id": i, "priority": i, "short": short, "origin": origin, "refs": refs})
(D / "labels.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(len(out), "labels:", sum(r["origin"] == "fixed" for r in out), "fixed,",
      sum(r["origin"] == "sanitizer" for r in out), "sanitizer,", sum(r["origin"] == "upstream" for r in out), "upstream,", sum(r["origin"] == "illustrative" for r in out), "illustrative")
