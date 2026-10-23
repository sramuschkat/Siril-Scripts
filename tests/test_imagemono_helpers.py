"""The pure helpers of Svenesis ImageMono Train, EXECUTED.

Static analysis cannot tell whether _format_duration survives an infinity.
This runs each helper on hostile input and asserts the invariants: no
exception, a usable answer, and — for the numeric ones — the documented
behaviour across the whole range.

Run:  python3 tests/test_imagemono_helpers.py
"""
import ast
import copy
import datetime
import itertools
import json
import tempfile
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
      "json": json,
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
        "_parse_spcc_fit", "_log_delta", "_log_text",
        "_parse_align_pairs", "_night_of", "_flat_shape",
        "_flat_normalise", "_rebin_mean", "_flat_ratio_spread", "_with_fits",
        "_spread_sample", "_palette_filters", "_align_ref_advice",
        "_pixel_scale_deg", "_fov_arcmin", "_rbf_narrowband_advice",
        "_output_dir", "_output_levels", "_looks_like_results",
        "_skip_in_discovery", "_filters_without_flats", "_frame_record",
        "_calib_master_stale", "_name_role", "_norm_filter",
        "_manifest_candidates", "_load_manifest", "_manifest_lights",
        "_manifest_pick", "_manifest_is_subset", "_manifest_panels",
        "_manifest_role", "_manifest_nb_doubt", "_manifest_role_overrides",
        "_manifest_spcc", "_manifest_metrics", "_apply_manifest",
        "_names_short", "_manifest_log_lines", "_manifest_md")
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

print("\n7b) _align_ref_advice names a switch only when it would do something")
adv = ns["_align_ref_advice"]
# The bug this replaces: the few-stars warning always pointed at "Stack
# only the filters this palette uses".  Under HaRGB that palette reads
# L, R, G, B AND Ha, so the option drops nothing and the advice sent the
# user to a switch that cannot change the outcome.
HARGB = {"compose": True, "palette_only": False, "compose_palette": "HaRGB",
         "map_red": "RED", "map_green": "GREEN", "map_blue": "BLUE",
         "map_lum": "LUMINOS"}
said = adv(HARGB, ["BLUE", "GREEN", "HA", "RED"], "LUMINOS")
check("palette uses" not in said,
      "HaRGB reads every filter — the switch is NOT offered")
check("LUMINOS is itself one of them" in said,
      "and the reference is named as one of the composite's own channels")
# The same warning under a palette that really does leave a master out.
SHO = {"compose": True, "palette_only": False, "compose_palette": "SHO",
       "map_red": "SII", "map_green": "HA", "map_blue": "OIII",
       "map_lum": "LUMINOS"}
said = adv(SHO, ["HA", "OIII", "SII"], "LUMINOS")
check("would leave LUMINOS out" in said,
      "SHO ignores the LUMINOS master — the switch IS offered, and names it")
# Three ways the switch cannot be the answer, each said as itself.
for opts, want, why in (
        (dict(SHO, palette_only=True), "already as small",
         "the pool is already restricted"),
        (dict(HARGB, compose=False), "needs a colour composite",
         "there is no palette to go by"),
        ({"compose": True, "palette_only": False, "compose_palette": "RGB",
          "map_red": "", "map_green": "", "map_blue": ""},
         "names none of the discovered filters",
         "the mapping is unrecognised")):
    got = adv(opts, ["HA"], "LUMINOS")
    check(want in got, f"no switch offered when {why}")

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

# The shipped functions, not a re-implementation of them.  This block once
# held its own copy of the arithmetic and went on passing while the real
# check reported shot noise as a mismatch on every dataset it saw.
norm, spread_of = fns["_flat_normalise"], fns["_flat_ratio_spread"]


def spread(x, y):
    return spread_of(norm(x), norm(y))


SIDE = 2000
ramp = np.linspace(0.8, 1.0, SIDE)[None, :] * np.ones((SIDE, 1))
base_img = np.ones((SIDE, SIDE)) * 24000.0
a = base_img * ramp
s_same = spread(a, a * 3.0)
s_moved = spread(a, base_img * (np.linspace(0.75, 1.0, SIDE)[None, :]
                                * np.ones((SIDE, 1))))
print(f"   same optics, 3x brighter: {s_same:.5f}")
print(f"   vignetting moved        : {s_moved:.5f}")
check(s_same < good, "a brightness difference is not a disagreement")
check(s_moved > limit, "a moved vignette is")

# Noise, and nothing else.  Two sets shot through the SAME optics differ by
# exactly zero in shape, so whatever the check returns for them is its own
# error bar -- and it has to land under the "these nights agree" threshold.
# The per-frame scatter is the one measured on a real 24 000 ADU flat.
rng = np.random.default_rng(20260816)
PER_FRAME = 0.0126


def night(n_frames):
    """The mean of `n_frames` noisy realisations of the same optics."""
    total = np.zeros((SIDE, SIDE))
    for _ in range(n_frames):
        total += a * (1.0 + rng.normal(0.0, PER_FRAME, (SIDE, SIDE)))
    return total / n_frames


one_a, one_b = night(1), night(1)
five_a, five_b = night(5), night(5)
raw = float(np.nanstd((one_a / np.median(one_a)) / (one_b / np.median(one_b))))
print(f"   noise only, one frame each, unbinned: {raw:.5f}")
check(raw > limit, "unbinned single frames are pure noise ABOVE the limit")
n_binned = spread(one_a, one_b)
n_full = spread(five_a, five_b)
print(f"   noise only, one frame each, binned  : {n_binned:.5f}")
print(f"   noise only, five frames each, binned: {n_full:.5f}")
check(n_binned < raw, "binning alone already suppresses most of it")
check(n_full < good, "a whole night, binned, lands under the agree threshold")
check(n_full < n_binned, "and averaging the night is what closes the gap")

