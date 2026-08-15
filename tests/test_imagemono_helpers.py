"""The pure helpers of Svenesis ImageMono Train, EXECUTED.

Static analysis cannot tell whether _format_duration survives an infinity.
This runs each helper on hostile input and asserts the invariants: no
exception, a usable answer, and — for the numeric ones — the documented
behaviour across the whole range.

Run:  python3 tests/test_imagemono_helpers.py
"""
import ast
import datetime
import itertools
import math
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "Svenesis-ImageMono-Train.py")
src = open(SRC).read()
tree = ast.parse(src)

ns = {"os": os, "re": re, "math": math, "datetime": datetime, "np": np,
      "_log_swallowed": lambda exc: None, "fits": None}
for node in tree.body:                      # module constants
    if isinstance(node, ast.Assign):
        try:
            exec(compile(ast.Module([node], []), "<c>", "exec"), ns)
        except Exception:                   # noqa: BLE001  (needs a name we skip)
            pass
WANT = ("_format_duration", "_median", "_exp_tag", "_night_key", "_path_date",
        "_safe", "_clean_token", "_filter_role", "_plural", "_sig_sort_key",
        "_rejection_args", "_rejection_fallback", "_calib_signature",
        "_signature_matches", "_effective_exposure", "_mix_words",
        "_palette_roles", "_is_nb_palette", "_fits_ext", "_is_fits_like",
        "_first_with_role", "_detect_palette", "_auto_channel_map",
        "_unfillable_channels", "_align_pairs_warn", "_weight_token",
        "_parse_spcc_fit", "_log_delta")
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in WANT:
        exec("from __future__ import annotations\n"
             + ast.get_source_segment(src, node), ns)
i = src.index("_NB_PALETTES = {")
j = src.index("def _plural")
exec("from __future__ import annotations\n" + src[i:j], ns)

fails = []


def probe(label, fn, *args, want=None, check=None):
    try:
        got = fn(*args)
    except Exception as exc:                # noqa: BLE001
        print(f"   RAISED  {label}: {type(exc).__name__}: {exc}")
        fails.append(label)
        return None
    ok = True if want is None else got == want
    if check is not None:
        ok = ok and check(got)
    print(f"   {'ok  ' if ok else 'FAIL'} {label} -> {got!r}")
    if not ok:
        fails.append(label)
    return got


def check(ok, msg):
    print(("   ok   " if ok else "   FAIL ") + msg)
    if not ok:
        fails.append(msg)


print("1) _format_duration answers every input with a string")
fd = ns["_format_duration"]
for v in (float("inf"), float("-inf"), float("nan"), None, "", "abc",
          0, -1, 0.4):
    probe(f"_format_duration({v!r})", fd, v, want="—")
probe("59s", fd, 59, want="59s")
probe("1m 00s", fd, 60, want="1m 00s")
probe("1h 00m", fd, 3600, want="1h 00m")

print("\n2) _exp_tag is a safe sequence-name token")
et = ns["_exp_tag"]
for v, w in ((300.0, "300s"), (1.5, "1p5s"), (0.001, "0p001s"), (120, "120s")):
    probe(f"_exp_tag({v})", et, v, want=w)
for v in (float("inf"), float("nan"), None, "abc"):
    probe(f"_exp_tag({v!r})", et, v, want="0s")
real = [0.001, 0.5, 1, 1.5, 2.5, 30, 120, 300.0, 1800, 3600.5]
tags = [et(v) for v in real]
check(len(set(tags)) == len(tags), "ten real exposures give ten distinct tags")
check(all("." not in t and "+" not in t and "e" not in t[:-1] for t in tags),
      "no dot, no plus, no exponent")

print("\n3) _median is a true median")
med = ns["_median"]
probe("[]", med, [], want=0.0)
probe("[2]", med, [2], want=2)
probe("[1,2,3,4]", med, [1, 2, 3, 4], want=2.5)
probe("[3,1,2]", med, [3, 1, 2], want=2)