# The floor is measured the way the run measures it: one night, split.
floor = spread_of(norm(night(2)), norm(night(2)))
check(floor > n_full,
      f"halves give a conservative floor: {floor:.5f} > {n_full:.5f}")

# A real mismatch still has to survive both noise-suppressing steps.
moved = a * 0 + base_img * (np.linspace(0.75, 1.0, SIDE)[None, :]
                            * np.ones((SIDE, 1)))
noisy_moved = np.zeros((SIDE, SIDE))
for _ in range(5):
    noisy_moved += moved * (1.0 + rng.normal(0.0, PER_FRAME, (SIDE, SIDE)))
check(spread(five_a, noisy_moved / 5) > limit,
      "a moved vignette is still caught through the noise")

print("\n10b) the noise floor is scaled to the comparison it judges")
# Each half of the reference night averages FEWER frames than the maps in
# the real comparison, so the raw half spread overstates the true noise —
# measured at sqrt(2) for equal counts.  _floor_rescale maps it back.
fns["math"] = math
rescale = fns["_floor_rescale"]
check(abs(rescale(1, 1, 2, 2) - math.sqrt(0.5)) < 1e-12,
      "a 2-frame night split 1/1: factor sqrt(1/2)")
check(abs(rescale(4, 4, 8, 8) - math.sqrt(0.5)) < 1e-12,
      "an 8-frame night split 4/4: same sqrt(1/2)")
check(rescale(8, 8, 8, 8) == 1.0,
      "both halves at the per-night cap: the halves carry the same noise "
      "as the full maps, factor exactly 1")
check(abs(rescale(2, 3, 5, 5)
          - math.sqrt((1 / 5 + 1 / 5) / (1 / 2 + 1 / 3))) < 1e-12,
      "an odd split follows the general 1/n formula")
check(rescale(4, 4, 8, 2) > 1.0,
      "a sparse OTHER night raises the floor — its map is noisier than "
      "the reference's halves")
# End to end, the way the run does it: base night of 5 frames, halves of
# 2 and 3, judged against another 5-frame night.  The scaled floor has to
# land NEAR the true comparison noise, where the raw one sat sqrt(2) high.
floor_raw = spread(night(2), night(3))
floor_scaled = floor_raw * rescale(2, 3, 5, 5)
print(f"   raw floor {floor_raw:.5f}, scaled {floor_scaled:.5f}, "
      f"true comparison noise {n_full:.5f}")
check(0.7 < floor_scaled / n_full < 1.35,
      "the scaled floor estimates the true comparison noise "
      f"(ratio {floor_scaled / n_full:.3f})")
check(floor_raw / n_full > 1.25,
      "where the raw half spread overstated it "
      f"(ratio {floor_raw / n_full:.3f})")

print("\n10c) _rebin_mean honours 'long side at most target'")
rebin = fns["_rebin_mean"]
for h, w in ((499, 400), (650, 500), (2000, 2000), (251, 200)):
    out = rebin(np.ones((h, w)), 250)
    check(max(out.shape) <= 250,
          f"{h}x{w} -> {out.shape}: long side within the target "
          "(floor division left these unbinned or oversized)")
check(rebin(np.ones((250, 200)), 250).shape == (250, 200),
      "an already-small frame is returned untouched")
check(float(rebin(np.full((499, 400), 7.0), 250).mean()) == 7.0,
      "block means preserve the level")

print("\n10d) _with_fits retries unmapped on astropy's memmap refusal")
# astropy raises "Cannot load a memory-mapped image ... Set memmap=False."
# at `.data` ACCESS time, after the open succeeded — so the retry has to
# repeat the whole read.  On one real run that error was swallowed ~130
# times and the flat consistency check silently skipped.  Executed against
# a stub fits module so the refusal is reproducible.
import contextlib

_wf_node = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "_with_fits")


class _StubFits:
    def __init__(self):
        self.calls = []

    def open(self, path, memmap=None, **kw):
        self.calls.append(memmap)

        @contextlib.contextmanager
        def cm():
            yield memmap                     # reader sees the memmap flag
        return cm()


_stub = _StubFits()
_wf_ns = {"fits": _stub}
exec("from __future__ import annotations\n"
     + ast.get_source_segment(src, _wf_node), _wf_ns)
with_fits = _wf_ns["_with_fits"]

REFUSAL = ("Cannot load a memory-mapped image: BZERO/BSCALE/BLANK header "
           "keywords present. Set memmap=False.")


def refusing_reader(mapped):
    if mapped:
        raise ValueError(REFUSAL)
    return "payload"


_stub.calls.clear()
got = with_fits("x.fit", refusing_reader)
check(got == "payload" and _stub.calls == [True, False],
      "the refusal at read time triggers ONE unmapped reopen "
      f"(calls: {_stub.calls})")

_stub.calls.clear()
got = with_fits("x.fit", lambda mapped: "fine")
check(got == "fine" and _stub.calls == [True],
      "a clean read stays mapped — no second open")

_stub.calls.clear()
try:
    with_fits("x.fit", lambda mapped: (_ for _ in ()).throw(
        ValueError("some other problem")))
    check(False, "an unrelated ValueError must propagate")
except ValueError:
    check(_stub.calls == [True],
          "an unrelated ValueError propagates without a retry")

print("\n10e) _connection_dead tells a dead link from a refusal")
# sirilpy wraps socket deaths into CommandError with the OS text kept, so
# the type alone cannot identify them.  These are the two messages from
# the real run that cascaded through every fallback.


class _StubConnErr(Exception):
    pass


_cd_ns = {"SirilConnectionError": _StubConnErr}
_marks_node = next(n for n in tree.body if isinstance(n, ast.Assign)
                   and getattr(n.targets[0], "id", "")
                   == "_CONNECTION_DEAD_MARKS")
_cd_node = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef)
                and n.name == "_connection_dead")
exec("from __future__ import annotations\n"
     + ast.get_source_segment(src, _marks_node) + "\n"
     + ast.get_source_segment(src, _cd_node), _cd_ns)
conn_dead = _cd_ns["_connection_dead"]

check(conn_dead(Exception(
    "Error in cmd(): Error in _send_command(): [Errno 32] Broken pipe")),
    "a broken pipe inside sirilpy's wrapper text is a dead link")
check(conn_dead(Exception(
    "Error in cmd(): Error receiving data: Connection closed during data "
    "transfer")),
    "so is a connection closed mid-transfer")
check(conn_dead(_StubConnErr("whatever the message")),
      "and SirilConnectionError is one by type, whatever it says")
check(not conn_dead(Exception("Unknown command: seqfoo")),
      "a plain refusal is NOT — the fallback chains stay in charge")
check(not conn_dead(Exception("could not open file lights_00001.fit")),
      "neither is an unreadable frame")


# ---------------------------------------------------------------------------
print("\n1.7.15 — the observing night is the one the frame itself records")
# `_night_key` was computed for every frame during discovery and then read
# by nothing: every night decision went through the date FOLDER instead, so
# a session crossing midnight was split in two and half its lights were
# paired against the wrong flats.  `_night_of` is the single rule now.
_night_of = ns["_night_of"]
LIGHT = "/data/2026-08-13/LIGHT/M16/HA/sub.fits"    # folder says the 13th
FLAT = "/data/2026-08-12/FLAT/HA/flat.fits"         # folder says the 12th
# ...but the light was taken at 01:20, i.e. during the night of the 12th.
hdr = {LIGHT: ns["_night_key"]("2026-08-13T01:20:00"),
       FLAT: ns["_night_key"]("2026-08-12T20:40:00")}
check(hdr[LIGHT] == "2026-08-12" and hdr[FLAT] == "2026-08-12",
      "noon-to-noon puts a dusk flat and a post-midnight light in one night")
check(_night_of(LIGHT, hdr) == _night_of(FLAT, hdr),
      "so the two now match, where the folder names never could")
check(_night_of(LIGHT, {}) != _night_of(FLAT, {}),
      "without the map they fall back to the folders and disagree — the "
      "behaviour every release up to 1.7.12 had")
check(_night_of(LIGHT, None) == "2026-08-13",
      "no map at all: the folder date, unchanged")
check(_night_of("/data/2026-09-01/x.fits", hdr) == "2026-09-01",
      "a path the map does not know falls back per frame, not wholesale")
check(_night_of("/nowhere/x.fits", {}) == "",
      "and a path with no date anywhere answers empty, as before")
check(_night_of(LIGHT, {LIGHT: ""}) == "2026-08-13",
      "an unreadable DATE-OBS (empty entry) falls back too")


print("\n1.7.15 — the flat map is built on the size the night agrees on")
# The reference size came from the FIRST frame read, so one mixed-binning
# frame at the head of the list made the outlier the reference and skipped
# every ordinary frame behind it -- the night was then compared on a map
# built from the one frame that did not belong.  The warning fired either
# way, which is how it looked handled.
_BIG = np.full((600, 600), 1000.0, dtype=np.float32)
_SMALL = np.full((300, 300), 1000.0, dtype=np.float32)
_PLANES = {}
ns["_with_fits"] = lambda path, reader, **kw: _PLANES[path]
_flat_shape = ns["_flat_shape"]

for name, arr in (("big", _BIG), ("small", _SMALL)):
    for i in range(8):
        _PLANES[f"{name}{i}"] = arr
big7 = [f"big{i}" for i in range(7)]

for label, paths in (("outlier first", ["small0"] + big7),
                     ("outlier last", big7 + ["small0"]),
                     ("outlier in the middle", big7[:3] + ["small0"]
                      + big7[3:])):
    st = {}
    m = _flat_shape(paths, limit=8, stats=st)
    check(st == {"used": 7, "skipped": 1},
          f"{label}: the seven agreeing frames are the ones averaged")
    check(m is not None, f"{label}: and a map comes back")

st = {}
_flat_shape(big7, limit=8, stats=st)
check(st == {"used": 7, "skipped": 0}, "a clean night skips nothing")
st = {}
_flat_shape(["small0"], limit=8, stats=st)
check(st == {"used": 1, "skipped": 0},
      "a night that is ALL one unusual size is not thrown away")
st = {}
_flat_shape(["small0", "small1", "big0", "big1"], limit=8, stats=st)
check(st["used"] == 2, "an even split keeps two, not one")
check(_flat_shape(["small0", "small1", "big0", "big1"], limit=8).shape
      == _flat_shape(["big0", "big1"], limit=8).shape,
      "and the tie goes to the larger, i.e. unbinned, image")
check(_flat_shape([], limit=8) is None, "no frames at all -> None")
st = {}
check(_flat_shape([], limit=8, stats=st) is None and st["used"] == 0,
      "and the stats still come back initialised, never stale")

print("\n1.7.15 — GESDT falls back to the band BELOW it")
_rf, _ra = ns["_rejection_fallback"], ns["_rejection_args"]
gesdt = _ra(100, True)[0]
check(gesdt[:2] == ["rej", "g"], "100 frames really are in the GESDT band")
fb = _rf(gesdt)
check(fb is not None and fb[0] == ["rej", "winsorized", "3", "3"],
      "an older Siril refusing `g` retries with winsorized")
check(fb[0] == _ra(GESDT_MIN := 30, True)[0],
      "which is exactly what _rejection_args gives the frames just short "
      "of GESDT — the tier below, as both call sites always claimed")
check(_rf(_ra(400, True)[0]) is None,
      "linear fit is never swapped — it is the band ABOVE GESDT")
for n in (2, 8, 20, 400):
    check(_rf(_ra(n, True)[0]) is None,
          f"n={n}: nothing but GESDT is ever retried with another algorithm")
check(_rf(_ra(50, False)[0]) is None,
      "and 'no rejection' is never quietly re-enabled")