print("\n4) rejection bands cover the range without gap or overlap")
ra = ns["_rejection_args"]
bands = {}
for n in range(0, 2001):
    bands.setdefault(ra(n, True)[1], []).append(n)
for label, got in sorted(bands.items(), key=lambda kv: kv[1][0]):
    contiguous = got == list(range(got[0], got[-1] + 1))
    print(f"   {label:44s} {got[0]:5d}..{got[-1]:5d} "
          f"{'contiguous' if contiguous else 'GAPPED'}")
    check(contiguous, f"{label} is one contiguous band")
covered = sorted(n for v in bands.values() for n in v)
check(covered == list(range(0, 2001)),
      "every count 0..2000 lands in exactly one band")
check(all(len(ra(n, True)[0]) == 4 and ra(n, True)[0][0] == "rej"
          for n in range(1, 2001)),
      "every token list reads `rej algo lo hi`")
check(ra(50, False)[0] == ["rej", "none"],
      "rejection off sends Siril's own `rej none`")

print("\n5) _night_key puts one observing night under one date")
nk = ns["_night_key"]
probe("21:00", nk, "2026-07-20T21:00:00", want="2026-07-20")
probe("03:00 next day", nk, "2026-07-21T03:00:00", want="2026-07-20")
probe("noon starts the new night", nk, "2026-07-21T12:00:00",
      want="2026-07-21")
probe("one second before noon", nk, "2026-07-21T11:59:59", want="2026-07-20")
for v in ("", None, "not-a-date", "2026-13-45T99:99:99"):
    probe(f"_night_key({v!r})", nk, v, want="")

print("\n6) _signature_matches is symmetric and tolerant of gaps")
sm = ns["_signature_matches"]
base = {"exp_s": 300.0, "gain_v": 100, "binning": 1, "dims": (3008, 3008),
        "temp_v": -10.0, "instrument": "Ares-M"}
check(sm(base, base), "a master matches its own lights")
for key, other in (("exp_s", 301.0), ("gain_v", 200), ("binning", 2),
                   ("dims", (100, 100)), ("temp_v", 20.0),
                   ("instrument", "ASI533")):
    a = dict(base, **{key: other})
    check(sm(a, base) == sm(base, a), f"symmetric in {key}")
    check(not sm(a, base), f"a different {key} is refused")
for key in ("gain_v", "temp_v", "dims", "instrument"):
    check(sm(dict(base, **{key: None}), base),
          f"a missing {key} does not block a match")
# `_inspect` seeds exp_s with 0.0 and only overwrites it when EXPTIME
# parses, so an unreadable exposure arrives as 0.0 — not None — and 0 s
# against 300 s is exactly the mismatch that must not slip through.
check(not sm(dict(base, exp_s=0.0), base),
      "an unreadable exposure (0.0) DOES block the match")

print("\n7) _align_pairs_warn on degenerate input")
w = ns["_align_pairs_warn"]
probe("empty", w, {}, want=set())
probe("one channel", w, {"HA": 100}, check=lambda g: isinstance(g, set))
probe("all zero", w, {"A": 0, "B": 0}, want={"A", "B"})
probe("one weak", w, {"A": 200, "B": 180, "C": 5},
      check=lambda g: g == {"C"})

print("\n8) filter roles and palettes survive junk")
fr = ns["_filter_role"]
for v, w2 in (("Ha", "ha"), ("ha", "ha"), ("H-alpha", "ha"),
              ("OIII", "oiii"), ("S2", "sii"), ("Lum", "lum")):
    probe(f"_filter_role({v!r})", fr, v, want=w2)
for v in ("", "  ", "ZZZ", None):
    probe(f"_filter_role({v!r})", fr, v, want=None)
probe("_detect_palette([])", ns["_detect_palette"], [],
      check=lambda g: g in ns["PALETTES"])