print("\n1.7.15 — a WCS and a distortion-aware WCS are different facts")
_hdr: dict = {}
ns_sip = {"_read_header": lambda path: _hdr.get(path)}
for _n in tree.body:
    if isinstance(_n, ast.FunctionDef) and _n.name == "_has_sip":
        exec("from __future__ import annotations\n"
             + ast.get_source_segment(src, _n), ns_sip)
has_sip = ns_sip["_has_sip"]
_hdr["linear"] = {"CTYPE1": "RA---TAN", "CRVAL1": 308.7, "CD1_1": 1e-4}
_hdr["sip"] = dict(_hdr["linear"], A_ORDER=3, B_ORDER=3)
_hdr["ctype"] = {"CTYPE1": "RA---TAN-SIP", "CRVAL1": 308.7}
_hdr["bonly"] = {"CTYPE1": "RA---TAN", "B_ORDER": 2}
check(has_sip("sip") is True,
      "SIP order keywords are what Siril writes, and what is asked for")
check(has_sip("ctype") is True,
      "a CTYPE suffix from another writer counts too")
check(has_sip("bonly") is True,
      "half a pair is still distortion — never treat it as linear and "
      "overwrite it")
check(has_sip("linear") is False,
      "a plain TAN solution is linear — exactly what the composite "
      "inherits, and what SPCC warns about")
check(has_sip("missing") is False,
      "an unreadable header means 'assume linear': one re-solve costs "
      "seconds, a skipped one costs the colour calibration")

print("\n1.7.19 — the field of view is read, never assumed")
scale, fov = ns["_pixel_scale_deg"], ns["_fov_arcmin"]
# The real NGC 6946 Ha master, the frame the warning actually fires on:
# 382 mm at 3.76 um is 2.03"/px, and 2985 px of that is 101'.  This is
# the one number the warning is allowed to print.
NINA = {"FOCALLEN": 382.0, "XPIXSZ": 3.76, "NAXIS1": 2985, "NAXIS2": 2980}
probe("scale from focal length + pitch", scale, NINA,
      check=lambda d: abs(d * 3600 - 2.030) < 0.005)
probe("field of the stacked master", fov, NINA,
      check=lambda a: 100.5 <= a <= 101.5)
# A solved master states the scale itself, and that answer wins.
probe("CDELT1 beats the focal-length arithmetic", scale,
      dict(NINA, CDELT1=-1.0 / 3600),
      check=lambda d: abs(d * 3600 - 1.0) < 1e-6)
# CD1_1 ALONE understates a rotated field, and every frame that went
# through seqapplyreg is rotated: this run's masters sit at -43.8 deg,
# where cos(43.8) = 0.72.  The column length is the scale.
rot = {"CD1_1": 1e-4 * math.cos(math.radians(43.8)),
       "CD2_1": 1e-4 * math.sin(math.radians(43.8)),
       "NAXIS1": 1000, "NAXIS2": 1000}
probe("a rotated CD matrix is measured by its column length", scale, rot,
      check=lambda d: abs(d - 1e-4) < 1e-9)
# Absent is an answer.  A default focal length here would put an invented
# field into the one message whose subject is not inventing things.
for bad, why in (({"NAXIS1": 100, "NAXIS2": 100}, "no scale of any kind"),
                 ({"FOCALLEN": 0, "XPIXSZ": 3.76}, "a zero focal length"),
                 ({"FOCALLEN": "n/a", "XPIXSZ": 3.76}, "a corrupt keyword"),
                 ({"FOCALLEN": 382.0}, "no pixel pitch")):
    check(fov(bad) == 0.0 and scale(bad) == 0.0, f"0.0, not a guess, on {why}")

print("\n1.7.19 — the RBF warning states its condition and both cases")
rbf = ns["_rbf_narrowband_advice"]
# The bug: "on a target THIS SIZE most of what it removes is your signal",
# said on the strength of the FILTER alone.  On NGC 6946 -- 11' of galaxy
# in 101' of sky -- that sentence told the user to switch off the model the
# constants block calls "clearly better" for exactly that case.
said = rbf("master", 101.0)
check("this size" not in said,
      "no claim about a target size the script never measured")
check("95%" in said and "18%" in said,
      "the measurement keeps the condition it was measured under")
check("COMPACT" in said and "better model" in said,
      "the case where RBF is the RIGHT choice is named too")
check("cannot tell the two apart" in said,
      "and the script says plainly that it cannot decide this")
check("101'" in said, "the field of view is the one size it may state")
check("99.9%" in said and "100%" not in said,
      "the polynomial figure is not rounded up to a flat 100%")
blind = rbf("composite")
check("could not be read" in blind and "' across" not in blind,
      "an unreadable field is said, not replaced by a default")
for who in ("master", "composite"):
    check(rbf(who, 12.0).startswith(f"This {who} is line emission"),
          f"the {who} is named as the thing being described")

print("\n1.7.20 — the results folder is Stacked, at the level the user picks")
import tempfile
odir, olev = ns["_output_dir"], ns["_output_levels"]
check(ns["STACKS_DIRNAME"] == "Stacked", "the results folder is called Stacked")
with tempfile.TemporaryDirectory() as tmp:
    # Astro-PM: [Root]/[Site - Telescope - Camera]/[Target]/Originals, with
    # Processed and Stacked as Originals' siblings.
    proj = os.path.join(tmp, "Site - RC10 - ASI6200", "NGC 1499")
    orig = os.path.join(proj, "Originals")
    os.makedirs(os.path.join(orig, "Session 1"))
    check(odir(orig, 0) == os.path.join(orig, "Stacked"),
          "level 0 keeps the old place: inside the selected folder")
    check(odir(orig, 1) == os.path.join(proj, "Stacked"),
          "level 1 from Originals is <Target>/Stacked, where Astro-PM wants it")
    check([lv for lv, _ in olev(orig, 3)] == [0, 1, 2, 3],
          "every level that exists and is writable is offered")
    site = os.path.dirname(proj)
    check([lv for lv, _ in olev(orig, 3, writable=lambda p: p != site)]
          == [0, 1],
          "the walk stops at the first folder a run could not write into")
    check([lv for lv, _ in olev(orig, 3, writable=lambda p: False)] == [0],
          "level 0 stays offered even when nothing above can be written")
check(odir("/a", 9) == os.path.join(os.sep, "Stacked"),
      "an out-of-range level stops at the filesystem root, never wraps")

skip, looks = ns["_skip_in_discovery"], ns["_looks_like_results"]
with tempfile.TemporaryDirectory() as tmp:
    old = os.path.join(tmp, "before_1720")
    os.makedirs(os.path.join(old, "output", "masters"))
    user = os.path.join(tmp, "user")
    os.makedirs(os.path.join(user, "output"))
    open(os.path.join(user, "output", "L_0001.fits"), "w").close()
    apm = os.path.join(tmp, "apm")
    os.makedirs(os.path.join(apm, "Stacked", "Session 1"))
    check(all(skip(tmp, n) for n in ("Stacked", "stacked", "STACKED")),
          "Stacked is pruned in any letter case")
    check(skip(old, "output"),
          "an 'output' written before 1.7.20 is still pruned — the rename "
          "must not feed its masters back in as light frames")
    check(not skip(user, "output"),
          "an 'output' holding only lights is scanned — pruning by name "
          "used to hide them silently")
    check(not skip(apm, "Originals") and not skip(apm, "Processed"),
          "Astro-PM's other folders are not touched by the pruning")
    check(not looks(os.path.join(apm, "Stacked")),
          "an Astro-PM Stacked folder with nothing of ours in it is not "
          "mistaken for our results by the picker guard")
    for marker, make in (("calib", os.makedirs),
                         ("output.md", lambda p: open(p, "w").close()),
                         ("commands.ssf", lambda p: open(p, "w").close())):
        d = os.path.join(tmp, f"m_{marker}", "Stacked")
        os.makedirs(d)
        make(os.path.join(d, marker))
        check(looks(d), f"{marker} marks a folder as our results")

print("\n1.7.20 — a filter without flats is named")
nf = ns["_filters_without_flats"]
check(nf({"HA": {}, "OIII": {}, "SII": {}}, {"HA": {}, "OIII": {}}) == ["SII"],
      "the NGC 7380 case: SII is the one without flats")
check(nf({"HA": {}}, {"HA": {}, "RED": {}}) == [],
      "flats for a filter with no lights are not a gap")
check(nf({"B": {}, "A": {}}, None) == ["A", "B"],
      "no flats at all names every filter, sorted")
check(nf(None, {"HA": {}}) == [], "no lights, nothing to name")

print("\n1.7.20 — a calibration master must still fit its frames")
fr, stale = ns["_frame_record"], ns["_calib_master_stale"]
sizes = {}
def _size(p):
    return sizes[p]
oiii = [f"/a/OIII/flat_{i:05d}.fit" for i in range(1, 21)]
for p in oiii:
    sizes[p] = 36201600
now = fr(oiii, _size)
check(len(now) == 20 and now == sorted(now), "the record is sorted, one row per frame")
check(stale(now, None, 12) == "built from 12 frames, 20 found now",
      "the NGC 7380 case: a 12-frame master with 20 flats found, no record")
check(stale(now, None, 20) == "" and stale(now, None, None) == "",
      "an older master is reused when STACKCNT agrees, or cannot be read")
twelve = fr(oiii[:12], _size)
check(stale(now, twelve, 12) == "8 frame(s) added since it was built",
      "with a record, the change is named")
check(stale(now, now, 99) == "", "the record decides over STACKCNT")
swapped = [[f"other_{i:05d}.fit", 36201600] for i in range(20)]
check(stale(now, swapped, 20).startswith("20 frame(s) added and 20 removed"),
      "a swapped set of the same size is caught — STACKCNT alone could not")
resized = [[n, s + 1] for n, s in now]
check("different size" in stale(now, resized, 20),
      "a frame re-exported under the same name is caught")
night_a = [f"/n1/flat_{i:05d}.fit" for i in range(1, 11)]
night_b = [f"/n2/flat_{i:05d}.fit" for i in range(1, 11)]
for p in night_a + night_b:
    sizes[p] = 1000
both = fr(night_a + night_b, _size)
check(stale(both, fr(night_a, _size), None) == "10 frame(s) added since it was built",
      "per-night folders reusing flat_00001.fit still count twice")
check(fr(["/x/gone.fit"], lambda p: (_ for _ in ()).throw(OSError())) == [["gone.fit", -1]],
      "an unreadable size is recorded as -1, not raised")

print("\n1.8.0 — the NINA-PM manifest")
# The LDN1228 export exactly as NINA-PM wrote it, and a discovery result
# built from its own file names, so every light and flat is "on disk".
FIX = os.path.join(HERE, "fixtures", "LDN1228-LRGB.svenesis-monotrain.json")
load = ns["_load_manifest"]
man, problem = load(FIX)
check(man is not None and problem == "", "the LDN1228 manifest loads")
ROOT = "/data/LDN1228/Originals"


def _scan(m, extra_light=None, extra_flat=None):
    groups, flats = {}, {}
    for lt in m["lights"]:
        p = f"{ROOT}/{lt['night']}/LIGHT/{lt['filter']}/{lt['file']}"
        g = groups.setdefault(lt["filter"], {
            "files": [], "by_exp": {}, "sample": {}, "info": {},
            "dates": [], "exps": [], "exp_total": 0.0})
        g["files"].append(p)
        g["by_exp"].setdefault(float(lt["exposureS"]), []).append(p)
    if extra_light:
        filt, name, exp = extra_light
        p = f"{ROOT}/x/LIGHT/{filt}/{name}"
        groups[filt]["files"].append(p)
        groups[filt]["by_exp"].setdefault(exp, []).append(p)
    for fs in m["flatSets"]:
        for f in fs["flats"]:
            p = f"{ROOT}/{fs['flatsNight']}/FLAT/{fs['filter']}/{f}"
            flats.setdefault(fs["filter"], {
                "files": [], "info": {"filter": fs["filter"], "exp_s": 3.0},
                "date": ""})["files"].append(p)
    if extra_flat:
        flats[extra_flat[0]]["files"].append(
            f"{ROOT}/old/FLAT/{extra_flat[0]}/{extra_flat[1]}")
    return groups, {"flat": flats, "darkflat": {}, "dark": {}, "bias": {}}