probe("_unfillable([], Realistic1)", ns["_unfillable_channels"], [],
      "Realistic1", want=["red", "green", "blue"])
for pal, roles in ns["_NB_PALETTES"].items():
    check(len(roles) == 3 and set(roles) <= {"ha", "oiii", "sii"},
          f"{pal} maps three emission lines")
    check(all(r in ns["_LINE_NM"] for r in roles),
          f"{pal} has a wavelength for every channel")
    # The name IS the assignment, read left to right.  A palette whose
    # letters disagree with its tuple would send SPCC the wavelengths of
    # one palette while the composite shows another.
    letter = {"ha": "H", "oiii": "O", "sii": "S"}
    check(pal == "".join(letter[r] for r in roles),
          f"{pal} is named after the channels it fills")

# All six ways to give three DIFFERENT lines to three channels.  SOH was
# missing until the table was checked against Perfect Palette Picker, with
# nothing behind its absence -- an asymmetry no reader could have guessed.
perms = {p for p, r in ns["_NB_PALETTES"].items() if len(set(r)) == 3}
want = {"".join(p) for p in itertools.permutations("HOS")}
check(perms == want, f"all six permutations are offered, missing {want - perms}")
two = {p for p, r in ns["_NB_PALETTES"].items() if len(set(r)) == 2}
check(len(two) == 8, f"and eight two-line variants ({len(two)})")
for pal, chans in ns["_MIX_PALETTES"].items():
    for ch, mix in chans.items():
        check(abs(sum(mix.values()) - 1.0) < 1e-9,
              f"{pal} {ch} weights sum to 1")