groups, calib = _scan(man, ("RED", "stray.fits", 180.0), ("RED", "old.fits"))
before = copy.deepcopy((groups, calib))
apply_m = ns["_apply_manifest"]
v = apply_m(groups, calib, {}, man)
r = v["report"]
check((groups, calib) == before, "the scan itself is left untouched")
check(r["listed"] == 518 and r["matched"] == 518,
      "all 518 listed lights are matched by file name")
check(len(r["rejected"]) == 26
      and all(x["reason"] == "stars" for x in r["rejected"]),
      "the 26 frames NINA-PM rejected are found, with their reason")
counts = {f: len(g["files"]) for f, g in v["groups"].items()}
check(counts == {"LUMINOS": 247, "RED": 78, "GREEN": 84, "BLUE": 84},
      "rejected frames leave the stack; the unlisted RED one stays")
check(r["unlisted"] == ["stray.fits"] and r["unlisted_kept"],
      "a light the full manifest does not list is named and kept")
red = v["groups"]["RED"]
check(red["exp_total"] == 78 * 180.0 and red["exps"] == [180.0],
      "integration time follows the frames that are left")
check(v["flats_by_night"], "the manifest assigns the flats per night")
fl = v["calib"]["flat"]
check({f: len(g["files"]) for f, g in fl.items()}
      == {"BLUE": 125, "GREEN": 75, "LUMINOS": 175, "RED": 100},
      "each filter's flats are exactly the files of its assigned sets")
check(r["flats_unused"] == 1, "a flat in no assigned set is counted, not used")
night = ns["_night_of"]
lum = v["groups"]["LUMINOS"]
check(lum["dates"] == ["2026-10-08", "2026-10-09", "2026-10-10",
                       "2026-10-11", "2026-10-14", "2026-10-16",
                       "2026-10-17"],
      "the lights' nights come from their flat sets")
fs3 = [p for p in fl["LUMINOS"]["files"] if "_FLAT_" in p
       and night(p, v["nights"]) == "2026-10-08"]
check(len(fs3) == 25, "a flat's night is the night of the set it belongs to")
check(len(r["flips"]) == 3, "the three meridian flips are carried")
check(r["metrics"]["LUMINOS"]["n"] == 247
      and r["metrics"]["LUMINOS"]["guiding_high"] == 13,
      "conditions are summarised over the frames that are stacked")

v2 = apply_m(groups, calib, {}, man, drop_rejected=False)
check(len(v2["groups"]["LUMINOS"]["files"]) == 266
      and not v2["report"]["rejected_dropped"],
      "switched off, rejected frames are stacked — and still listed")

# Catch-up flats: lights of one night calibrated with flats of a later one.
cu = copy.deepcopy(man)
fs = next(f for f in cu["flatSets"] if f["id"] == "fs-0019")
fs["flatsNight"], fs["catchUp"] = "2026-10-18", True
g2, c2 = _scan(cu)
v3 = apply_m(g2, c2, {}, cu)
late = [p for p in v3["calib"]["flat"]["RED"]["files"] if "/2026-10-18/" in p]
red17 = [p for p in v3["groups"]["RED"]["files"] if "/2026-10-17/" in p]
check(len(late) == 25 and red17
      and {night(p, v3["nights"]) for p in late + red17} == {"2026-10-18"},
      "catch-up flats taken a night later pair with the lights they serve")
check(v3["groups"]["RED"]["light_nights"][-1] == "2026-10-17",
      "while the table still shows the night the lights were taken")
check(any(x["catch_up"] for x in v3["report"]["flat_sets"]["RED"]),
      "and the report marks the set as a catch-up")

# A subset export: an unlisted light is left out on purpose.
sub = copy.deepcopy(man)
sub["options"]["nights"] = ["2026-10-08"]
check(ns["_manifest_is_subset"](sub) and not ns["_manifest_is_subset"](man),
      "a manifest limited to some nights is recognised as a subset")
v4 = apply_m(groups, calib, {}, sub)
check("stray.fits" in v4["report"]["unlisted"]
      and len(v4["groups"]["RED"]["files"]) == 77,
      "a subset leaves unlisted lights out, so a stand repeats exactly")
noRej = copy.deepcopy(man)
noRej["options"]["includeRejected"] = False
check(ns["_manifest_is_subset"](noRej),
      "an export without the rejected frames is a subset too")

# The header wins over the manifest, and says so.
mm = copy.deepcopy(man)
mm["lights"][0]["filter"], mm["lights"][1]["exposureS"] = "RED", 30
v5 = apply_m(groups, calib, {}, mm)
check(len(v5["report"]["mismatch"]) == 2
      and len(v5["groups"]["LUMINOS"]["files"]) == 247,
      "a filter or exposure disagreement is reported; the header decides")

# A light without a flat set is named per night.
nf = copy.deepcopy(man)
for lt in nf["lights"]:
    if lt["filter"] == "BLUE" and lt["night"] == "2026-10-16":
        lt["flatSet"] = None
v6 = apply_m(groups, calib, {}, nf)
check(v6["report"]["no_flat_set"] == {"BLUE": ["2026-10-16"]},
      "lights without a flat set are named by filter and night")

# Mosaic: one panel per run.
mo = copy.deepcopy(man)
mo["project"]["panels"].append({"name": "P2", "index": 1, "deleted": False})
for lt in mo["lights"][:10]:
    lt["panel"] = "P2"
check(ns["_manifest_panels"](mo) == ["Main", "P2"],
      "panels with lights come in project order")
check(ns["_manifest_panels"](man) == ["Main"], "LDN1228 is a single field")
v7 = apply_m(groups, calib, {}, mo, panel="Main")
p2_ok = sum(1 for lt in mo["lights"][:10] if lt["status"] == "ok")
check(sum(v7["report"]["other_panels"].values()) == 10
      and sum(len(g["files"]) for g in v7["groups"].values())
      == 492 - p2_ok,
      "the other panel's lights are left for their own run")
v8 = apply_m(groups, calib, {}, mo, panel="P2")
check(sum(len(g["files"]) for g in v8["groups"].values()) == p2_ok
      and v8["report"]["listed"] == 10,
      "and the second panel's run takes exactly its own")
check(v8["report"]["unlisted"] == ["stray.fits"]
      and v8["report"]["unlisted_why"] == "mosaic",
      "a light of no known panel goes into no panel's run, and is named")

# Choosing among several manifests: by the frames they list.
names = {os.path.basename(p) for g in groups.values() for p in g["files"]}
other = {"lights": [{"file": "M31_LIGHT_0001.fits"}]}
pick = ns["_manifest_pick"]
path, chosen, notes = pick([(0, "/a/x" + ns["MANIFEST_SUFFIX"], other),
                            (1, "/a/LDN" + ns["MANIFEST_SUFFIX"], man)], names)
check(chosen is man and any("none of the light" in n for n in notes),
      "the manifest that lists these frames wins; the other is named")
path, chosen, notes = pick([(1, "/a/one.json", man), (1, "/b/two.json", man)],
                           names)
check(chosen is None and any("equally well" in n for n in notes),
      "two equally good manifests at one level are a tie, not a guess")
path, chosen, _n = pick([(0, "/a/near.json", man), (1, "/b/far.json", man)],
                        names)
check(path == "/a/near.json", "at equal evidence the nearer one is used")

# Finding them: the selected folder and the folders above it.
with tempfile.TemporaryDirectory() as tmp:
    orig = os.path.join(tmp, "LDN1228", "Originals")
    os.makedirs(orig)
    target_m = os.path.join(tmp, "LDN1228", "LDN1228" + ns["MANIFEST_SUFFIX"])
    with open(target_m, "w") as fh:
        fh.write("{}")
    open(os.path.join(orig, "notes.json"), "w").close()
    found = ns["_manifest_candidates"](orig)
    check(found == [(1, target_m)],
          "an Astro-PM manifest one level up is found; other JSON is not")
    bad = os.path.join(orig, "broken" + ns["MANIFEST_SUFFIX"])
    with open(bad, "w") as fh:
        fh.write("{not json")
    check(load(bad)[0] is None and "could not be read" in load(bad)[1],
          "a broken file is refused with a reason, never raised")
    with open(bad, "w") as fh:
        json.dump({"format": "something-else", "version": 1}, fh)
    check("is not a" in load(bad)[1], "a foreign JSON file is refused")
newer = copy.deepcopy(man)
newer["version"] = 2
check(any("newer than this script" in t for t, _k in
          ns["_manifest_log_lines"](dict(r, version=2))),
      "a newer format version is read, and said")

# Roles and SPCC.
over = ns["_manifest_role_overrides"]
check(over(man) == ({}, []),
      "a manifest whose names already work changes no role")
odd = {"filters": [{"shortName": "NB1", "filterType": "narrowband",
                    "centerWavelengthNm": 656.3, "bandwidthNm": 3},
                   {"shortName": "LUMINOS", "filterType": "narrowband",
                    "centerWavelengthNm": 567.5, "bandwidthNm": 295}]}
roles, notes = over(odd)
check(roles == {"NB1": "ha"},
      "an unknown narrowband name is mapped by its centre wavelength")
check(any("295 nm wide" in n for n in notes),
      "L marked narrowband (the first LDN1228 export) is caught, not obeyed")
spcc = ns["_manifest_spcc"]
SENS = {"Sony IMX411/455/461/533/571"}
FILT = {"Antlia L", "Antlia R", "Antlia G", "Antlia B"}
sp = spcc(man, SENS, FILT)
check((sp["sensor"], sp["red"], sp["green"], sp["blue"])
      == ("Sony IMX411/455/461/533/571", "Antlia R", "Antlia G", "Antlia B")
      and not sp["notes"],
      "the LDN1228 SPCC names are taken when Siril's tables hold them")
wrong = copy.deepcopy(man)
wrong["equipment"]["spccSensor"] = "IMX533"
sp = spcc(wrong, SENS, FILT)
check(sp["sensor"] == "" and any("IMX533" in n for n in sp["notes"]),
      "the OSC trap 'IMX533' is refused, and the settings' sensor stays")
sp = spcc(man)
check(sp["sensor"] and any("unchecked" in n for n in sp["notes"]),
      "without Siril's tables the names are used, and that is said")
nb = {"filters": [{"shortName": "OIII", "filterType": "narrowband",
                   "centerWavelengthNm": 500.7, "bandwidthNm": 4.5}]}
check(spcc(nb, SENS, FILT)["bandwidths"] == {"oiii": 4.5},
      "a narrowband filter contributes its bandwidth by line")

# The report never raises and says the headline facts.
lines = ns["_manifest_log_lines"](dict(r, spcc=spcc(man, SENS, FILT)),
                                  "/x/LDN1228" + ns["MANIFEST_SUFFIX"])
text = "\n".join(t for t, _k in lines)
check("518 of 518" in text and "26 light(s) rejected" in text
      and "LUMINOS 19× stars" in text,
      "the log names the counts and the reasons")
check(all(k in ("ok", "info", "warn") for _t, k in lines),
      "every line carries a known colour")