print("\n8a) the log delta survives a buffer that drops its oldest lines")
# The reason the star-pair counts never appeared on a real three-filter
# run: `after.startswith(before)` assumes the log only grows.  Siril's
# buffer is bounded, so on a long run the front falls off and no earlier
# snapshot is a prefix again — after which BOTH readers returned silently.
ld = ns["_log_delta"]
before = "line %d\n" * 0 + "".join(f"old line {i}\n" for i in range(200))
step = "".join(f"step line {i}\n" for i in range(20))
check(ld(before, before + step) == step, "the ordinary growing case")
# Now the same, with the first half of the buffer dropped.
slid = (before + step)[len(before) // 2:]
check(ld(before, slid) == step,
      "and the case that actually happens: the front was trimmed away")
check(ld("", "anything") == "anything",
      "an empty snapshot means everything after it is the delta")
check(ld(None, "x") is None and ld("x", None) is None,
      "an unreadable log yields None, not a wrong answer")
# If the step outran the whole buffer, the anchor is gone and the honest
# answer is None -- the caller then says so rather than guessing.
check(ld(before, "totally unrelated buffer contents") is None,
      "and so does a buffer that no longer holds the anchor at all")
probe("anchor is bounded", lambda: ns["LOG_ANCHOR_CHARS"],
      check=lambda n: 100 <= n <= 2000)

print("\n8b) the SPCC fit is read back from Siril's own words")
# Verbatim from two runs of the same 94 frames, HOS and HSO.  Siril's
# "imprecise solution" warning fires on BOTH, so it cannot separate them;
# the sigmas differ by a factor of 40 and can.
HOS_LOG = """21:46:59: Applying aperture photometry to 2594 stars.
21:46:59: 1042 stars excluded from the calculation
21:46:59: SPCC Linear Fits
21:46:59: Image R/G = -0.058264 + 1.425576 * Catalog R/G (sigma: 6.159311)
21:46:59: Image B/G = 0.005830 + 1.442021 * Catalog B/G (sigma: 5.388299)
21:46:59: Found a solution for color calibration using 1554 stars. Factors:
21:46:59: K0: 0.872
21:46:59: K1: 1.000
21:46:59: K2: 0.848
21:46:59: The photometric color calibration seems to have found an imprecise \
solution, consider correcting the image gradient first
21:46:59: Spectrophotometric Color Calibration succeeded."""
HSO_LOG = """21:46:59: 1042 stars excluded from the calculation
21:46:59: Image R/G = -0.223529 + 1.165380 * Catalog R/G (sigma: 0.148979)
21:46:59: Image B/G = 0.004268 + 0.685778 * Catalog B/G (sigma: 0.238639)
21:46:59: Found a solution for color calibration using 1552 stars. Factors:
21:46:59: K0: 0.858
21:46:59: K1: 0.847
21:46:59: K2: 1.000"""
sp = ns["_parse_spcc_fit"]
hos, hso = sp(HOS_LOG), sp(HSO_LOG)
print(f"   HOS: {hos.get('sigma')}  stars={hos.get('stars')}")
print(f"   HSO: {hso.get('sigma')}  stars={hso.get('stars')}")
check(hos["sigma"] == {"R/G": 6.159311, "B/G": 5.388299},
      "both ratio sigmas are read")
check(hos["stars"] == 1554 and hos["excluded"] == 1042,
      "so are the star counts behind them")
check(hos["k"] == {0: 0.872, 1: 1.0, 2: 0.848},
      "and the white-balance factors that were applied")
check(hos.get("imprecise") and not hso.get("imprecise"),
      "Siril's own warning is recorded where it appears")
check(max(hso["sigma"].values()) < ns["SPCC_SIGMA_LIMIT"]
      < max(hos["sigma"].values()),
      "the threshold separates the two runs the warning could not")
# Timestamps are stripped the same way _parse_align_pairs strips them,
# and a run that logged nothing recognisable must stay silent.
check(sp("") == {} and sp("nothing to see here\nSaving FITS: x") == {},
      "an unrecognised log yields nothing rather than a wrong number")
check(sp("Image R/G = 1 + 2 * Catalog R/G (sigma: not-a-number)") == {},
      "and an unparseable sigma is dropped, not guessed")

print("\n9) file extensions, including the compound ones")
for name, ext, like in (("a.fit", ".fit", True), ("a.fits", ".fits", True),
                        ("a.fits.fz", ".fits.fz", True),
                        ("a.fts.fz", ".fts.fz", True),
                        ("a.FIT", ".fit", True), ("a.xisf", ".xisf", False),
                        ("a", "", False), ("a.fits.fz.bak", ".bak", False)):
    got = ns["_fits_ext"](name)
    check(got == ext and ns["_is_fits_like"](got) is like,
          f"{name} -> {got!r}, fits-like={like}")

print("\n10) the flat-on-flat measurement separates level from shape")
seg = src[src.index("FLAT_MATCH_GOOD"):src.index("def _median")]
fns = {"np": np, "fits": None, "_log_swallowed": lambda e: None}
exec("from __future__ import annotations\n" + seg, fns)
good, limit = fns["FLAT_MATCH_GOOD"], fns["FLAT_MATCH_LIMIT"]
check(good < limit, f"thresholds ordered: {good} < {limit}")


def spread(x, y):
    sx = x[::4, ::4] / np.median(x[::4, ::4])
    sy = y[::4, ::4] / np.median(y[::4, ::4])
    return float(np.nanstd(sx / sy))


base_img = np.ones((256, 256)) * 1000.0
vign = np.linspace(0.8, 1.0, 256)[None, :] * np.ones((256, 1))
a = base_img * vign
s_same = spread(a, a * 3.0)
s_moved = spread(a, base_img * (np.linspace(0.75, 1.0, 256)[None, :]
                                * np.ones((256, 1))))
print(f"   same optics, 3x brighter: {s_same:.5f}")
print(f"   vignetting moved        : {s_moved:.5f}")
check(s_same < good, "a brightness difference is not a disagreement")
check(s_moved > limit, "a moved vignette is")

print()
if fails:
    print(f"{len(fails)} FAILURE(S)")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ALL HELPER PROBES PASSED")