md = "\n".join(ns["_manifest_md"](r, "LDN1228" + ns["MANIFEST_SUFFIX"]))
check("stars 772 < 804" in md and "fs-0003" in md
      and "| --- |" in md, "output.md lists each rejected frame and each set")
check(ns["_manifest_md"]({}) == [] and ns["_manifest_log_lines"]({})[0],
      "no manifest, no section; an empty report still logs one line")

print("\n1.8.0 — Siril's log as it really arrives: NUL-padded, and German")
ld, pf, pa = ns["_log_delta"], ns["_parse_spcc_fit"], ns["_parse_align_pairs"]
# The LDN1228 breadcrumb: head intact, tail anchor gone, last line '\x00'.
before = "x\n" * 500 + "\x00" * 300
after = "x\n" * 500 + "Befehlsausführung: spcc\nK0: 1.000\n" + "\x00" * 120
d = ld(before, after)
check(d is not None and d.startswith("Befehlsausführung: spcc"),
      "NUL padding no longer hides the step's own lines")
check(ld(None, after, ("Running command: spcc", "Befehlsausführung: spcc"))
      .startswith("\nK0"), "a localised marker is found among several")
check(ld(None, "abc", "") is None and ld(None, None, "x") is None,
      "no marker, no snapshot: still None, never a guess")
DE = """19:16:32: 893 Sterne von der Berechnung ausgeschlossen
19:16:32: Bild R/G = 0.017823 + 1.146376 * Katalog R/G (Sigma: 0.177796)
19:16:32: Bild B/G = 0.047100 + 1.033429 * Katalog B/G (Sigma: 0.065609)
19:16:32: Ich habe eine Lösung für die Farbkalibrierung mit 1117 Sternen gefunden. Faktoren:
19:16:32: K0: 1.000
19:16:32: Die photometrische Farbkorrektur scheint eine ungenaue Lösung gefunden zu haben"""
fit = pf(DE)
check(fit.get("sigma") == {"R/G": 0.177796, "B/G": 0.065609}
      and fit.get("stars") == 1117 and fit.get("excluded") == 893
      and fit.get("imprecise"),
      "a German SPCC fit is read like an English one (LDN1228 lines)")
ALIGN = """Versuch #1: Nach der Sequenzanalyse wählen wir das Bild 4 als neue Referenz für die Registrierung
Bringe Sterne in Bild 1 zur Deckung: erledigt
Korrespondierende Paare: 1334
Bringe Sterne in Bild 3 zur Deckung: erledigt
Korrespondierende Paare: 1796"""
check(pa(ALIGN, {1: "BLUE", 3: "LUMINOS", 4: "RED"})
      == ({"BLUE": 1334, "LUMINOS": 1796}, "RED"),
      "and so are the German star-pair counts")

print("\n1.8.0 — flat sets that list the same files make one master (IC434)")
ic, problem = load(os.path.join(HERE, "fixtures", "IC434.svenesis-monotrain.json"))
check(ic is not None and not problem, "the IC434 manifest loads")
gi, ci = _scan(ic)
for fk, grp in ci["flat"].items():          # one copy per file, as on disk
    grp["files"] = list(dict.fromkeys(grp["files"]))
vi = apply_m(gi, ci, {}, ic)
ri = vi["report"]
check(ri["flats_missing"] == 0 and not ri["flats_shared"],
      "no flat counted missing or shared because three sets list it")
oiii = vi["groups"]["OIII"]
check(oiii["dates"] == ["2026-10-19"] and len(vi["calib"]["flat"]["OIII"]
                                              ["files"]) == 25,
      "OIII's three sets of one flat run are one calibration part")
check(oiii["light_nights"] == ["2026-10-19", "2026-10-20", "2026-10-21"],
      "and the lights still say which nights they came from")
red = vi["groups"]["RED"]
red16 = [p for p in red["files"] if night(p, vi["nights"]) == "2026-10-16"]
check(len(red16) == 2,
      "the two single RED frames sharing one flat set calibrate together")
text = "\n".join(t for t, _k in ns["_manifest_log_lines"](ri))
check("OIII 1, reused for 2 more night(s)" in text,
      "the log says one master serves three nights")
check(len(ri["rejected"]) == 6, "the six HA frames NINA-PM rejected are found")

# flatsInProjectFolder: borrowed DrZi1 flats copied under IC434's name,
# as the 14:33 IC434 export lists them.
cp = ic
check(all(len(fs.get("flatsInProjectFolder") or []) == len(fs["flats"])
          for fs in cp["flatSets"]),
      "the IC434 export lists a project-folder name for every flat")
ic = copy.deepcopy(cp)
for fs in ic["flatSets"]:
    fs.pop("flatsInProjectFolder", None)
    fs.pop("darkFlatsInProjectFolder", None)
gc, cc = _scan(ic)
for grp in cc["flat"].values():
    grp["files"] = [p.replace("/DrZi1_", "/IC434_") for p in
                    dict.fromkeys(grp["files"])]
vc = apply_m(gc, cc, {}, cp)
check(vc["report"]["flats_missing"] == 0
      and vc["report"]["flats_copied"] == 4 * 25,   # 0010/0012 = 0009
      "flats on disk only as the project-folder copy are found by that name")
vo = apply_m(gc, cc, {}, ic)
check(vo["report"]["flats_missing"] == 6 * 25,
      "without the list the same folder misses the six borrowed sets' files")
part = copy.deepcopy(cp)
part["flatSets"][0]["flatsInProjectFolder"][0] = None
del part["flatSets"][1]["flatsInProjectFolder"]
gp, cpp = _scan(ic)
vp = apply_m(gp, cpp, {}, part)
check(vp["report"]["flats_missing"] == 0,
      "an empty entry or a missing list (mosaic) falls back to `flats`")

print()
if fails:
    print(f"{len(fails)} FAILURE(S)")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ALL HELPER PROBES PASSED")
