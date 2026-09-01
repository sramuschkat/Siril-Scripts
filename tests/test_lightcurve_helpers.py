"""The pure helpers of Svenesis LightCurve, EXECUTED.

Every function that decides a number is checked against input whose answer
is known independently: the J2000 epoch, sec z at 30 degrees, a synthetic
transit of a stated depth, and a run with no transit in it at all.

The two checks that matter most are the ones a light-curve tool can fail
silently: that a noise-only run is NOT called a detection, and that the
airmass detrend does not eat the transit depth it is supposed to preserve.

Run:  python3 tests/test_lightcurve_helpers.py

The two-sided baseline test has its own section (7b): a monotonic trend is
the failure mode this tool is most likely to meet in real data, and the
suite caught it in the first version of the significance test.
"""
import ast
import datetime
import math
import os
import re
import sys
import textwrap

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "Svenesis-LightCurve.py")
src = open(SRC).read()
tree = ast.parse(src)

ns = {"np": np, "math": math, "re": re, "datetime": datetime, "os": os,
      "csv": __import__("csv"), "shutil": __import__("shutil"),
      "io": __import__("io"), "json": __import__("json"),
      "urllib": __import__("urllib.request").request and
                __import__("urllib.parse") or __import__("urllib")}
for node in tree.body:                       # module constants
    if isinstance(node, ast.Assign):
        try:
            exec(compile(ast.Module([node], []), "<c>", "exec"), ns)
        except Exception:                    # noqa: BLE001 — needs a name we skip
            pass
for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        exec("from __future__ import annotations\n"
             + ast.get_source_segment(src, node), ns)

fails = []


def check(ok, msg, detail=""):
    print(("   ok   " if ok else "   FAIL ") + msg
          + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(msg)


print("1) Julian dates and coordinates")
jd = ns["_jd_from_dateobs"]
check(abs(jd("2000-01-01T12:00:00") - 2451545.0) < 1e-9,
      "the J2000.0 epoch is 2451545.0 exactly")
check(abs(jd("2026-08-12T21:00:00") - 2461265.375) < 1e-6,
      "a 21:00 UT observation lands on .375 of a day")
for bad in ("", None, "not a date", "2026-13-45T99:99:99"):
    check(not np.isfinite(jd(bad)), f"{bad!r} yields NaN, never a wrong date")

sx = ns["_sexagesimal"]
check(abs(sx("12:34:56.7") - 12.582417) < 1e-5, "sexagesimal splits on colons")
check(abs(sx("-13 47 31") - (-13.791944)) < 1e-5, "and keeps the sign")
check(abs(sx("274.6875") - 274.6875) < 1e-9, "a bare decimal passes through")
check(not np.isfinite(sx("")), "empty is NaN, not zero — zero is a real angle")

print("\n2) airmass follows Kasten & Young, not sec z")
am = ns["_airmass"]
check(abs(am(90.0) - 1.0) < 5e-4, "unity at the zenith")
for alt in (60.0, 45.0, 30.0):
    secz = 1.0 / math.sin(math.radians(alt))
    got = am(alt)
    print(f"   alt {alt:4.0f}°  sec z {secz:6.3f}   K&Y {got:6.3f}")
    check(got <= secz + 1e-6, f"at {alt:.0f}° K&Y does not exceed sec z")
check(am(30.0) > 1.99, "and stays close to it high up")
check(not np.isfinite(am(-5.0)), "below the horizon is NaN, not a huge number")
alt = ns["_altitude_deg"]
check(not np.isfinite(alt(jd("2026-08-12T21:00:00"), 274.7, -13.8, None, 8.0)),
      "a missing site yields NaN rather than a silent default")

print("\n3) Siril's light_curve.dat, including the JD offset")
parse = ns["_parse_light_curve_dat"]
import shutil as _sh
import tempfile
tmp = tempfile.mkdtemp()
plain = os.path.join(tmp, "plain.dat")
with open(plain, "w") as fh:
    fh.write("# JD_UT V-C err\n2461265.4000 -0.0021 0.0031\n"
             "2461265.4007 0.0102 0.0030\n")
t, m, e, _d = parse(plain)
check(t.size == 2 and abs(t[0] - 2461265.4) < 1e-9, "two rows, full JD")
check(abs(m[1] - 0.0102) < 1e-9 and abs(e[0] - 0.0031) < 1e-9,
      "magnitude and error columns land in the right arrays")

offs = os.path.join(tmp, "offset.dat")
with open(offs, "w") as fh:
    fh.write("#JD_UT (+ 2461265) V-C err\n0.4000 -0.0021 0.0031\n")
t2, _m2, _e2, _d2 = parse(offs)
check(abs(t2[0] - 2461265.4) < 1e-6,
      "the declared day offset is added back", str(t2))
# What this section never asked, and section 8a2 now does: what happens
# when the column ALREADY carries the full JD and the header declares an
# offset anyway.  That is what Siril actually writes, and adding the two
# put the real run in the year 8600.
check(parse(os.path.join(tmp, "nope.dat"))[0].size == 0,
      "a missing file gives empty arrays, not an exception")

print("\n4) the trapezoid recovers a transit it was given")
fit = ns["fit_transit"]
_TMPL = ns["ld_template"](0.10, 0.0)


def shape(t, t0, duration, _ingress=None):
    """A limb-darkened transit of unit depth — the model the fit searches.

    The suite used to synthesise trapezoids, which flattered a trapezoid
    fitter. It now injects the real shape, so a signal the fit cannot make
    would show up here rather than being hidden by a matching assumption.
    """
    return ns["ld_shape"](t, t0, duration, _TMPL)
rng = np.random.default_rng(20260818)
t = np.linspace(0.0, 8.0 / 24.0, 480)
TRUE_T0, TRUE_DUR, TRUE_DEPTH = 4.0 / 24.0, 2.5 / 24.0, 0.015
truth = TRUE_DEPTH * shape(t, TRUE_T0, TRUE_DUR, 0.15)
# A limb-darkened transit has a ROUNDED bottom, not a flat one, so the
# sampled maximum sits just below the nominal depth — by 0.4% here at 480
# points. That rounding is the whole reason for the model change: a
# trapezoid fitted to it comes out 5-6% too shallow.
check(0.97 * TRUE_DEPTH <= float(np.max(truth)) <= TRUE_DEPTH + 1e-12,
      "the shape peaks at the nominal depth, and never above it",
      f"{float(np.max(truth))/TRUE_DEPTH:.4f} of depth")
check(float(np.min(truth)) == 0.0, "and exactly 0 outside the event")

for label, noise, t0_tol_min, depth_tol in (
        ("1 mmag scatter", 0.001, 2.0, 1.0),
        ("4 mmag scatter", 0.004, 5.0, 2.0)):
    r = fit(t, truth + rng.normal(0, noise, t.size))
    dt_min = abs(r["t0"] - TRUE_T0) * 24 * 60
    dd = abs(r["depth_mmag"] - TRUE_DEPTH * 1000)
    print(f"   {label:16s} T0 {dt_min:4.1f} min off, depth "
          f"{r['depth_mmag']:5.1f} mmag, {r['significance']:5.1f} sigma")
    check(dt_min < t0_tol_min, f"{label}: mid-time within {t0_tol_min} min")
    check(dd < depth_tol, f"{label}: depth within {depth_tol} mmag")
    check(r["detected"], f"{label}: and it is claimed")

print("\n5) a run with NO transit must not be called one")
claimed = 0
for k in range(12):
    r = fit(t, rng.normal(0, 0.004, t.size))
    if r is not None and r["detected"]:
        claimed += 1
check(claimed == 0, f"none of 12 pure-noise runs was claimed", f"{claimed} were")
# A BRIGHTENING must never come back as a transit depth.  The invariant is
# not "and it is not claimed" -- a negative significance already fails that
# on its own, which made the earlier form of this check vacuous.  The
# invariant is that the DEPTH ITSELF is never negative, whatever the data.
for label, series in (("a pure brightening", -truth),
                      ("a rising ramp", np.linspace(0, -0.02, t.size)),
                      ("noise only", np.zeros(t.size))):
    r = fit(t, series + rng.normal(0, 0.002, t.size))
    check(r is None or r["depth_mag"] > 0,
          f"{label}: the fitted depth is positive or there is no fit",
          "None" if r is None else f"{r['depth_mmag']:.2f} mmag")
    check(r is None or not r["detected"],
          f"{label}: and nothing is claimed")

print("\n6) the airmass detrend does not eat the depth")
detrend = ns["airmass_detrend"]
X = 1.0 + 1.6 * np.linspace(0, 1, t.size) ** 2          # target setting
TRUE_SLOPE = 0.030
y = truth + TRUE_SLOPE * (X - X[0]) + rng.normal(0, 0.003, t.size)
naive = float(np.polyfit(X, y, 1)[0])
_d, trimmed, _b = detrend(y, X)
print(f"   true {TRUE_SLOPE:.4f}   naive {naive:.4f} "
      f"({100*(naive/TRUE_SLOPE-1):+.0f}%)   trimmed {trimmed:.4f} "
      f"({100*(trimmed/TRUE_SLOPE-1):+.0f}%)")
check(abs(trimmed - TRUE_SLOPE) < abs(naive - TRUE_SLOPE),
      "the trimmed baseline beats the all-points fit")
check(abs(trimmed / TRUE_SLOPE - 1) < 0.05,
      "and lands within 5% of the truth")

# The second pass earns its keep where the FIRST one runs out of untouched
# baseline to trim to.  Below ~50% duty cycle the two are interchangeable and
# comparing them on one noise draw measures the draw, not the method -- so
# the claim is made where it is actually a claim, and averaged.
def _slope_errors(run_h, dip_h, draws=12):
    r = np.random.default_rng(4242)
    tt = np.linspace(0, run_h / 24, int(60 * run_h))
    tr = 0.015 * shape(tt, float(np.median(tt)), dip_h / 24, 0.15)
    XX = 1.0 + 1.6 * np.linspace(0, 1, tt.size) ** 2
    e1, e2 = [], []
    for _ in range(draws):
        yy = tr + TRUE_SLOPE * (XX - XX[0]) + r.normal(0, 0.003, tt.size)
        dd1, ss1, _ = detrend(yy, XX)
        e1.append(abs(ss1 - TRUE_SLOPE))
        ff = fit(tt, dd1)
        _dd2, ss2, _ = detrend(yy, XX, ff["oot_mask"])
        e2.append(abs(ss2 - TRUE_SLOPE))
    return float(np.mean(e1)) / TRUE_SLOPE, float(np.mean(e2)) / TRUE_SLOPE

lo1, lo2 = _slope_errors(8, 2)      # 25% duty — both should be fine
md1, md2 = _slope_errors(6, 3)      # 50% duty — where the TRIM decides
hi1, hi2 = _slope_errors(4, 3)      # 75% duty — pass 1 is out of baseline
print(f"   25% duty: pass1 {lo1:6.1%}  pass2 {lo2:6.1%}")
print(f"   50% duty: pass1 {md1:6.1%}  pass2 {md2:6.1%}")
print(f"   75% duty: pass1 {hi1:6.1%}  pass2 {hi2:6.1%}")
check(lo1 < 0.03 and lo2 < 0.03,
      "at 25% duty both passes are within 3% of the true slope")
# 50% is the band that pins the ITERATIVE trim specifically.  Without it the
# final +/-2 MAD re-admission alone is a sigma clip seeded from the
# all-points line -- which still looks fine at 25% duty (1.5%) and is
# already hopeless here (9.9%, i.e. no better than the plain fit). Leaving
# this band untested let a mutation that disabled the trim loop pass the
# whole suite.
check(md1 < 0.03,
      "at 50% duty the iterative trim still holds the slope to 3%",
      f"{md1:.1%}")
check(hi1 > 0.05,
      "at 75% duty the blind pass really does fall apart — the constant's "
      "comment is not decoration", f"{hi1:.1%}")
check(hi2 < hi1 / 2.0,
      "and the out-of-transit anchor at least halves that error",
      f"{hi1:.1%} -> {hi2:.1%}")
check(ns["BLIND_DETREND_BREAKDOWN"] <= 0.60,
      "the documented breakdown is not optimistic about pass 1")

# On dip-free data the trimming must NOT bias the slope: it selects on the
# residual, not on airmass.
clean = TRUE_SLOPE * (X - X[0]) + rng.normal(0, 0.003, t.size)
_dc, sc, _ = detrend(clean, X)
check(abs(sc / TRUE_SLOPE - 1) < 0.03,
      "trimming leaves the slope unbiased when there is no dip",
      f"{sc:.4f}")

# No airmass spread means no ramp to remove — and a line through a vertical
# stripe is arbitrary, so it must decline rather than invent one.
flat = np.full(t.size, 1.2)
_df, sf, _ = detrend(y, flat)
check(sf is None, "a constant airmass yields no fit at all")
check(detrend(y, None)[1] is None, "and neither does a missing one")

print("\n7) significance uses the right standard error")
sig = ns["stacked_significance"]
n = 400
tt = np.linspace(0, 1, n)
dip = np.where(np.abs(tt - 0.5) < 0.1, 0.01, 0.0)      # 20% duty
s_short = sig(tt, dip, 0.5, 0.2, 0.002)
# Same dip, same noise, but four times the out-of-transit baseline.
tt2 = np.linspace(0, 4, 4 * n)
dip2 = np.where(np.abs(tt2 - 2.0) < 0.1, 0.01, 0.0)
s_long = sig(tt2, dip2, 2.0, 0.2, 0.002)
print(f"   20% duty {s_short:7.1f} sigma   ·   5% duty (4x the baseline) "
      f"{s_long:7.1f} sigma")
check(s_long < s_short * 1.6,
      "a longer baseline does not inflate the significance the way "
      "sqrt(N_total) would", f"{s_short:.1f} -> {s_long:.1f}")
check(sig(tt, dip, 0.5, 5.0, 0.002) == 0.0,
      "an all-inside window is a baseline offset, not a detection")
check(sig(tt, dip, 0.5, 0.2, 0.0) == 0.0,
      "zero noise is refused rather than dividing by it")

print("\n7b) a monotonic trend is not a transit")
# The failure this test exists for: on a ramp the fitter puts its window
# over the faint half, the POOLED contrast is genuinely large, and a
# one-sided test reports a trend as a detection.  Comparing each side of
# the window separately is what separates the two.
ramp = np.linspace(0.0, 0.02, n)              # star fades steadily
one_sided = ((float(np.mean(ramp[np.abs(tt - 0.75) < 0.1]))
              - float(np.mean(ramp[np.abs(tt - 0.75) >= 0.1]))) / 0.002
             * math.sqrt(80 * 320 / 400.0))
two_sided = sig(tt, ramp, 0.75, 0.2, 0.002)
print(f"   window over the faint half:  pooled {one_sided:+6.1f} sigma   "
      f"two-sided {two_sided:+6.1f} sigma")
check(one_sided > 3.0,
      "the pooled test really would have claimed this ramp",
      f"{one_sided:.1f}")
check(two_sided < 0.0,
      "the two-sided test refuses it outright", f"{two_sided:.1f}")
for centre in (0.3, 0.5, 0.7):
    check(sig(tt, ramp, centre, 0.2, 0.002) < 3.0,
          f"no window on the ramp reaches 3 sigma (centre {centre})",
          f"{sig(tt, ramp, centre, 0.2, 0.002):.1f}")
# A real dip still clears the bar comfortably, which is the other half of
# the claim -- a test that rejects everything is not a test.
check(sig(tt, dip, 0.5, 0.2, 0.002) > 10.0,
      "while a genuine dip is still far above the floor",
      f"{sig(tt, dip, 0.5, 0.2, 0.002):.1f}")
# No baseline on one side means the question cannot be answered at all.
check(sig(tt, dip, 0.05, 0.2, 0.002) == 0.0,
      "a transit clipped by the start of the run is refused, not guessed")
check(sig(tt, dip, 0.95, 0.2, 0.002) == 0.0,
      "and so is one clipped by the end")

print("\n7c) a meridian flip is measured, not missed")
spread = ns["rotation_spread_deg"]


class _H:
    def __init__(self, deg):
        r = math.radians(deg)
        self.h00, self.h10 = math.cos(r), math.sin(r)


# Verbatim from a real 178-frame WASP-75b run: the first ~21 frames sit at
# 0 deg, the rest at +179.88 after the mount flipped.
real = [_H(-0.001)] * 21 + [_H(179.878)] * 157
got = spread(real)
print(f"   real WASP-75b run: {got:.2f} deg  (flip threshold "
      f"{ns['FLIP_ROTATION_DEG']:.0f})")
check(abs(got - 179.879) < 0.01, "the 180 deg flip is measured", f"{got}")
check(got >= ns["FLIP_ROTATION_DEG"], "and it trips the threshold")

# An EQ mount tracking well shows a fraction of a degree; an alt-az drifts
# a few.  Neither may be reported as a flip.
check(spread([_H(0.0), _H(0.3), _H(-0.2)]) < ns["FLIP_ROTATION_DEG"],
      "ordinary tracking jitter is not a flip")
check(spread([_H(0.0), _H(4.0), _H(-3.0)]) < ns["FLIP_ROTATION_DEG"],
      "nor is alt-az field rotation across a night")

# The wrap: -179.9 and +179.9 are 0.2 deg apart, not 359.8.  Without the
# circular difference a run that straddles the wrap reports a phantom flip.
straddle = spread([_H(179.95), _H(-179.95)])
print(f"   straddling the +/-180 wrap: {straddle:.2f} deg")
check(straddle < 1.0, "the wrap is handled on the circle", f"{straddle}")

check(spread([]) is None and spread([None]) is None,
      "nothing to compare yields None, not zero")
check(spread([_H(0.0)]) is None, "and one frame is not a spread")
# An unset registration is all zeros -- that is missing data, not 0 degrees.
class _Zero:
    h00 = h10 = 0.0
check(spread([_Zero(), _Zero()]) is None,
      "an unset homography is skipped, not read as zero rotation")

print("\n8) comparison stars are filtered for the right reasons")
choose = ns["choose_comparison_stars"]


class _Star:
    def __init__(self, x, y, snr, sat=False, mag=0.0):
        self.xpos, self.ypos, self.SNR, self.has_saturated = x, y, snr, sat
        self.mag = mag


stars = [
    _Star(500, 500, 300),               # the target itself
    _Star(505, 505, 400),               # far too close
    _Star(900, 900, 500, sat=True),     # saturated
    _Star(100, 900, 5),                 # too faint
    _Star(900, 100, 250),               # good
    _Star(100, 100, 120),               # good
    _Star(700, 300, 60),                # good
]
chosen, rejected, note = choose(stars, (500, 500), 5, fwhm_px=3.0,
                               min_snr=20.0)
reasons = " | ".join(r[2] for r in rejected)
print(f"   chose {len(chosen)}, rejected {len(rejected)}: {reasons}")
check(len(chosen) == 3, "the three usable stars are chosen", str(len(chosen)))
check([c[2] for c in chosen] == sorted([c[2] for c in chosen], reverse=True),
      "brightest first")
check(any("saturated" in r[2] for r in rejected), "the saturated one is named")
check(any("from the target" in r[2] for r in rejected), "so is the close one")
check(any("SNR" in r[2] for r in rejected), "and the faint one")
check(all((c[0], c[1]) != (500, 500) for c in chosen),
      "the target never ends up in its own ensemble")

check("SNR" in note, "and it says it ranked by SNR", note)

# The first real run: 866 stars, and `findstar` had left SNR at zero for
# every one of them -- Siril fills that field during PHOTOMETRY, not
# during detection.  Reading zero as "pure noise" rejected the entire
# field and the run died with 0 usable comps out of 865.
blind = [_Star(500, 500, 0.0, mag=-9.0)]                      # target
blind += [_Star(100 + 40 * i, 900, 0.0, mag=-8.0) for i in range(6)]
blind += [_Star(100 + 40 * i, 1400, 0.0, mag=-2.0) for i in range(20)]
c2, r2, note2 = choose(blind, (500, 500), 5, fwhm_px=1.91, min_snr=20.0)
print(f"   SNR unpopulated: chose {len(c2)}, rejected {len(r2)}")
print(f"   {note2}")
check(len(c2) == 5, "an unmeasured SNR field does not empty the ensemble",
      f"chose {len(c2)}")
check("magnitude" in note2, "and the fallback is declared, not silent", note2)
check(all("fainter" in r[2] or "were needed" in r[2] for r in r2),
      "the ones dropped are the faint ones, for that stated reason")
# A run reported "6 chosen, 668 rejected" out of 864 detections and said
# nothing about the remaining 189, which reads as a field that barely
# yielded a comp.  Chosen plus not-used must account for every star but the
# target, or the tally is a different claim than the one it looks like.
check(len(c2) + len(r2) == len(blind) - 1,
      "chosen + not-used accounts for every star but the target",
      f"{len(c2)} + {len(r2)} vs {len(blind) - 1}")
check(any("were needed" in r[2] for r in r2),
      "and a star that passed every filter but was surplus says so")
# The window must cut BOTH ways: a comp far brighter than the target is a
# saturation risk the flag does not always catch.
glare = [_Star(500, 500, 0.0, mag=-4.0)] + \
        [_Star(100 + 40 * i, 900, 0.0, mag=-12.0) for i in range(6)]
c3, r3, _ = choose(glare, (500, 500), 5, fwhm_px=1.91, min_snr=20.0)
check(len(c3) == 0 and all("brighter" in r[2] for r in r3),
      "and a far brighter star is refused too")

print("\n8a0) significance is corrected for correlated noise")
rnb = ns["red_noise_beta"]
fit0 = ns["fit_transit"]
rg = np.random.default_rng(7)
NN, sp = 240, 4.0 / 24
tt0 = np.linspace(0.0, sp, NN)
dur0 = 2.0 / 24

# White noise must cost nothing -- a correction that always fires is a
# tax, not a test.
bw, _rows = rnb(tt0, rg.normal(0, 0.01, NN), dur0)
print(f"   white noise      beta = {bw:.2f}")
check(bw < 1.2, "white residuals give beta near 1", f"{bw:.3f}")

# Correlated noise must be caught, and the size of the catch matters.
wn = rg.normal(0, 0.01, NN + 40)
rednoise = np.convolve(wn, np.ones(20) / 20, "valid")[:NN]
rednoise *= 0.01 / rednoise.std()
br, rows = rnb(tt0, rednoise, dur0)
print(f"   correlated noise beta = {br:.2f} over {len(rows)} timescales")
check(br > 2.0, "correlated residuals give a large beta", f"{br:.3f}")
check(len(rows) >= 3, "and the ladder reports several timescales")

check(rnb(tt0, rg.normal(0, 0.01, NN), 0.0)[0] == 1.0,
      "a zero duration cannot define a timescale, so beta is 1")
check(rnb(tt0[:8], rg.normal(0, 0.01, 8), dur0)[0] == 1.0,
      "too few points give beta 1 rather than a fluctuation")
# Beta may never REWARD a run: residuals that bin down faster than white
# noise are a small-sample fluke, not evidence of sub-Poisson data.
best = rnb(tt0, np.zeros(NN) + rg.normal(0, 1e-12, NN), dur0)[0]
check(best >= 1.0, "beta is clamped at 1 and can only weaken a claim",
      f"{best:.3f}")

# The case the whole correction exists for: correlated noise and NO
# transit, which the white-noise significance would have reported.
f_red = fit0(tt0, rednoise)
print(f"   pure red noise, no transit: {f_red['significance_white']:.1f}s "
      f"white -> {f_red['significance']:.1f}s corrected")
check(f_red["significance"] < f_red["significance_white"],
      "the correction weakens a red-noise-only run")
check(not f_red["detected"],
      "and that run is NOT reported as a detection",
      f"{f_red['significance']:.1f}s")

# A real transit in clean data must survive.  The assertion is on the
# DECISION, not on beta: measured over 60 realisations of this exact
# setup, beta has median 1.00 but a tail to 1.53, and 8% of draws exceed
# 1.2 -- so a bound on a single draw would be a flaky test rather than a
# statement about the method.  What does hold every time is that no real
# transit was pushed below the floor.
dip0 = np.where(np.abs(tt0 - sp / 2) < 0.5 / 24, 0.012, 0.0)
lost = 0
for seed in range(12):
    f_ok = fit0(tt0, dip0 + np.random.default_rng(seed).normal(0, 0.008, NN))
    if f_ok and f_ok["significance_white"] >= 3.0 > f_ok["significance"]:
        lost += 1
check(lost == 0,
      "across twelve noise draws the correction never kills a real transit",
      f"{lost} lost")

print("\n8a1) too few points is a refusal, not a null result")
ft = ns["fit_transit"]
tt = np.linspace(0.0, 0.2, 4)
check(ft(tt, np.array([0.1, -0.2, 0.4, -0.4])) is None,
      "four points cannot constrain a five-parameter trapezoid")
check(ft(np.linspace(0, 0.2, 9), np.zeros(9)) is None,
      "nor can nine")
# Ten is the stated floor, and it must actually pass -- a guard that
# refuses everything is as wrong as one that refuses nothing.
tt2 = np.linspace(0.0, 0.25, 60)
dip = np.where(np.abs(tt2 - 0.125) < 0.04, 0.02, 0.0)
got = ft(tt2, dip)
check(got is not None, "but sixty points with a dip ARE fitted", str(got))
check(got["detected"], "and that dip is detected", f"{got['significance']:.1f}s")
# A perfectly flat curve legitimately returns None: no node has a
# positive depth, and the fit refuses to invent one.  Getting this
# backwards the first time is what the assertion is for.
check(ft(tt2, np.zeros_like(tt2)) is None,
      "a flat curve yields no fit at all, since depth cannot be positive")

print("\n8a2) Siril's light_curve.dat, with both of its traps")
parse = ns["_parse_light_curve_dat"]
import tempfile


def _parse_text(text):
    with tempfile.NamedTemporaryFile("w", suffix=".dat", delete=False) as fh:
        fh.write(text)
        path = fh.name
    try:
        return parse(path)
    finally:
        os.unlink(path)


# Verbatim shape of the real WASP-75b file: the header declares an offset
# AND the column already carries the full JD.
jd, mag, err, dropped = _parse_text(
    "#JD_UT (+ 2461267)\n"
    "# JD_UT V-C err\n"
    "2461267.816702 nan 3.74397\n"
    "2461267.881108 -6.58917 0.672294\n"
    "2461267.906306 -6.94601 1.06631\n")
print(f"   {jd.size} measured, {dropped} unmeasured, JD {jd[0]:.5f}")
check(dropped == 1, "the nan row is dropped, not counted", str(dropped))
check(jd.size == 2, "and only real measurements remain", str(jd.size))
check(2.4e6 < jd[0] < 2.5e6,
      "the declared offset is NOT added on top of an absolute JD",
      f"{jd[0]:.5f}")
# Adding it would have given 4922534 -- the year 8600, which is exactly
# what astropy reported as "date outside the range 1900-2100 AD".
check(jd[0] < 3.0e6, "so the run cannot land in the year 8600", f"{jd[0]:.1f}")
check(abs(mag[0] + 6.58917) < 1e-5,
      "the surviving magnitudes line up with their own times")

# The other convention must still work: a relative column plus an offset.
jd2, _m2, _e2, _d2 = _parse_text(
    "#JD_UT (+ 2460000)\n1267.816702 -6.5 0.1\n1267.881108 -6.6 0.1\n")
print(f"   relative column -> JD {jd2[0]:.5f}")
check(abs(jd2[0] - 2461267.816702) < 1e-6,
      "a relative column DOES get the offset added", f"{jd2[0]:.6f}")

# A file where every row failed must report its rows, not look empty.
jd3, _m3, _e3, d3 = _parse_text(
    "#JD_UT (+ 2461267)\n2461267.8 nan 1.0\n2461267.9 nan 1.0\n")
check(jd3.size == 0 and d3 == 2,
      "an all-nan file reports its rows so the message can say why",
      f"{jd3.size} / {d3}")

print("\n8b) the light_curve command line Siril will actually accept")
lc = ns["light_curve_args"]

# The exact positions from the first real WASP-75b run.  Sent with three
# decimals, Siril answered "Command execution failed: invalid arguments"
# -- after logging the ring radii, so the error pointed at -autoring
# rather than at the coordinate that actually broke the parse.
args = lc("lights", 0, True, (1503.646, 1505.257),
          [(1878.489, 2094.754), (1684.483, 2903.578), (2489.626, 505.154)])
line = " ".join(args)
print(f"   {line}")
check(not re.search(r"=[\d,]*\.", line),
      "no coordinate carries a decimal point", line)
check("-at=1504,1505" in line, "the target rounds to the nearest pixel")
check(line.count("-refat=") == 3, "every comparison star is passed")
check(args[:3] == ["light_curve", "lights", "0"],
      "sequence and channel come first, in that order", str(args[:3]))
check(args[3].startswith("-at="),
      "the positions follow the channel directly — -autoring used to sit "
      "here and no longer does: measured against Siril 1.4.4, the flag "
      "makes light_curve abort on coordinates that are inside the image, "
      "and the caller sets the same radii with setphot instead (8r4)",
      str(args[3:5]))

plain = lc("lights", 1, False, (10.4, 20.6), [])
check("-autoring" not in plain and plain[2] == "1",
      "the flag is absent with the option off as with it on, and the "
      "channel is honoured", str(plain))
check(plain[-1] == "-at=10,21", "rounding is to nearest, not truncation",
      plain[-1])

print("\n8c) a poor frame yield is judged, not just counted")
yv = ns["photometry_yield_note"]

# The first real WASP-75b run: 35 of 178 frames survived, and Siril's own
# reason was "pixel out of range" -- PSF_ERR_INVALID_PIX_VALUE, a saturated
# pixel in the aperture.  That reads like a tracking fault and is an
# exposure fault.
sev, msg = yv(35, 178, True)
print(f"   35/178, saturated target -> [{sev}]")
check(sev == "bad", "a 20% yield on a saturated target is not 'ok'", sev)
check(msg and "SATURATED" in msg, "and saturation is named as the cause")
check(msg and "35 of 178" in msg, "with the actual numbers, not a percentage alone")

check(yv(35, 178, False)[0] == "bad",
      "a 20% yield is bad even when the target looks clean")
check(yv(170, 178, False) == ("ok", None),
      "a healthy run says nothing", str(yv(170, 178, False)))
check(yv(100, 178, False)[0] == "ok",
      "and just over half is still acceptable")

# Saturation must speak up even when the yield alone would have passed:
# the frames that survived are seeing-selected, which the count hides.
sev2, msg2 = yv(170, 178, True)
check(sev2 == "bad" and msg2 is not None,
      "a saturated target is reported even at a high yield", str(sev2))
check(yv(0, 0, False)[0] == "bad", "zero frames is not a division by zero")

print("\n8d) a target match is judged by its runner-up, not its distance")
pick2 = ns["pick_target"]


class _Sky:
    def __init__(self, x, y, ra, dec):
        self.xpos, self.ypos, self.ra, self.dec = x, y, ra, dec
        self.SNR, self.has_saturated, self.mag = 100.0, False, 0.0


# The real WASP-75b run matched 9.4" from the typed coordinates.  That is
# not by itself a problem -- it says as much about the precision of the
# coordinates as about the match.  What would be a problem is a second
# star at a comparable distance.
w = (342.3854, -10.6749)
cd = math.cos(math.radians(w[1]))
near = _Sky(1503.6, 1505.3, w[0] + 9.4 / 3600 / cd, w[1])
far = _Sky(1900.0, 1900.0, w[0] + 0.2, w[1] + 0.2)
note = pick2([near, far], "radec", want_radec=w)[2]
print(f"   {note}")
check("9.4" in note, "the separation is stated, not hidden")
check("AMBIGUOUS" not in note,
      "a lone match is not called ambiguous just for being 9.4 arcsec off")

rival = _Sky(1512.0, 1505.0, w[0] + 20.0 / 3600 / cd, w[1])
note2 = pick2([near, rival], "radec", want_radec=w)[2]
print(f"   {note2}")
check("AMBIGUOUS" in note2,
      "a comparably close second star IS called ambiguous", note2)
check("20.0" in note2, "and the runner-up's distance is given too")

# Pixel mode has to behave the same way -- same trap, same test.
# 4 px to the nearest, 8 px to the next -- ratio 2, inside the threshold.
px = [_Sky(100.0, 100.0, 0.0, 0.0), _Sky(104.0, 100.0, 0.0, 0.0)]
note3 = pick2(px, "pixel", want_xy=(96.0, 100.0))[2]
check("AMBIGUOUS" in note3 and "px" in note3,
      "pixel mode is judged the same way", note3)
check("AMBIGUOUS" not in pick2([px[0]], "pixel", want_xy=(96.0, 100.0))[2],
      "and a single candidate cannot be ambiguous")
# 4 px vs 16 px is ratio 4 -- outside the threshold, so NOT ambiguous.
# Getting this wrong the first time is what the assertion is for.
wide = [_Sky(100.0, 100.0, 0.0, 0.0), _Sky(112.0, 100.0, 0.0, 0.0)]
check("AMBIGUOUS" not in pick2(wide, "pixel", want_xy=(96.0, 100.0))[2],
      "a runner-up four times further away is not a rival")

print("\n8d2) the observatory position is read from the frames")
sfh = ns["site_from_header"]

# Verbatim from the WASP-75b subs.  The run had refused to convert times
# for want of a latitude that was sitting in all 178 files.
real = {"SITELAT": 31.5469444444444, "SITELONG": -99.3822222222222,
        "SITEELEV": 500.0, "SITENAME": "Starfront Building 8"}
got = sfh(real)
print(f"   {got}")
check(got is not None, "the real header is read")
check(abs(got[0] - 31.5469) < 1e-3 and abs(got[1] + 99.3822) < 1e-3,
      "latitude and longitude come through unchanged", str(got[:2]))
check(got[2] == 500.0, "and the elevation too")
check("Starfront" in got[3], "the site name is carried into the log line")

# 0..360 longitudes have to fold, or a US site reads as Asian.
folded = sfh({"SITELAT": 31.5, "SITELONG": 260.6})
check(folded and abs(folded[1] + 99.4) < 0.1,
      "a 0..360 longitude folds to east-negative", str(folded))

# Alternative keywords, since not every capture program writes SITELAT.
alt = sfh({"LAT-OBS": 50.0, "LONG-OBS": 8.0})
check(alt and alt[:2] == (50.0, 8.0), "LAT-OBS/LONG-OBS are accepted")

# Refusals must be refusals, not silent zeros -- a site at (0, 0) is in
# the Atlantic and would give a plausible-looking wrong airmass.
check(sfh(None) is None, "no header is None, not (0, 0)")
check(sfh({"SITELAT": 31.5}) is None, "a latitude alone is not a position")
check(sfh({"SITELAT": "n/a", "SITELONG": 8.0}) is None,
      "an unparsable latitude is refused")
check(sfh({"SITELAT": 991.0, "SITELONG": 8.0}) is None,
      "and so is one outside +/-90")
check(sfh({"SITELAT": 50.0, "SITELONG": 8.0})[2] == 0.0,
      "a missing elevation defaults to sea level, which costs microseconds")

print("\n8e) times reach BJD_TDB, the system every ephemeris is quoted in")
tob = ns["to_bjd_tdb"]

# The real WASP-75b night: 2026-08-14, target at 22h49m -10d40'.
jd = np.array([2461267.35, 2461267.40, 2461267.45])
bjd, note = tob(jd, 342.3854, -10.6749, 50.0, 8.0)
off = (bjd - jd) * 86400.0
print(f"   {note}")
print(f"   offset {off[0]:.1f} .. {off[-1]:.1f} s, "
      f"drift {off[-1] - off[0]:.2f} s across the run")
check(bjd is not None, "the conversion runs with astropy present")
check(400.0 < abs(off.mean()) < 600.0,
      "the correction is minutes, not seconds — this is why it matters",
      f"{off.mean():.1f} s")
check(abs(off[-1] - off[0]) < 2.0,
      "but it drifts under 2 s across a night, so the transit SHAPE is safe",
      f"{off[-1] - off[0]:.3f} s")
check(np.all(np.diff(bjd) > 0), "the conversion is monotonic in time")
# TDB-UTC alone is ~69 s; the barycentric term is the rest.  Both must be
# in there -- a conversion that forgot the barycentre would land near 69.
check(abs(off.mean()) > 100.0,
      "the barycentric term is present, not just TDB-UTC",
      f"{off.mean():.1f} s")

# Refusing is fine; refusing SILENTLY is not.  Every failure names itself.
for args, what in (((jd, None, None, 50.0, 8.0), "no target coordinates"),
                   ((jd, 342.0, -10.0, None, 8.0), "no site latitude"),
                   ((jd, 342.0, -10.0, 50.0, None), "no site longitude")):
    out, why = tob(*args)
    check(out is None and why, f"{what} is refused with a stated reason", why)

print("\n8f) a comparison star must be alone in its aperture")
# The radius is Siril's own geometry, not taste: `-autoring` sets the outer
# ring to 6.3 x FWHM, so two sky annuli stop touching at twice that.  A
# neighbour inside it contributes to the aperture AND to the sky estimate,
# and its share breathes with the seeing.
#
# An earlier version of this section also dropped a comp that had a
# BRIGHTER star within 5 x outer, on the theory that Siril's `-refat` search
# would lock onto the neighbour.  That rule is gone: Siril's own log puts
# the search box at `requested - 19` in both axes, and the positions that
# motivated the rule fall OUTSIDE that 38 px box, so a snap cannot be what
# produced them.  It cost 28% of a real field and changed none of them.
FW = 2.0                       # outer ring = 6.3 x FWHM = 12.6 px
pair = [_Star(500, 500, 0.0, mag=-9.0),          # target
        _Star(1000, 1000, 0.0, mag=-8.0),        # clear
        _Star(1400, 1400, 0.0, mag=-8.0),        # has company at 20 px
        _Star(1420, 1400, 0.0, mag=-8.5),        # ...mutually, so both go
        _Star(2000, 2000, 0.0, mag=-8.0),        # brighter star 50 px away
        _Star(2050, 2000, 0.0, mag=-8.6)]        # ...but that is not a fault
cc, rr, _ = choose(pair, (500, 500), 5, fwhm_px=FW, min_snr=20.0)
why = {(r[0], r[1]): r[2] for r in rr}
kept = [(c[0], c[1]) for c in cc]
print(f"   chose {len(cc)} of 5 candidates")
for k, v in why.items():
    print(f"   ({k[0]:.0f},{k[1]:.0f}) {v}")
check((1000, 1000) in kept, "an isolated star is kept")
check("annulus" in why.get((1400, 1400), ""),
      "a star with a neighbour inside its own annulus is dropped, and the "
      "reason names the annulus", why.get((1400, 1400), "KEPT"))
check("annulus" in why.get((1420, 1400), ""),
      "and so is its neighbour — overlap is mutual, not a contest",
      why.get((1420, 1400), "KEPT"))
check((2000, 2000) in kept and (2050, 2000) in kept,
      "a pair 50 px apart is left alone: outside the annulus there is no "
      "measured mechanism, and inventing one cost a quarter of a real field")

# The rule is worthless if it empties a normal field.  864 stars over
# 3008 px at FWHM 1.95 was the real run; mean nearest-neighbour spacing is
# about 51 px there, comfortably outside the 24.6 px annulus.
rng = np.random.default_rng(7)
xy = rng.uniform(0, 3008, size=(864, 2))
dense = [_Star(500, 500, 0.0, mag=-9.0)]
dense += [_Star(float(a), float(b), 0.0, mag=-8.0 - float(rng.uniform(0, 1)))
          for a, b in xy]
c4, r4, _ = choose(dense, (500, 500), 5, fwhm_px=1.95, min_snr=20.0)
survivors = len(c4) + sum(1 for r in r4 if "were needed" in r[2])
print(f"   real-density field: {survivors} of 864 stay isolated")
check(len(c4) == 5, "a field of real density still fills the ensemble")
check(survivors > 500, "and the rule costs a minority of the field, not most "
      "of it", f"{survivors} survivors")

print("\n8g) the target cannot be dropped, so its company is reported")
ns["LogColor"] = type("LC", (), {"SALMON": "salmon"})
crowd = ns["crowding_note"]
check(crowd([_Star(500, 500, 0.0, mag=-9.0),
             _Star(1500, 1500, 0.0, mag=-8.0)], 500, 500, 2.0) is None,
      "a clear target draws no comment")
near = crowd([_Star(500, 500, 0.0, mag=-9.0),
              _Star(515, 500, 0.0, mag=-8.0)], 500, 500, 2.0)
check(near and "annulus" in near[1],
      "a neighbour inside the annulus is named, with the trend it creates",
      near[1] if near else "silent")
# Two geometries, said apart: the first HAT-P-32 AAVSO run printed
# "sits 16 px away, inside the 15 px sky annulus" — a contradiction,
# because the check fires out to TWICE the radius (overlapping annuli).
_in = crowd([_Star(500, 500, 0.0, mag=-9.0),
             _Star(508, 500, 0.0, mag=-8.0)], 500, 500, 2.0)
check(_in and "inside the" in _in[1] and "overlaps" not in _in[1],
      "a neighbour truly inside the annulus says 'inside'")
_ov = crowd([_Star(500, 500, 0.0, mag=-9.0),
             _Star(515, 500, 0.0, mag=-8.0)], 500, 500, 2.0)
check(_ov and "overlaps" in _ov[1] and "inside the" not in _ov[1],
      "one between the radius and twice the radius says the annuli "
      "OVERLAP — not that it sits inside an annulus smaller than the "
      "distance itself")
check(crowd([_Star(500, 500, 0.0, mag=-8.0),
             _Star(540, 500, 0.0, mag=-9.0)], 500, 500, 2.0) is None,
      "a brighter star well outside the annulus draws no comment — the "
      "warning that used to fire here rested on a refuted mechanism")
check(crowd([], 500, 500, 2.0) is None, "an empty field is not a crowd")

print("\n8h) calibration is delegated to Siril, and never claimed falsely")
cargs = ns["calibration_args"]
iscal = ns["frames_are_calibrated"]
darknote = ns["dark_exposure_note"]

args, used = cargs("lights", flat="/m/flat.fit")
check(args is not None and args[0] == "calibrate" and args[1] == "lights",
      "a flat alone produces a calibrate command", " ".join(args or []))
# The WHOLE token is quoted, not just the path. Siril keeps a quote that
# starts after the "=" as part of the file name and then reports
# `"....fit".[any_allowed_extension] not found` — which reads like a
# missing master, not like a quoting bug, and cost a full run to find.
check('"-flat=/m/flat.fit"' in args and used == [("flat", "/m/flat.fit")],
      "the whole -flat= token is quoted, path included", " ".join(args))
check('-flat="/m/flat.fit"' not in args,
      "and never just the path — Siril would look for a file whose name "
      "starts with a quote")
check(any(a.startswith("-prefix=") for a in args),
      "and a prefix is set, so the calibrated sequence has its own name")
check("-cfa" not in args, "no debayer for a mono sensor by default")
check("-cfa" in cargs("lights", flat="/m/f.fit", cfa=True)[0],
      "-cfa -debayer only when the sensor is one-shot colour")
none_args, none_used = cargs("lights")
check(none_args is None and none_used == [],
      "with no master at all there is NO command — an empty calibrate would "
      "rewrite every frame and change nothing")
order = [a for a in cargs("l", bias="/b", dark="/d", flat="/f")[0]
         if a.startswith('"-bias') or a.startswith('"-dark')
         or a.startswith('"-flat')]
check(order == ['"-bias=/b"', '"-dark=/d"', '"-flat=/f"'],
      "bias, dark, flat are passed in that order", str(order))

# The header question has THREE answers.  N.I.N.A. writes neither CALSTAT
# nor a HISTORY card, so "no evidence" is not "not calibrated" -- claiming
# it would be a warning that cries wolf, and those get skipped past.
state, why = iscal({"IMAGETYP": "LIGHT"})
check(state is False and "CALSTAT" in why,
      "a raw light with nothing in the header is called raw", why)
state, why = iscal({"IMAGETYP": "LIGHT", "CALSTAT": "BDF"})
check(state is True and "bias" in why and "flat" in why,
      "CALSTAT=BDF settles it and spells out which steps", why)
state, why = iscal({"IMAGETYP": "LIGHT",
                    "HISTORY": ["Flat field correction applied"]})
check(state is True and "HISTORY" in why,
      "so does a HISTORY card naming the step", why)
check(iscal(None)[0] is None, "no header is unknown, not 'raw'")
check(iscal({"IMAGETYP": "FLAT"})[0] is None,
      "a frame that is not a light is not judged either way")
check(iscal({"IMAGETYP": "LIGHT", "CALSTAT": "  "})[0] is False,
      "a blank CALSTAT is no evidence, so the raw verdict still stands")

# The dark that silently does the wrong thing: right camera, right night,
# wrong exposure.  Siril subtracts it without comment.
ok, note = darknote({"EXPTIME": 3.0}, {"EXPTIME": 60.0})
print(f"   {note}")
check(ok is False and "3.0 s" in note and "60.0 s" in note,
      "a 3 s dark on 60 s lights is refused in words, with both numbers")
check("5%" in note, "and it quantifies what is actually removed", note)
check(darknote({"EXPTIME": 60.0}, {"EXPTIME": 60.0})[0] is True,
      "a matching dark passes")
check(darknote({"EXPTIME": 60.5}, {"EXPTIME": 60.0})[0] is True,
      "and header rounding does not trip it")
check(darknote({}, {"EXPTIME": 60.0})[0] is None,
      "an unreadable exposure is unknown, not fine")

# The wiring, not just the helper.  If `_calibrate` returned the calibrated
# sequence name and the caller dropped it on the floor, everything below
# would run on the UNCALIBRATED frames and every number in the report would
# still look perfectly reasonable.  That is exactly the class of bug a pure
# helper test cannot see, so it is asserted on the source.
run_fn = next(f for c in tree.body if isinstance(c, ast.ClassDef)
              and c.name == "LightCurveWorker"
              for f in c.body
              if isinstance(f, ast.FunctionDef) and f.name == "_run")
flow = ast.dump(run_fn)
check("_calibrate" in flow, "the run flow calls _calibrate at all")
assigned = [n for n in ast.walk(run_fn)
            if isinstance(n, ast.Assign)
            and isinstance(n.value, ast.Call)
            and isinstance(n.value.func, ast.Attribute)
            and n.value.func.attr == "_calibrate"
            and any(isinstance(t, ast.Name) and t.id == "seq" for t in n.targets)]
check(len(assigned) == 1,
      "and assigns its return value back to seq — otherwise registration "
      "would silently run on the uncalibrated frames",
      f"{len(assigned)} such assignments")
body_src = open(SRC).read()
i_link = body_src.index('"link", seq')
i_cal = body_src.index("seq = self._calibrate(")
i_reg = body_src.index("self._register(seq)")
check(i_link < i_cal < i_reg,
      "and it sits between link and register, in that order")

print("\n8j) calibration frames are FOUND, not demanded")
kindof = ns["classify_kind"]
pathof = ns["classify_path"]
sig = ns["calib_signature"]
sigmatch = ns["signature_matches"]
scan = ns["scan_calibration"]
pick = ns["choose_masters"]
roots_of = ns["calibration_roots"]

check(kindof("Dark Flat") == "darkflat" and kindof("DARK") == "dark",
      "a dark-flat is not read as a dark — it would be subtracted from the "
      "lights instead of from the flats")
check(kindof("Flat Field") == "flat" and kindof("BIAS") == "bias",
      "IMAGETYP is matched on substrings, since it is a type name")
check(kindof("") is None, "and an empty keyword decides nothing")
# The folder fallback must match WHOLE segments.
check(pathof("/data/Dark-Nebula/LIGHT/2026-08-14/L/x.fits") == "light",
      "a target called Dark-Nebula keeps its lights", 
      str(pathof("/data/Dark-Nebula/LIGHT/2026-08-14/L/x.fits")))
check(pathof("/data/WASP-75b/FLAT/2026-08-14/LUMINOS/x.fits") == "flat",
      "and N.I.N.A.'s upper-case FLAT folder is found")

# The real layout: lights three levels below the target folder, flats
# beside the LIGHT folder rather than anywhere near the lights.
import shutil as _sh
import tempfile
tmp = tempfile.mkdtemp()
lights = os.path.join(tmp, "WASP-75b", "LIGHT", "2026-08-14", "LUMINOS")
flats = os.path.join(tmp, "WASP-75b", "FLAT", "2026-08-14", "LUMINOS")
lib = os.path.join(tmp, "_CALIB", "DARK", "60.00s_G125")
for d in (lights, flats, lib):
    os.makedirs(d, exist_ok=True)
found = roots_of(lights, lib)
names = {os.path.basename(r) for r in found}
print(f"   roots: {sorted(names)}")
check("FLAT" in names,
      "the session flats are found from the lights folder alone — three "
      "levels up, beside the LIGHT folder", str(sorted(names)))
check(any(os.path.basename(r) == "60.00s_G125" for r in found),
      "and the library folder is added as given")
check("LIGHT" not in names,
      "the LIGHT folder itself is not scanned for calibration frames")

# Grouping and matching, with headers injected so no FITS is needed.
def _mk(path, kind, exp, gain=125, temp=-10.0, filt="LUMINOS", dims=(3008, 3008)):
    return {"path": path, "kind": kind, "exp_s": exp, "gain_v": gain,
            "temp_v": temp, "binning": 1, "dims": dims,
            "instrument": "Ares-M PRO", "filter": filt}

fake = {}
def _reader(path):
    return fake[path]

for i in range(5):
    fp = os.path.join(flats, f"f{i}.fits")
    open(fp, "w").close()
    fake[fp] = _mk(fp, "flat", 3.0)
for i in range(4):
    dp = os.path.join(lib, f"d{i}.fits")
    open(dp, "w").close()
    fake[dp] = _mk(dp, "dark", 60.0)
groups = scan(found, "LUMINOS", read=_reader)
check(len(groups.get("flat", [])) == 1 and len(groups["flat"][0]["files"]) == 5,
      "five flats of one signature form one group")
check(len(groups.get("dark", [])) == 1 and len(groups["dark"][0]["files"]) == 4,
      "and four darks another")

light = _mk("L", "light", 60.0)
chosen, notes = pick(groups, light)
for n in notes:
    print("   " + n)
check("dark" in chosen and "flat" in chosen,
      "a matching dark and flat are both selected")

# The case that actually applies to this data set.
bad = dict(groups)
bad["dark"] = [{"kind": "dark", "key": None, "files": ["a", "b", "c"],
                "info": _mk("a", "dark", 3.0)}]
chosen2, notes2 = pick(bad, light)
print("   " + [n for n in notes2 if "dark" in n][0])
check("dark" not in chosen2,
      "a 3 s dark is NOT applied to 60 s lights")
check(any("read noise" in n for n in notes2),
      "and the rejection says what the mismatch would have done, not just "
      "that two numbers differ")

# Temperature splits darks; it must not split bias.
warm = _mk("w", "dark", 60.0, temp=-20.0)
check(sig(_mk("c", "dark", 60.0), with_temp=True) != sig(warm, with_temp=True),
      "-10 C and -20 C darks never share a master — the average is correct "
      "for neither")
check(sig(_mk("c", "bias", 0.0), with_temp=False)
      == sig(_mk("d", "bias", 0.0, temp=-25.0), with_temp=False),
      "but bias is temperature-independent, so splitting it would only add "
      "noise")

ok, why = sigmatch(_mk("m", "dark", 60.0, dims=(3008, 3008)),
                   _mk("l", "light", 60.0, dims=(2048, 2048)))
check(ok is False and "size" in why, "a master of the wrong size is refused", why)
ok, why = sigmatch(_mk("m", "flat", 3.0), _mk("l", "light", 60.0),
                   check_exposure=False)
check(ok is True,
      "but a flat need not match the lights' exposure — a flat is a ratio", why)
ok, why = sigmatch({"instrument": "Ares-M PRO", "binning": 1},
                   {"instrument": "ASI2600MM", "binning": 1})
check(ok is False and "camera" in why,
      "and two different cameras never calibrate each other", why)
_sh.rmtree(tmp, ignore_errors=True)

print("\n8k) the scan is recursive, and knows a copy from an exposure")
split = ns["split_frames"]
gcal = ns["group_calibration"]
merge = ns["merge_calibration"]
fits_files = ns["_fits_files"]

tmp2 = tempfile.mkdtemp()
deep = os.path.join(tmp2, "WASP-75b", "LIGHT", "2026-08-14", "LUMINOS")
inflat = os.path.join(tmp2, "WASP-75b", "FLAT", "2026-08-14", "LUMINOS")
stale = os.path.join(deep, "_lightcurve", "process")
legacy = os.path.join(deep, "_flux", "lights")
for d in (deep, inflat, stale, legacy):
    os.makedirs(d, exist_ok=True)
for d in (deep, inflat, stale, legacy):
    for i in range(3):
        open(os.path.join(d, f"x{i}.fits"), "w").close()
seen = fits_files(tmp2)
print(f"   {len(seen)} FITS found under the project root")
check(len(seen) == 6,
      "the walk reaches lights three levels down AND the FLAT folder beside "
      "them — pointing at the project root is enough", f"{len(seen)} files")
check(not any(os.sep + "_lightcurve" + os.sep in f for f in seen),
      "this script's own working folder is never descended into")
check(not any(os.sep + "_flux" + os.sep in f for f in seen),
      "and neither is the one it used before it was renamed — a stale "
      "working folder re-ingests its own staged copies as subs")

# Duplicates: the failure this actually hit. A leftover working folder
# turned 178 subs into 534, and every copy would have entered the curve as
# an independent point, shrinking every error bar by root-3 for nothing.
def _lt(path, stamp, exp=60.0, filt="LUMINOS"):
    return {"path": path, "kind": "light", "exp_s": exp, "gain_v": 125,
            "temp_v": -10.0, "binning": 1, "dims": (3008, 3008),
            "instrument": "Ares-M PRO", "filter": filt, "date_obs": stamp}

real = [_lt(f"/L/{i:03d}.fits", f"2026-08-15T02:{i:02d}:00") for i in range(10)]
copies = [_lt(f"/L/_old/{i:03d}.fits", f"2026-08-15T02:{i:02d}:00")
          for i in range(10)]
kept, _c, note = split(real + copies, inside=True)
print("   " + note)
check(len(kept) == 10, "ten exposures copied twice stay ten points",
      f"{len(kept)} kept")
check(all("_old" not in k["path"] for k in kept),
      "and the originals are the ones kept, not the copies")
check("duplicate" in note, "the drop is reported, never silent")

# A frame with no timestamp cannot be deduplicated, and guessing would be
# worse than keeping it.
nostamp = [_lt("/L/a.fits", ""), _lt("/L/b.fits", "")]
check(len(split(nostamp, inside=True)[0]) == 2,
      "frames without DATE-OBS are kept — unknown is not duplicate")

# A filter or exposure change mid-run is two series, not a longer one.
mixed = ([_lt(f"/L/l{i}.fits", f"t{i}", filt="LUMINOS") for i in range(8)]
         + [_lt(f"/L/r{i}.fits", f"u{i}", filt="RED") for i in range(3)])
kept, _c, note = split(mixed, inside=True)
print("   " + note)
check(len(kept) == 8 and all(k["filter"] == "LUMINOS" for k in kept),
      "the larger set wins")
check("set aside" in note and "RED" in note,
      "and what was set aside is named, with its filter", note)

# Kind decides, and where the frame came from decides the default.
unlabelled = [{"path": "/x.fits", "kind": None, "exp_s": 60.0, "gain_v": None,
               "temp_v": None, "binning": 1, "dims": None,
               "instrument": None, "filter": "", "date_obs": "z"}]
check(len(split(unlabelled, inside=True)[0]) == 1,
      "an unlabelled frame inside YOUR folder is a light — you pointed at it")
check(len(split(unlabelled, inside=False)[0]) == 0,
      "the same frame in a library folder is discarded, not guessed at")

# Calibration found in two places is one group, not two.
def _cf(path, kind, exp):
    return {"path": path, "kind": kind, "exp_s": exp, "gain_v": 125,
            "temp_v": -10.0, "binning": 1, "dims": (3008, 3008),
            "instrument": "Ares-M PRO", "filter": "LUMINOS", "date_obs": ""}
a = gcal([_cf("/in/f1.fits", "flat", 3.0), _cf("/in/f2.fits", "flat", 3.0)])
b = gcal([_cf("/lib/f3.fits", "flat", 3.0)])
both = merge(a, b)
check(len(both["flat"]) == 1 and len(both["flat"][0]["files"]) == 3,
      "the same signature found inside your folder and in the library is "
      "ONE group of three, not two groups competing")
check(len(merge(a, gcal([_cf("/lib/d.fits", "dark", 60.0)]))) == 2,
      "different kinds stay apart")
_sh.rmtree(tmp2, ignore_errors=True)

print("\n8l) saturation is read from the pixels, not from a flag")
# The regression this replaces: calibration turned the frames from 16-bit
# integers into 32-bit floats, Siril's `has_saturated` stopped firing, and
# the run reported "Siril kept 8 of 178 frames (4%)" with no cause. The
# saturation had not changed at all — only the flag had. Measured on the
# real pair: raw peak 65532 of 65535, calibrated peak 1.000 of 1.0.
sat = ns["saturation_verdict"]
fs = ns["full_scale_of"]

check(fs(np.zeros(4, np.uint16)) == 65535.0, "uint16 full scale is 65535")
check(fs(np.zeros(4, np.uint8)) == 255.0, "and uint8 is 255")
check(fs(np.array([0.0, 1.0], np.float32)) == 1.0,
      "a float frame in [0,1] is Siril's normalised convention")
check(fs(np.array([0.0, 4000.0], np.float32)) == 4000.0,
      "a float frame that is NOT normalised falls back to its own peak — "
      "relative is worse than knowing the ADC range, better than inventing "
      "a threshold")

raw = np.full((200, 200), 1500, np.uint16)
raw[100, 100] = 65532                       # the real clip level, not 65535
ok, why = sat(raw, 100, 100)
print("   " + why)
check(ok is True, "a 16-bit core clipped at 65532 counts as saturated — "
      "asking for the exact maximum would have missed this camera", why)
check(sat(raw, 50, 50)[0] is False, "and empty sky does not")

cal = np.full((200, 200), 0.024, np.float32)
cal[100, 100] = 1.0
ok, why = sat(cal, 100, 100)
print("   " + why)
check(ok is True, "the SAME star after calibration to float still reads as "
      "saturated — which is the whole point", why)
check(sat(cal, 50, 50)[0] is False, "and empty sky still does not")

check(sat(raw, 500, 500)[0] is None,
      "a target outside the frame is unknown, not clean")
check(sat(None, 1, 1)[0] is None, "and so is missing data")
# The box must be wide enough for the centroid to wander and narrow enough
# not to annex the neighbourhood.
off = np.full((200, 200), 1500, np.uint16)
off[100, 112] = 65532                       # 12 px away — still the core
check(sat(off, 100, 100)[0] is True,
      "a peak 12 px from the reported centroid is still the target's core")
far = np.full((200, 200), 1500, np.uint16)
far[100, 140] = 65532                       # 40 px away — a different star
check(sat(far, 100, 100)[0] is False,
      "a saturated star 40 px away is NOT the target — the box does not "
      "annex the neighbourhood")

print("\n8p2) a locally-imported name is imported in every function using it")
# astropy is optional everywhere else in this file, so `fits` is imported
# inside the three functions that need it. Forgetting one cost a whole
# run: the drift filter raised NameError, the frame size stayed None, the
# filter silently did nothing, and the log said only "swallowed NameError".
tree_li = ast.parse(src)
LOCAL_ONLY = {"fits"}
offenders = []
for fn in [n for n in ast.walk(tree_li) if isinstance(n, ast.FunctionDef)]:
    brought = {a.asname or a.name.split(".")[0]
               for n in ast.walk(fn)
               if isinstance(n, (ast.Import, ast.ImportFrom))
               for a in n.names}
    used_names = {n.id for n in ast.walk(fn)
                  if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    missing_imp = (used_names & LOCAL_ONLY) - brought
    if missing_imp:
        offenders.append(f"{fn.name}:{fn.lineno} needs {sorted(missing_imp)}")
check(not offenders,
      "every function that uses a locally-imported module imports it — a "
      "NameError here does not crash, it makes a guard quietly do nothing",
      "; ".join(offenders) if offenders else "all clean")
probe_src = src[src.index("envelope = getattr(self, \"_drift\", None)"):]
probe_src = probe_src[:probe_src.index("comps, rejected, how_ranked")]
check("drift filter is" in probe_src and "OFF for this run" in probe_src,
      "and if the frame size cannot be read the run SAYS the filter is off "
      "— a guard that quietly does not run is worse than no guard")

print("\n8q2) repeated failures stop instead of hammering Siril")
# Twelve light_curve calls failed in a row on EXOTIC's demo set — five in
# the comparison screen, six in the aperture scan, one final — every one
# for the SAME reason. Siril's process then died and the script could only
# report "[Errno 32] Broken pipe", which reads as somebody else's bug.
check(ns["MAX_PHOTOMETRY_FAILURES"] <= 5,
      "the probes give up after a handful of identical failures — three is "
      "enough to tell an unlucky aperture from a broken geometry",
      f"{ns['MAX_PHOTOMETRY_FAILURES']} in a row")
meas = src[src.index("def _measure_curve"):]
meas = meas[:meas.index("\n    def _screen_comparisons")]
check("self._photometry_failures >= MAX_PHOTOMETRY_FAILURES" in meas,
      "and the guard is at the TOP of the probe, so the remaining calls "
      "are skipped rather than merely counted")
check("self._photometry_failures = 0" in meas,
      "a success resets the count — a bad frame in the middle of a good "
      "run must not end the scan")
note = src[src.index("def _note_photometry_failure"):]
note = note[:note.index("\n    def ", 10)]
check("!= MAX_PHOTOMETRY_FAILURES" in note,
      "the diagnosis is printed ONCE, at the moment a streak becomes one")
drift_h = src[src.index('if "light_curve" in str(exc) and drift'):]
drift_h = drift_h[:drift_h.index("elif")]
check("seqapplyreg" in drift_h and "trim the run" in drift_h,
      "a light_curve refusal on a drifting run names the two ways out — "
      "resample, or cut to the stretch that holds still — instead of "
      "handing back 'Generic error'")
fail_h = src[src.index('elif "broken pipe" in str(exc).lower()'):]
fail_h = fail_h[:fail_h.index("else:")]
check("crash on Siril's side" in fail_h and "Restart Siril" in fail_h,
      "and a broken pipe is named for what it is — Siril's process is "
      "gone, so the command in flight is the one thing that CANNOT be at "
      "fault any more")

print("\n8r2) a comparison star must stay ON the sensor for the whole run")
env_f = ns["drift_envelope"]
stays = ns["stays_in_frame"]
# Siril moves each measurement box by the registration data. A star that
# is comfortably inside the reference frame can still leave the sensor
# later — and when a COMPARISON does, the whole light_curve command fails
# with "generic error" after a warning that names one FRAME and never says
# which star. Measured on EXOTIC's demo set: dx runs +52 to -218 px on a
# 650 px frame.
# x from the stored h02 range (-52.04..+218.25) NEGATED — the measured
# convention — and y from the h12 range directly. The first envelope used
# the raw x values, judged every star by the mirror of its true
# excursion, and kept (222, 73): a star that in truth walks to x = 4 and
# was the first -refat light_curve then failed on.
ENV = (-218.25, 52.04, -37.42, 24.85)
MARGIN = 11.0
verdicts = {(x, y): stays(x, y, 650, 500, ENV, MARGIN)
            for x, y in ((371, 323), (222, 73), (645, 120),
                         (567, 198), (499, 88), (51, 232))}
for xy, ok in verdicts.items():
    print(f"   {str(xy):>11} -> {'stays' if ok else 'leaves'}")
check(verdicts[(371, 323)],
      "the target of that run stays on the chip — which is why the failure "
      "looked like a photometry bug rather than a geometry one")
gone = [xy for xy, ok in verdicts.items() if not ok]
check(len(gone) == 3 and (51, 232) in gone and (645, 120) in gone,
      "while THREE of the five comparisons it chose spend part of the run "
      "off the sensor: one runs to x = -167, another to x = 697 on a 650 px "
      "frame", str(sorted(gone)))
# sirilpy hands back an OBJECT with h00..h22 attributes, not an array.
# The first version of this test used a numpy 3x3 — a shape the running
# code never sees — so it passed while the filter returned None on every
# real run and quietly did nothing. Both forms are checked now, and the
# object one is the one that matters.
class _Hom:
    def __init__(self, dx, dy):
        self.h00, self.h10, self.h02, self.h12 = 1.0, 0.0, dx, dy
# The REAL stored values of that run: frame 1, frame 140, the reference.
SHIFTS = ((-52.04, -37.42), (218.25, -17.32), (0.0, 0.0))
for label, homs in (
        ("sirilpy objects", [_Hom(dx, dy) for dx, dy in SHIFTS]),
        ("plain 3x3 arrays", [np.array([[1, 0, dx], [0, 1, dy], [0, 0, 1]],
                                       float) for dx, dy in SHIFTS])):
    got_env = env_f(homs)
    check(got_env is not None and abs(got_env[0] + 218.25) < 1e-6
          and abs(got_env[1] - 52.04) < 1e-6,
          f"the envelope reads {label} — sirilpy hands back an object with "
          "h00..h22, and a plain 3x3 works too so the maths can be "
          "exercised without sirilpy", str(got_env))
class _Opaque:
    pass
check(env_f([_Opaque(), _Opaque()]) is None,
      "and something it cannot read at all gives None, which switches the "
      "filter off rather than inventing an envelope")
check(env_f([]) is None and env_f([None, None]) is None,
      "and an unregistered sequence gives None, which switches the filter "
      "off rather than rejecting everything")
check(stays(300, 250, 650, 500, None, MARGIN),
      "with no envelope every star passes — the filter must never be the "
      "reason a run with no registration data finds nothing")
ccs2 = ns["choose_comparison_stars"]
class _S2:
    def __init__(self, x, y, m):
        self.xpos, self.ypos, self.mag = x, y, m
        self.has_saturated = False
pool = [_S2(371, 323, 10.0), _S2(51, 232, 10.2), _S2(645, 120, 10.3),
        _S2(400, 250, 10.4), _S2(450, 300, 10.5), _S2(500, 200, 10.6)]
kept, rej, _n = ccs2(pool, (371, 323), 5, 1.84,
                     frame_wh=(650, 500), envelope=ENV)
why = {(int(r[0]), int(r[1])): r[2] for r in rej}
check("drifts" in why.get((51, 232), "") and "drifts" in why.get((645, 120), ""),
      "and the two that would walk off are rejected with that reason, not "
      "silently", why.get((51, 232), "KEPT"))
check(all((int(c[0]), int(c[1])) not in ((51, 232), (645, 120)) for c in kept),
      "so they never reach the -refat list that would fail the command")

print("\n8s2) the plate scale is handed to Siril, not left to its memory")
isc = ns["image_scale_arcsec"]
s2f = ns["scale_to_focal_pixel"]
# Siril takes the scale from FOCALLEN and XPIXSZ. With neither it uses
# whatever it last SAVED as a default — the previous target's telescope.
# On EXOTIC's demo set that was 3.76 um / 380.33 mm from another rig: a
# 0.46 deg field where the truth is 0.94, 373 000 catalogue stars fetched,
# and "Generic error". Nothing in that message says "wrong scale".
sc, where = isc({"IM_SCALE": "5.210"})
print(f"   IM_SCALE 5.210 -> {sc:.3f} arcsec/px, field {650 * sc / 3600:.2f} deg")
check(abs(sc - 5.210) < 1e-9 and where == "IM_SCALE",
      "a header that states the scale outright is read directly — "
      "MicroObservatory writes IM_SCALE, older systems SECPIX", where)
check(abs(650 * sc / 3600 - 0.94) < 0.01,
      "and that is the 0.94 deg field Siril could not find while looking "
      "for 0.46", f"{650 * sc / 3600:.2f} deg")
sc2, where2 = isc({"FOCALLEN": "382.0", "XPIXSZ": "3.76"})
check(abs(sc2 - 2.03) < 0.01 and "FOCALLEN" in where2,
      "and where the optics are given instead, the scale is derived — this "
      "matches Siril's own solve of the same frames to 0.4%", f"{sc2:.3f}")
foc, pix = s2f(5.210)
check(abs(206.265 * pix / foc - 5.210) < 1e-6,
      "the focal/pixel pair handed back reproduces the scale — only the "
      "RATIO matters to a solver, so one value is fixed and the other "
      "follows", f"focal {foc:.1f} mm, pixel {pix:.1f} um")
none_sc, why = isc({})
check(none_sc is None and "saved defaults" in why,
      "with nothing to go on it says so rather than guessing — a wrong "
      "scale fails as 'Generic error', which reads like a broken solve",
      why[-40:])
solver = src[src.index("def _solve_reference"):]
solver = solver[:solver.index("\n    def ", 10)]
check("-focal=" in solver and "-pixelsize=" in solver,
      "and the run passes both to platesolve, so Siril never reaches for "
      "the previous target's optics")

print("\n8t2) a crowded field still yields an ensemble, with the price named")
class _St:
    def __init__(self, x, y, m):
        self.xpos, self.ypos, self.mag = x, y, m
        self.has_saturated = False
ccs = ns["choose_comparison_stars"]
FW = 1.84
OUT = ns["AUTORING_OUTER_FWHM"] * FW
rng8t2 = np.random.default_rng(4)
def _field(n, w=650, h=500):
    xs = rng8t2.uniform(20, w - 20, n)
    ys = rng8t2.uniform(20, h - 20, n)
    ms = rng8t2.uniform(10.0, 12.0, n)
    return [_St(x, y, m) for x, y, m in zip(xs, ys, ms)]
# EXOTIC's demo set is 650x500 at 5.2 arcsec/px: 164 of 261 stars fell to
# the isolation cut, ONE comparison survived, and the run stopped. Refusing
# to run is worse than running with a stated compromise.
for n, expect_relaxed in ((400, False), (1500, True)):
    stars = _field(n)
    got, _rej, note = ccs(stars, (stars[0].xpos, stars[0].ypos), 5, FW)
    relaxed = "isolation relaxed" in note
    print(f"   {n:5d} stars in 650x500 -> {len(got)} comps"
          + ("  (relaxed)" if relaxed else "  (full radius)"))
    check(len(got) >= ns["MIN_COMPS"],
          f"{n} stars still yields an ensemble", f"{len(got)} comps")
    check(relaxed is expect_relaxed,
          "and the relaxation engages ONLY when the strict radius cannot "
          f"reach the MINIMUM ({n} stars: "
          f"{'relaxed' if expect_relaxed else 'full'}) — relaxing to reach "
          "the requested count would trade isolation away in any field "
          "that simply has fewer good stars than asked for",
          note.split(";")[-1].strip()[:50] if relaxed else "full radius")
stars = _field(1500)
_g, _r, note = ccs(stars, (stars[0].xpos, stars[0].ypos), 5, FW)
check("isolation relaxed to" in note and "survived a field this crowded" in note,
      "the compromise is NAMED with its radius and its reason — a silently "
      "loosened criterion is a measurement nobody can weigh", note[-60:])
src2 = src[src.index("def choose_comparison_stars"):]
src2 = src2[:src2.index("\ndef crowding_note")]
check("COMP_APERTURE_FLOOR_FWHM" in src2,
      "and the floor is the APERTURE: a neighbour inside that is blended "
      "photometry, not a background error, and no report rescues it")

print("\n8v1) choosing a folder reads the headers straight away")
probe = src[src.index("def _probe_target"):]
probe = probe[:probe.index("\n    def ", 10)]
pick = src[src.index("def _on_pick_folder"):]
pick = pick[:pick.index("\n    def ", 10)]
check("self._probe_target(files)" in pick,
      "the folder picker probes immediately — the run does this anyway, but "
      "at folder-choose time it is a number you can CHECK rather than one "
      "that appears after five minutes of registration")
check("PROBE_HEADERS" in probe and ns["PROBE_HEADERS"] <= 50,
      "capped, because this runs on the UI thread: 30 compressed N.I.N.A. "
      "subs measured 153 ms, which is a click; several hundred would freeze "
      "the window", f"{ns['PROBE_HEADERS']} headers")
check("target_key(existing) != target_key(name)" in probe,
      "the NAME field follows OBJECT when it names a DIFFERENT target — "
      "the box persists across sessions, and a stale previous name sat "
      "over WASP-75 frames as 'HATP-32' (see 8q10)")
check("gap <= TARGET_DISAGREE_ARCSEC" in probe
      and "left over from another " in probe,
      "the RA/Dec fields follow OBJCTRA/OBJCTDEC the same way: agreement "
      "within the threshold leaves them as typed, anything further is the "
      "previous target and is replaced, with the gap logged")
check("split_frames" in probe,
      "it splits lights from calibration first, so a folder of flats "
      "cannot prefill the target from a parked mount")
check("agrees with the fields" in probe and '\\" away, left over' in probe,
      "filled fields are COMPARED first — agreement is said and kept, "
      "and a replacement names the gap it replaced")
check("carry no OBJCTRA/OBJCTDEC" in probe,
      "and headers that say nothing produce a line too — silence there "
      "reads as 'nothing to do' when it means 'type the name'")

# The data path itself, on the two shapes of header this met.
NINA = [{"kind": "light", "object": "WASP-75b",
         "objctra": "22 49 33", "objctdec": "-10 40 32"} for _ in range(25)]
MICRO = [{"kind": None, "object": "HATP-32",
          "objctra": "", "objctdec": ""} for _ in range(30)]
FLATS = [{"kind": "flat", "object": "WASP-75b",
          "objctra": "00 00 00", "objctdec": "+00 00 00"} for _ in range(5)]
ra_n, dec_n, _n = ns["header_target_radec"](NINA + FLATS)
check(ra_n is not None and abs(ra_n - 342.3875) < 1e-3,
      "N.I.N.A. subs beside their flats yield the target, not the park "
      "position", f"{ra_n:.5f}")
check(ns["header_target_radec"](MICRO)[0] is None
      and next((i["object"] for i in MICRO if i.get("object")), "") == "HATP-32",
      "MicroObservatory subs yield no coordinates but DO yield the name, "
      "which is exactly the case the archive lookup exists for")

print("\n8v2) the target controls sit where the target is chosen")
grp3 = src[src.index('QGroupBox("3 · Target star")'):]
grp3 = grp3[:grp3.index("def _build_photometry_group")]
grp6 = src[src.index("def _build_export_group"):]
grp6 = grp6[:grp6.index("\n    def _build_action_buttons")]
# The name box and the archive lookup DECIDE THE POSITION, so they belong
# with the other ways of deciding it. Having them in the submission group
# meant the one control that spares you typing coordinates sat in a group
# about filing the result.
for w in ("self.ed_target_name = QLineEdit()", "self.chk_resolve = QCheckBox("):
    check(w in grp3 and w not in grp6,
          f"{w.split('=')[0].strip()} lives in group 3, not group 6 — it "
          "decides the target, not the submission")
check("From the frames" in grp3,
      "and the frames themselves are a target MODE, offered first: subs "
      "usually carry OBJCTRA/OBJCTDEC or OBJECT, and asking the user to "
      "retype what the file already says is the thing to remove")
modes = src[src.index("def _target_mode"):]
modes = modes[:modes.index("\n    def ", 10)]
check('"auto"' in modes and modes.index('"auto"') < modes.index('"brightest"'),
      "'auto' is the FIRST mode, so it is what a fresh install starts on",
      modes.strip().splitlines()[-1].strip())
run_src = src[src.index("eph = self._resolve_from_name"):]
run_src = run_src[:run_src.index("_detect_reference_stars")]
check('"auto"' in run_src and "BRIGHTEST star is used" in run_src,
      "and when the frames say nothing, falling back to brightest is "
      "ANNOUNCED — a guess that looks like a measurement is the failure "
      "this whole tool is against")

print("\n8w) time stamps real telescopes actually write")
jdf = ns["_jd_from_dateobs"]
ref = jdf("2017-12-20T01:33:43.317")
# Both of these came back NaN before, and both are silent failures.
for stamp, why in (
        ("2026-08-15T07:26:29.1714366",
         "N.I.N.A. writes SEVEN fractional digits, which fromisoformat "
         "refuses on Python 3.10 and earlier — every frame of a 178-sub run "
         "parsed to NaN, so the seeing, sky and star-count bases could never "
         "be paired and the fit quietly ran on airmass alone"),
        ("2017-12-19T18:33:43.317-0700",
         "and MicroObservatory writes LOCAL time with a UTC offset — taking "
         "that as UTC is a seven-hour error in a quantity measured in "
         "minutes"),
        ("2017-12-20T01:33:43.317-0000",
         "as well as the explicit +00:00 form")):
    got = jdf(stamp)
    check(np.isfinite(got), why, repr(stamp))
check(abs(jdf("2017-12-19T18:33:43.317-0700") - ref) * 86400 < 0.01,
      "the offset is SUBTRACTED, so local and UTC land on the same instant",
      f"{abs(jdf('2017-12-19T18:33:43.317-0700') - ref) * 86400:.4f} s apart")
# Against the header's own MJD-OBS = 58107.065 -> JD 2458107.565.
check(abs(ref - 2458107.565) < 0.002,
      "and the result matches the MJD-OBS the same header records",
      f"{ref:.5f} vs 2458107.565")
check(not np.isfinite(jdf("")), "empty is still NaN, not a date")

print("\n8x) the longitude sign is decided by measurement, not convention")
lsc = ns["longitude_sign_check"]
# FITS never settled east- vs west-positive. Getting it wrong mirrors the
# site across the globe and detrends the airmass for the wrong place —
# silently. But the frames carry the answer: an altitude, a pointing and a
# time say where the telescope actually was.
MICRO = {"TELALT": "+62.592", "RA": "31.312099", "DEC": "46.769087",
         "DATE-OBS": "2017-12-19T18:33:43.317-0700"}
lon, note = lsc(MICRO, 31.68, 110.88)
print(f"   MicroObservatory: {lon:+.4f} — {note[:70]}…")
check(abs(lon + 110.88) < 1e-9 and "FLIPPED" in note,
      "a WEST-positive header is caught and flipped, because +110.88 would "
      "put the target below the horizon while -110.88 reproduces TELALT",
      f"{lon:+.4f}")
NINA = {"CENTALT": "47.8483", "RA": "342.2429", "DEC": "-10.3012",
        "DATE-OBS": "2026-08-15T07:26:29.1714366"}
lon2, note2 = lsc(NINA, 31.5469, -99.3822)
check(abs(lon2 + 99.3822) < 1e-9 and "confirmed" in note2,
      "a correct east-positive header is CONFIRMED, not flipped — the check "
      "has to be able to say yes", note2[:50])
lon3, note3 = lsc({}, 31.68, 110.88)
check(abs(lon3 - 110.88) < 1e-9 and "no altitude" in note3,
      "with no altitude to check against, nothing is changed and the "
      "assumption is stated rather than hidden", note3[:50])
lon4, note4 = lsc(dict(MICRO, RA="2.087"), 31.68, 110.88)
check(abs(lon4 - 110.88) < 1e-9 and "not conclusive" in note4,
      "and an RA in the WRONG UNIT makes the check inconclusive rather than "
      "flipping wrongly — a guess that can only fail safe", note4[-40:])

print("\n8y) a frame with no IMAGETYP is still a light")
hdr2 = ns["header_target_radec"]
UNK = {"kind": None, "objctra": "22 49 33", "objctdec": "-10 40 32"}
check(hdr2([dict(UNK) for _ in range(5)])[0] is not None,
      "most archive and school-telescope data carries OBJECT but no "
      "IMAGETYP, and requiring kind=='light' made this whole path invisible "
      "on it — 142 frames of EXOTIC's own demo set")
check(hdr2([dict(UNK, kind="flat") for _ in range(5)])[0] is None,
      "while a frame that SAYS it is a flat is still skipped: unknown is "
      "not the same as known-to-be-something-else")

print("\n8z) a saturation flag far below the pixels does not win")
sat_frac = ns["_sat_fraction"]
data_lo = np.zeros((60, 60)); data_lo[30, 30] = 846.0; data_lo[0, 0] = 32767.0
verdict, why = ns["saturation_verdict"](data_lo, 30, 30)
frac = sat_frac(why)
print(f"   peak 846 of 32767 -> verdict {verdict}, fraction {frac:.3f}")
check(verdict is False and frac is not None and abs(frac - 0.026) < 1e-6,
      "the fraction reads back out of the very message that reports it, so "
      "the two can never describe different things", f"{frac}")
check(frac < 0.5 * ns["SATURATION_FRACTION"],
      "and 2.6% of full scale is far enough under the limit that Siril's "
      "flag is reported as a disagreement rather than accepted — measured "
      "on MicroObservatory data, where that false positive would block the "
      "AAVSO file and tell the observer to re-shoot a good night")
check(sat_frac("no percentage here") is None,
      "an unparseable message gives None, and None keeps the old "
      "flag-wins behaviour")

print("\n8u) the target comes from the headers first, the archive second")
hdr = ns["header_target_radec"]
sep = ns["angular_sep_arcsec"]
# The rig this was written for: N.I.N.A. writes the OBJECT's position in
# OBJCTRA/OBJCTDEC, and all 178 lights carry it identically.
LIGHT = {"kind": "light", "objctra": "22 49 33", "objctdec": "-10 40 32"}
# A flat is shot with the mount PARKED, and this rig then writes the
# sentinel plus a pointing near the celestial pole. Reading one of those
# instead of a light is what made these fields look untrustworthy.
FLAT = {"kind": "flat", "objctra": "00 00 00", "objctdec": "+00 00 00"}
ra_h, dec_h, note_h = hdr([dict(LIGHT) for _ in range(178)])
d_arch = sep(ra_h, dec_h, 342.3858995, -10.6754686)
print(f"   178 lights -> {ra_h:.5f} / {dec_h:+.5f}, {d_arch:.1f}\" from the "
      f"archive ({note_h})")
check(d_arch < 15.0,
      "the headers put the target within a few arcsec of the archive — under "
      "3 px at 2 arcsec/px, well inside Siril's own +/-19 px search box, so "
      "no lookup is needed for the POSITION", f"{d_arch:.1f} arcsec")
check(hdr([dict(FLAT) for _ in range(5)])[0] is None,
      "a folder of flats yields nothing — the mount was parked and the "
      "sentinel is not a position on the sky")
mixed = [dict(FLAT) for _ in range(5)] + [dict(LIGHT) for _ in range(178)]
check(abs(hdr(mixed)[0] - ra_h) < 1e-9,
      "and a flat sitting beside the lights cannot pull the answer toward "
      "the pole, because only LIGHT frames are read")
two = [dict(LIGHT), dict(LIGHT, objctra="12 00 00")]
check(hdr(two)[0] is None and "more than one target" in hdr(two)[2],
      "two targets in one folder is a refusal with the reason, not a median "
      "between them", hdr(two)[2][:60])
# The pointing pair is a different thing and must never be substituted.
resolver = src[src.index("def _resolve_from_name"):]
resolver = resolver[:resolver.index("\n    def ", 10)]
body = resolver[resolver.index('"""', resolver.index('"""') + 3) + 3:]
check("header_target_radec" in body and 'info.get("objctra")' not in body,
      "the run reads the object position through that one helper, rather "
      "than parsing the cards a second time somewhere else")
for bad in ('get("RA")', 'info["RA"]', '"DEC"'):
    check(bad not in resolver,
          f"and never {bad} — those are the TELESCOPE pointing, a quarter of "
          "a degree off here because the target is not the field centre",
          "absent")
check("KIND_LIGHT" in resolver,
      "the OBJECT name is taken from a light frame too, for the same reason")
# A real run exposed this: the user had RA/Dec stored from an earlier
# session, so the manual entry won — correctly — and NOTHING said the
# headers had also been read and agreed. Silence there is the worst of the
# three outcomes, because a coordinate left over from the previous target
# looks exactly like a deliberate one.
for branch in ("Target position not in the headers",
               "Target from OBJCTRA/OBJCTDEC in your lights",
               "Using the RA/Dec in the form"):   # "you entered" would be
               # wrong now: the folder picker prefills these fields
    check(branch in resolver,
          f"every path says where the position came from: {branch!r}")
check("from what OBJCTRA/OBJCTDEC in your lights say" in resolver,
      "and a manual entry that DISAGREES with the frames is called out — "
      "that is how a stale coordinate from the previous target announces "
      "itself")

print("\n8u2) the name lookup adds the ephemeris, and cross-checks")
norm = ns["normalise_planet_name"]
for raw, want in (("WASP-75b", "WASP-75 b"), ("  HAT-P-32B ", "HAT-P-32 b"),
                  ("Kepler-8 b", "Kepler-8 b"), ("TrES-3", "TrES-3"),
                  ("", "")):
    check(norm(raw) == want,
          f"{raw!r} normalises to {want!r} — one missing space is the whole "
          "difference between a hit and a silent miss", repr(norm(raw)))
calls = []
class _Resp:
    def __init__(self, body): self.body = body
    def read(self): return self.body.encode()
    def __enter__(self): return self
    def __exit__(self, *a): return False
def _fake(url, timeout=None):
    calls.append(url)
    return _Resp("pl_name,ra,dec,pl_orbper,pl_tranmid,pl_trandur,pl_trandep,"
                 "st_teff,st_logg,sy_vmag\n"
                 '"WASP-75 b",342.3858995,-10.6754686,2.484193,'
                 "2456016.2669,1.9728,1.07,6100.0,4.29,11.591\n")
eph, note = ns["archive_lookup"]("wasp-75B", opener=_fake)
check(eph is not None and not note, "a lower-case name still resolves", note)
# EXOTIC's demo headers read OBJECT = 'HATP-32'; the archive holds
# 'HAT-P-32 b'. Hyphens and spaces are stripped from BOTH sides, so every
# spelling in between works without a table of survey prefixes.
for typed in ("HATP-32", "hatp32b", "HAT-P-32 b"):
    calls.clear()
    ns["archive_lookup"](typed, opener=_fake)
    check("REPLACE" in calls[0] and "HATP32" in calls[0].upper(),
          f"{typed!r} queries the same stripped key", typed)
check("hostname" in calls[0],
      "and hostname is searched as well as pl_name — a name with no planet "
      "letter, which is what a header usually carries, exists only there")
def _many(url, timeout=None):
    return _Resp("pl_name,hostname,ra,dec\n"
                 '"Kepler-11 b","Kepler-11",1,2\n'
                 '"Kepler-11 c","Kepler-11",1,2\n')
e_m, n_m = ns["archive_lookup"]("Kepler-11", opener=_many)
check(e_m is None and "2 known planets" in n_m and "Kepler-11 b" in n_m,
      "a multi-planet system is a REFUSAL that lists the choices — picking "
      "one silently would attach the wrong ephemeris to the O−C", n_m[:60])
check(eph.get("period_d") and eph.get("t0_bjd"),
      "and it brings the ephemeris, which is the part the header CANNOT "
      "carry and the only reason to go to the network at all")
check("TARGET_DISAGREE_ARCSEC" in resolver and "disagree by" in resolver,
      "a header/archive disagreement is REPORTED, not silently resolved — "
      "the two describing different things is what a wrong OBJECT looks like")
check("The headers win" in resolver,
      "and the headers win, because they arrived with the frames")
def _empty(url, timeout=None): return _Resp("pl_name,ra,dec\n")
e2, n2 = ns["archive_lookup"]("Nonesuch 1 b", opener=_empty)
check(e2 is None and "no planet" in n2,
      "an unknown name is a named refusal, not a crash", n2)
def _boom(url, timeout=None): raise OSError("no route to host")
e3, n3 = ns["archive_lookup"]("WASP-75 b", opener=_boom)
check(e3 is None and "could not be reached" in n3,
      "and no connection loses only the O−C — the position came from the "
      "headers and still stands", n3)

print("\n8v) O−C is what a single night is worth contributing")
oc = ns["o_minus_c"]
P, T0 = 2.484193, 2456016.2669
for off in (0.0, 4.2, -7.5):
    got, ep = oc(T0 + 2114 * P + off / 1440.0, T0, P)
    check(abs(got - off) < 1e-6 and ep == 2114,
          f"a mid-transit {off:+.1f} min from the prediction reads "
          f"{off:+.1f} min at epoch 2114", f"{got:+.3f} min, epoch {ep}")
check(oc(1.0, 0.0, 0.0) == (None, None),
      "a missing period is None, not a division")
lines = ns["oc_lines"]({"time_system": "JD_UTC",
                        "ephemeris": {"period_d": P, "t0_bjd": T0}},
                       {"t0": T0 + 2114 * P, "t0_sigma_s": 300.0})
check(lines and "not computed" in lines[0][0],
      "and JD_UTC against a BJD_TDB ephemeris is REFUSED — the 8-minute "
      "offset would land in a number whose whole interest is minutes",
      lines[0][0][:60] if lines else "no line")
good = ns["oc_lines"]({"time_system": "BJD_TDB",
                       "ephemeris": {"period_d": P, "t0_bjd": T0,
                                     "name": "WASP-75 b"}},
                      {"t0": T0 + 2114 * P + 4.2 / 1440.0,
                       "t0_sigma_s": 300.0})
joined = " ".join(l for l, _h in good)
print("   " + good[0][0].strip())
check("+4.20 min" in joined and "epoch 2114" in joined,
      "a usable one prints the drift AND the epoch — the drift alone is "
      "unreadable once a stale period mislabels which transit it was")

print("\n8r3) the reference frame is moved to the middle of the DRIFT")
# Siril 1.4.4 REFUSES light_curve when any frame sits more than 160 px
# from the reference: bisected on EXOTIC's demo set, 159.6 px runs and
# 160.7 px aborts with a line Siril calls a "Warning" followed by a
# generic error. Siril picks its reference on image quality, which put
# the whole drift on one side (image 35 of 142, worst drift 218.9 px).
shift_f = ns["shift_list"]
worst_f = ns["worst_drift"]
best_f = ns["best_reference"]
LIMIT = ns["SIRIL_DRIFT_LIMIT_PX"]
check(abs(LIMIT - 160.0) < 1e-9,
      "the limit is the measured 160 px, not a guess", f"{LIMIT:g} px")

class _H2:
    """A homography the way sirilpy hands it back: all nine elements."""
    def __init__(self, dx, dy, rot_deg=0.0):
        c, sn = math.cos(math.radians(rot_deg)), math.sin(math.radians(rot_deg))
        self.h00, self.h01, self.h02 = c, -sn, dx
        self.h10, self.h11, self.h12 = sn, c, dy
        self.h20, self.h21, self.h22 = 0.0, 0.0, 1.0

W_IMG, H_IMG = 650, 500
# The real run's geometry, sampled the way the real run samples it: dx
# runs +52 to -218 in small steps, dy stays small. The coarse five-point
# version this started as had only ONE frame under the limit, which hid
# the very thing the choice has to get right.
REAL = [(52.0 - 10.0 * k, 37.42 - 2.0 * k) for k in range(28)]
homs2 = [_H2(dx, dy) for dx, dy in REAL]
sh = shift_f(homs2, W_IMG, H_IMG)
# The list holds where the centre LANDS; the callers take differences.
# The signs are the MEASURED convention (see ref_to_frame): the stored
# homography maps frame onto reference in Siril's bottom-up row order,
# so in FITS coordinates a stored (h02, h12) moves a star by (-h02, +h12)
# — anchored by cross-correlating real frames and confirming on the
# target star itself: frame 1 stores (-52.0, -37.4) and the star sits at
# ref + (+52, -37).  The first reading applied H forwards and seeded half
# the centroids onto the wrong stars: 900 mmag of scatter.
check(len(sh) == len(REAL)
      and abs(sh[0][0] - (W_IMG / 2.0 - 52.0)) < 1e-6
      and abs(sh[0][1] - (H_IMG / 2.0 + 37.42)) < 1e-6,
      "a stored pure shift (h02, h12) moves the centre by (-h02, +h12) "
      "in FITS coordinates — the measured convention, not a guessed one",
      str(sh[0]))
r2f = ns["ref_to_frame"]
pos1 = r2f([1.0, 0.0, -52.04, 0.0, 1.0, -37.42, 0.0, 0.0, 1.0],
           371.1, 323.3, 650, 500)
check(abs(pos1[0] - 423.14) < 0.01 and abs(pos1[1] - 285.88) < 0.01,
      "and the real frame-1 numbers reproduce where the target was "
      "actually found on the pixels: stored (-52.0, -37.4) puts "
      "(371.1, 323.3) at (423.1, 285.9)", str(pos1))
check(abs(worst_f(sh, 0) - max(math.hypot(dx - 52.0, dy - 37.42)
                               for dx, dy in REAL)) < 1e-6,
      "and the worst drift against a frame is the plain distance between "
      "the two centres")

# A MERIDIAN FLIP is what exposed reading the translation column instead.
# 180 degrees about the centre leaves every star on the same piece of sky
# and moves nothing off the sensor, but the translation column becomes the
# width and height of the frame.
FLIP_W = FLIP_H = 3008
flip = [_H2(0.0, 0.0), _H2(3000.97, 3013.91, 179.878)]
fs = shift_f(flip, FLIP_W, FLIP_H)
flip_centre = math.hypot(fs[1][0] - fs[0][0], fs[1][1] - fs[0][1])
flip_column = math.hypot(3000.97, 3013.91)
check(flip_column > 4000 and flip_centre < 30,
      "a 180-degree flip moves the image centre a few px while its "
      "translation column reads thousands — measured on a real 3008x3008 "
      "run: 4253 px by the column, 13.7 px by the centre",
      f"column {flip_column:.0f} px, centre {flip_centre:.1f} px")
check(flip_centre < LIMIT,
      "so a flipped run is NOT declared unmeasurable. Reading the column "
      "said 'no reference can rescue this run' about a run with no drift "
      "problem at all, and threw the whole photometry away")
check(shift_f(flip)[1] == (-3000.97, 3013.91),
      "with no frame size there is no flip axis, so the fallback is the "
      "translation column with the measured signs (-h02, +h12) — right "
      "whenever the field does not rotate")

MARGIN = ns["DRIFT_LIMIT_MARGIN"]
CEIL = LIMIT * MARGIN
# Weighted FWHM, lower is better.
QUAL = [2.4 + 0.01 * k for k in range(28)]
QUAL[0] = 1.80                               # Siril's pick: the best frame
mid = min(range(len(sh)), key=lambda i: worst_f(sh, i))
QUAL[mid] = 8.50                             # ...and the middle is the worst
w_siril = worst_f(sh, 0)                     # Siril's quality pick
i_best, w_best = best_f(sh, QUAL, CEIL)
check(w_siril > LIMIT,
      "with Siril's own reference the run is over the limit and CANNOT be "
      "measured at all", f"{w_siril:.1f} px vs {LIMIT:.0f}")
check(w_best <= CEIL,
      "re-centring brings it under, with margin — a frame that only just "
      "squeaks under would abort again on the next nudge of the mount",
      f"frame index {i_best}, {w_best:.1f} px vs {CEIL:.0f}")
check(i_best != mid,
      "and the frame at the exact middle of the drift is NOT taken when a "
      "usable frame is better: that one was the worst of the night, and "
      "picking it made light_curve run and return 6 points of 142",
      f"middle {mid} (q={QUAL[mid]}), chosen {i_best} (q={QUAL[i_best]})")
check(all(QUAL[i_best] <= QUAL[i] for i in range(len(sh))
          if worst_f(sh, i) <= CEIL),
      "the chosen frame is the best-QUALITY one Siril will accept, not "
      "merely an acceptable one")
i_free, _ = best_f(sh, QUAL, None)
check(QUAL[i_free] == min(QUAL),
      "and with no limit to satisfy it reproduces Siril's own criterion — "
      "quality alone", f"index {i_free}")
# Unregistered frames must not be chosen and must not break the search.
sh_gap = shift_f([_H2(*REAL[0]), None, _H2(*REAL[2]), None, _H2(*REAL[4])],
                 W_IMG, H_IMG)
check(sh_gap[1] is None and sh_gap[3] is None,
      "frames that failed registration come back as None, not as (0, 0) — "
      "a fake zero shift would look like a perfect reference")
i_gap, w_gap = best_f(sh_gap, None, None)
check(i_gap is not None and sh_gap[i_gap] is not None,
      "and the reference is chosen from frames that HAVE registration")
check(best_f([None, None], None, None) == (None, None),
      "a run with no registration at all yields no choice rather than an "
      "index that would then be handed to setref")
# The envelope must follow the reference that is actually in use.
env_f2 = ns["drift_envelope"]
e0 = env_f2(homs2, (0.0, 0.0), W_IMG, H_IMG)
e1 = env_f2(homs2, sh[i_best], W_IMG, H_IMG)
check(abs(e0[0] - e1[0]) > 1.0,
      "the drift envelope is measured against the reference in use, not "
      "against the one Siril happened to start with",
      f"{e0[0]:.0f} -> {e1[0]:.0f}")
check(abs((e1[1] - e1[0]) - (e0[1] - e0[0])) < 1e-6,
      "and re-centring moves the window without changing its width — the "
      "field drifts just as far either way")

print("\n8r4) -autoring is set with setphot, never passed as a flag")
# Measured against Siril 1.4.4: passing -autoring makes light_curve abort
# with "The given coordinates are not in the image" on coordinates that
# are demonstrably inside it. The identical command without the flag, on
# the same sequence and the same stars, produces the light curve.
lca = ns["light_curve_args"]
argv = lca("lights", 0, True, (371, 323), [(222, 73)])
check("-autoring" not in argv,
      "the flag never reaches Siril — it is what made light_curve refuse",
      " ".join(argv))
check(argv[:3] == ["light_curve", "lights", "0"]
      and "-at=371,323" in argv and "-refat=222,73" in argv,
      "while everything else about the command is unchanged")
inner_f, outer_f = ns["AUTORING_INNER_FWHM"], ns["AUTORING_OUTER_FWHM"]
check(abs(inner_f * 1.797542 - 7.55) < 0.02
      and abs(outer_f * 1.797542 - 11.32) < 0.02,
      "and the radii set instead reproduce Siril's own arithmetic to the "
      "digit it logged: FWHM 1.797542 -> 7.5 and 11.3",
      f"{inner_f * 1.797542:.2f} / {outer_f * 1.797542:.2f}")
setref_src = src[src.index("def _centre_reference"):]
setref_src = setref_src[:setref_src.index("def _reference_frame")]
check('self._cmd("setref"' in setref_src and "best_i + 1" in setref_src,
      "the reference is moved with setref, one-based as Siril counts")
check("_register(seq)\n        self._centre_reference(seq)" in src,
      "and it runs AFTER register, which picks its own reference and "
      "would otherwise overwrite the choice")
check("weighted_fwhm" in setref_src,
      "the quality that decides is Siril's own weighted FWHM, read from "
      "the registration data rather than measured again")
check('getattr(data, "rx"' in setref_src
      and 'getattr(data, "ry"' in setref_src,
      "the frame size comes from the SEQUENCE, not from a FITS read — the "
      "file read failed on a real run and took the drift filter with it")
sat_src = src[src.index("def _target_saturation"):]
sat_src = sat_src[:sat_src.index("# -- calibration")]
check("memmap=False" in sat_src,
      "and the pixel read that decides saturation does not memory-map: "
      "astropy refuses to map a file carrying BZERO/BSCALE/BLANK, which "
      "Siril's compressed frames do")
scan_src = src[src.index("Aperture scan produced nothing usable") - 1400:]
scan_src = scan_src[:scan_src.index("Aperture scan produced nothing usable")]
check("dyn_ratio" in scan_src,
      "a failed aperture scan hands the aperture BACK to Siril — without "
      "that the run measures at the last radius the scan tried, one it "
      "had just rejected")
check("seqapplyreg" in setref_src and "Trim" in setref_src,
      "when no reference can rescue the run it says so and names the two "
      "ways out, rather than moving the reference pointlessly")

print("\n8q3) the native photometry engine, measured against known truth")
# Siril's light_curve moves each box by the registration alone and lost
# half of a drifting run (67 of 140, measured); seqpsf -followstar loses
# nothing but its numbers are unreachable from a script. So the frames
# are measured HERE, and every claim below is a measurement against a
# synthetic truth, not a code-shape check.
_rng = np.random.default_rng(42)

def _mkstar(shape, x, y, flux, sigma, sky=100.0):
    ys, xs = np.mgrid[0:shape[0], 0:shape[1]]
    lam = sky + flux / (2 * np.pi * sigma ** 2) * np.exp(
        -(((xs - x) ** 2 + (ys - y) ** 2) / (2 * sigma ** 2)))
    return _rng.poisson(lam).astype(float)

cen_f = ns["refine_centroid"]
aph_f = ns["aperture_photometry"]
img = _mkstar((60, 60), 30.37, 28.81, 60000, 1.6)
got_c = cen_f(img, 34.0, 25.0)
check(got_c is not None
      and math.hypot(got_c[0] - 30.37, got_c[1] - 28.81) < 0.15,
      "a centroid seeded 5 px off lands subpixel on the true centre — "
      "this is the follow-star light_curve lacks", str(got_c))
check(cen_f(img, 3.0, 3.0) is None,
      "a box that leaves the frame is None, not a truncated centroid")

wgt = ns["circle_weights"]((31, 31), 15.0, 15.0, 8.0)
check(abs(float(wgt.sum()) / (math.pi * 64.0) - 1.0) < 0.005,
      "subpixel aperture weights integrate to the circle's area within "
      "0.5% — and after sky subtraction an AREA error only couples to "
      "the residual sky error, second order for relative photometry",
      f"{float(wgt.sum()):.3f} vs {math.pi * 64.0:.3f}")
areas = [float(ns["circle_weights"]((31, 31), 15.0 + fr, 15.0, 8.0).sum())
         for fr in (0.0, 0.25, 0.5)]
check(max(areas) - min(areas) < 0.3,
      "and the area is SMOOTH under subpixel centre shifts — a binary "
      "mask steps by whole pixels as the centroid moves between frames, "
      "which is scatter with the cadence of the seeing",
      str([f"{a:.3f}" for a in areas]))

fls = []
for _ in range(30):
    im = _mkstar((80, 80), 40.2, 39.7, 80000, 1.6)
    rows, _sky, _ssig, _pk = aph_f(im, 40.2, 39.7, [5.6], 10, 15, 1.0)
    fls.append(rows[5.6][0])
fls = np.asarray(fls)
truth = 80000 * (1.0 - math.exp(-5.6 ** 2 / (2 * 1.6 ** 2)))
check(abs(fls.mean() / truth - 1.0) < 0.01,
      "the flux in 3.5 sigma matches the analytic Gaussian integral to "
      "1%", f"{fls.mean():.0f} vs {truth:.0f}")
rows, _sky, _ssig, _pk = aph_f(_mkstar((80, 80), 40.2, 39.7, 80000, 1.6),
                               40.2, 39.7, [5.6], 10, 15, 1.0)
pred = rows[5.6][1]
check(0.6 < pred / fls.std() < 1.6,
      "and the CCD-equation error agrees with the empirical scatter of "
      "30 independent Poisson realisations",
      f"predicted {pred:.0f}, empirical {fls.std():.0f}")
sat = aph_f(np.full((60, 60), 100.0)
            + 70000.0 * (np.hypot(*np.mgrid[0:60, 0:60] -
                                  np.array([[[30]], [[30]]])) < 2),
            30, 30, [5.6], 10, 15, 1.0, sat_adu=65535 * 0.98)
check(sat is not None and math.isinf(sat[3]),
      "a clipped core reports an infinite peak, which the caller reads "
      "as: this frame's flux is not a measurement")

ens_f = ns["ensemble_relative_mags"]
n = 100
c_a = np.full(n, 10000.0) + _rng.normal(0, 20, n)
c_b = np.full(n, 30000.0) + _rng.normal(0, 40, n)
c_b[50:] = np.nan
t_f = np.full(n, 20000.0) + _rng.normal(0, 30, n)
mag2, _err2 = ens_f(t_f, [c_a, c_b])
step = abs(np.nanmedian(mag2[:50]) - np.nanmedian(mag2[50:]))
check(step < 0.005,
      "a comp that vanishes mid-run steps the ensemble by under 5 mmag — "
      "normalised members; a raw flux sum would step by ~440 mmag, the "
      "exact shape of an ingress", f"{1000 * step:.2f} mmag")

rank_f = ns["rank_comps_by_scatter"]
quiet = [np.full(n, 10000.0) + _rng.normal(0, 15, n) for _ in range(4)]
wob = (np.full(n, 10000.0) + _rng.normal(0, 15, n)
       + 300.0 * np.sin(np.arange(n) / 4.0))
keep2, sc2 = rank_f(quiet + [wob])
check(keep2 == [True, True, True, True, False],
      "a comp with a SLOW 30 mmag wobble is dropped — scored by total "
      "robust scatter, not point-to-point, precisely because slow "
      "structure written inverted into the target is what a fake transit "
      "looks like", str([f"{1000 * v:.1f}" for v in sc2]))
keep3, _ = rank_f([quiet[0], wob])
check(keep3 == [True, True],
      "but with only two comps nobody is dropped — one comp is no "
      "ensemble and zero comps un-calibrates the run silently")

p2p_f = ns["point_to_point_sigma"]
base = _rng.normal(0, 0.002, 200)
tr = base.copy()
tr[80:120] -= 0.02
check(abs(p2p_f(tr) - p2p_f(base)) < 0.3 * p2p_f(base)
      and np.std(tr) > 3 * p2p_f(tr),
      "the aperture is judged by point-to-point noise, which a 20 mmag "
      "transit barely moves while the plain standard deviation triples — "
      "an aperture chooser on std would prefer whatever washes the "
      "transit out",
      f"p2p {1000 * p2p_f(tr):.2f} vs std {1000 * np.std(tr):.2f} mmag")

f2r = ns["frame_to_ref"]
r2f2 = ns["ref_to_frame"]
H70 = [1.0, -0.0016, 75.26, 0.0016, 1.0, 24.85, 0.0, 0.0, 1.0]
fp = r2f2(H70, 371.1, 323.3, 650, 500)
bk = f2r(H70, fp[0], fp[1], 650, 500)
nat_src = src[src.index("def _native_photometry"):]
nat_src = nat_src[:nat_src.index("def _run_light_curve")]
check('hdr.get("DATE-OBS"' in nat_src
      and nat_src.index('hdr.get("DATE-OBS"')
      < nat_src.index("when.isoformat()"),
      "the native engine stamps each point from the frame's OWN header, "
      "with sirilpy's date_obs only as fallback — ImgData.date_obs came "
      "back empty on a real N.I.N.A. run: 83 good magnitudes, zero "
      "usable time stamps, silent fallback to Siril")
late_src = nat_src[nat_src.index("yield_frac"):]
silent = [m.start() for m in re.finditer(r"return None", late_src)
          if "_emit" not in late_src[max(0, m.start() - 700):m.start()]]
check(not silent,
      "and every bail-out after the measuring starts SAYS why before "
      "handing over to Siril — the silent one was found only because the "
      "fallback's log lines appeared after the engine had already "
      "printed its aperture table", str(silent))
check(math.hypot(bk[0] - 371.1, bk[1] - 323.3) < 1e-9,
      "frame_to_ref inverts ref_to_frame exactly — needed because setref "
      "moves the DETECTION frame without rebasing the homographies "
      "(measured: after setref 70 the .seq keeps the identity at image "
      "35), so detected positions must ride through the detection "
      "frame's own H before any seeding")

print("\n8q7) error-bar calibration, measured over synthetic nights")
# 24 independent nights of the same 12 mmag transit at 4 mmag per point
# with an airmass ramp in the design.  The run-to-run scatter of the
# recovered parameters is the TRUTH the reported bars must match.
_rng7 = np.random.default_rng(21)
_n7 = 140
_t7 = np.linspace(0.0, 0.22, _n7)
_X7 = 1.1 + 1.4 * (_t7 / 0.22) ** 2
_tmpl7 = ns["ld_template"](0.10, 0.0)
_sh7 = ns["ld_shape"](_t7, 0.11, 0.055, _tmpl7)
_deps7, _dbars7, _t0s7, _tbars7 = [], [], [], []
for _ in range(24):
    _m7 = (0.004 * _rng7.standard_normal(_n7) + 0.012 * _sh7
           + 0.008 * (_X7 - _X7.mean()))
    _f7 = ns["fit_transit"](_t7, _m7, bases={"airmass": _X7})
    if _f7 is None:
        continue
    _deps7.append(_f7["depth_mmag"])
    _dbars7.append(_f7["depth_sigma_mmag"])
    _t0s7.append(_f7["t0"])
    _tbars7.append(_f7["t0_sigma_s"])
check(len(_deps7) >= 20, "the fits converge night after night",
      f"{len(_deps7)} of 24")
_d_true = float(np.std(_deps7))
_d_bar = float(np.median(_dbars7))
check(0.7 < _d_true / _d_bar < 1.35,
      "the DEPTH bar is calibrated within ~30% of the true run-to-run "
      "scatter — it comes from the covariance of the joint solve now; "
      "the two-box formula it replaces was 26% optimistic, and that "
      "number goes into the AAVSO file",
      f"true {_d_true:.2f} vs bar {_d_bar:.2f} mmag")
_t_true = 86400.0 * float(np.std(_t0s7))
_t_bar = float(np.median(_tbars7))
check(_t_bar >= 0.9 * _t_true,
      "the T0 bar COVERS the true scatter — overcoverage is the safe "
      "failure direction for a number that feeds O−C claims",
      f"true {_t_true:.0f} vs bar {_t_bar:.0f} s")
check(_t_bar <= 2.5 * _t_true,
      "but not by more than a factor ~2 — measured 1.75x at this "
      "configuration, from profiling over the systematics; a wider gap "
      "would make every O−C 'consistent' and the bar useless",
      f"true {_t_true:.0f} vs bar {_t_bar:.0f} s")

# --- AAVSO header carries exactly one #NOTES key -----------------------
aav_src = src[src.index("def _write_aavso"):src.index("def _write_csv")]
check(aav_src.count('"#NOTES=') == 1
      and "no transit claimed" in aav_src,
      "the no-transit case merges into the single #NOTES line — two "
      "#NOTES keys in one header, and which one a parser keeps is the "
      "parser's mood")

print("\n8q8) error bars survive Siril's [0,1] float normalisation")
# Siril's calibrated output is 16-bit ADU divided by 65535.  A gain in
# e-/ADU must scale with the data or the CCD equation is fed the wrong
# units — measured on the first calibrated live run: err 100x off.
_rng8 = np.random.default_rng(4)

def _pstar01(flux_e, sigma, sky_e=6000.0, g=0.8):
    ys, xs = np.mgrid[0:80, 0:80]
    lam = sky_e + flux_e / (2 * np.pi * sigma ** 2) * np.exp(
        -(((xs - 40.2) ** 2 + (ys - 39.7) ** 2) / (2 * sigma ** 2)))
    return _rng8.poisson(lam) / g / 65535.0

_fl8 = []
for _ in range(30):
    _im8 = _pstar01(120000, 1.6)
    _r8, *_rest = ns["aperture_photometry"](_im8, 40.2, 39.7, [5.6],
                                            10, 15, 0.8 * 65535.0)
    _fl8.append(_r8[5.6][0])
_true8 = float(np.std(_fl8))
_im8 = _pstar01(120000, 1.6)
_r8s, *_x1 = ns["aperture_photometry"](_im8, 40.2, 39.7, [5.6],
                                       10, 15, 0.8 * 65535.0)
_r8n, *_x2 = ns["aperture_photometry"](_im8, 40.2, 39.7, [5.6],
                                       10, 15, 0.8)
check(0.5 < _r8s[5.6][1] / _true8 < 2.0,
      "with the x65535 scaling the predicted error brackets the true "
      "Poisson scatter of [0,1]-normalised frames",
      f"pred {_r8s[5.6][1]:.6f} vs true {_true8:.6f}")
check(_r8n[5.6][1] / _true8 > 10.0,
      "while an unscaled e-/ADU gain on the same frames is off by two "
      "orders of magnitude — the state the first calibrated run exposed",
      f"{_r8n[5.6][1] / _true8:.0f}x off")
check("gain * 65535.0" in nat_src,
      "and the native engine applies the scaling exactly when it detects "
      "the [0,1] convention")

print("\n8q6) second audit pass — beta bias, template truth, invariants")
# --- red-noise beta: the small-sample correction must LIFT the rungs ---
# E[std(x, ddof=1)] sits BELOW sigma by c4(M).  The first correction
# multiplied expected by sqrt(M/(M-1)) — the wrong direction — and drove
# white-noise rungs from 0.92-0.98 down to 0.80-0.94.  A deflated beta
# overstates every significance on exactly the nights that need the
# correction.  With c4 the rungs centre on 1.
_rng6 = np.random.default_rng(9)
_beta_f = ns["red_noise_beta"]
_n6 = 200
_t6 = np.linspace(0.0, 0.2, _n6)
_rungs = []
for _ in range(120):
    _rows6 = _beta_f(_t6, _rng6.normal(0, 0.004, _n6), 0.05)[1]
    _rungs.extend(b for _w, b, _m, _k in _rows6)
_med_rung = float(np.median(_rungs))
check(0.95 < _med_rung < 1.05,
      "white-noise ladder rungs centre on 1.0 — the pre-clamp ratios, "
      "straight from the rows the report prints",
      f"median rung {_med_rung:.3f} over {len(_rungs)} rungs")
_red_betas = []
for _ in range(60):
    _slow = np.interp(_t6, np.linspace(0, 0.2, 12),
                      _rng6.normal(0, 0.004, 12))
    _red_betas.append(_beta_f(_t6, _slow + _rng6.normal(0, 0.004, _n6),
                              0.05)[0])
check(float(np.median(_red_betas)) > 1.5,
      "while genuinely correlated noise with the transit's own timescale "
      "still reads well above 1", f"median {np.median(_red_betas):.2f}")
check("math.gamma" in src and "sqrt(n_bins / float(n_bins - 1))" not in src,
      "and the correction in the source is c4, not the sqrt(M/(M-1)) "
      "that pushed the wrong way")

# --- the 1D radial quadrature against an independent 2D integration ----
def _blocked_2d(z, rp, u1, u2, ngrid=700):
    xs = np.linspace(-1, 1, ngrid)
    dA = (xs[1] - xs[0]) ** 2
    XX, YY = np.meshgrid(xs, xs)
    r2 = XX * XX + YY * YY
    disc = r2 <= 1.0
    mu = np.sqrt(np.clip(1 - r2, 0, None))
    II = (1 - u1 * (1 - mu) - u2 * (1 - mu) ** 2) * disc
    cover = ((XX - z) ** 2 + YY ** 2) <= rp * rp
    return float((II * cover).sum() / II.sum())

for _rp, _b, _phase in ((0.10, 0.0, 0.30), (0.14, 0.5, 0.0)):
    _ph6, _sh6 = ns["ld_template"](_rp, _b, 0.35, 0.23)
    _xmax = math.sqrt((1 + _rp) ** 2 - _b * _b)
    _z = math.hypot(_phase * 2 * _xmax, _b)
    _peak2d = _blocked_2d(_b, _rp, 0.35, 0.23)
    _got1d = float(np.interp(_phase, _ph6, _sh6)) * _peak2d
    _got2d = _blocked_2d(_z, _rp, 0.35, 0.23)
    check(abs(_got1d - _got2d) < 3e-4,
          f"the arc quadrature matches a blind 2D integration at "
          f"rp={_rp}, b={_b}, phase={_phase} — the docstring claimed this "
          "verification; now the suite owns it",
          f"{_got1d:.6f} vs {_got2d:.6f}")

# --- the merge point enforces the finiteness invariant -----------------
run_src = src[src.index("def _run("):src.index("def _write_aavso")]
check("finite = np.isfinite(jd) & np.isfinite(mag)" in run_src
      and "jd, mag = jd[finite], mag[finite]" in run_src,
      "jd/mag finiteness is enforced once at the merge point — the fit "
      "filters internally and returns FILTERED-size arrays, so a single "
      "NaN row would silently misalign every CSV column after it")

print("\n8q5) audit fixes, each measured against truth")
# --- ensemble error must be flux-weighted, like the reference itself ---
_rng5 = np.random.default_rng(3)
_meds = [1e5, 1e4, 2e3]
_n5 = 4000
_comps5 = [_rng5.normal(m, math.sqrt(m), _n5) for m in _meds]
_errs5 = [np.full(_n5, math.sqrt(m)) for m in _meds]
_tf5 = _rng5.normal(2e4, math.sqrt(2e4), _n5)
_mag5, _err5 = ns["ensemble_relative_mags"](
    _tf5, _comps5, np.full(_n5, math.sqrt(2e4)), _errs5)
_pred = float(np.nanmedian(_err5))
_emp = float(np.std(_mag5))
check(abs(_pred / _emp - 1.0) < 0.10,
      "the predicted per-point error matches 4000 Poisson realisations on "
      "comps of 100k/10k/2k ADU — the reference is flux-weighted, so its "
      "error must be too", f"pred {1000 * _pred:.2f} vs emp "
      f"{1000 * _emp:.2f} mmag")
_equal_split = math.sqrt(2e4 / 2e4 ** 2
                         + sum(m / m ** 2 for m in _meds) / 9.0) * 1.0857
check(_equal_split / _emp > 1.3,
      "while the equal-split formula this replaces overstates by >30% on "
      "the same data — it divided every comp's variance by N^2 although "
      "the faint comp barely enters the weighted reference",
      f"{1000 * _equal_split:.2f} vs {1000 * _emp:.2f} mmag")

# --- the yield note names whichever engine measured --------------------
_note_f = ns["photometry_yield_note"]
_sev_n, _msg_n = _note_f(83, 178, True, engine="This script")
check("Siril" not in _msg_n and "This script" in _msg_n,
      "on the native path the note never says 'Siril kept' — the first "
      "full native run printed '83 points measured by this script' "
      "immediately followed by 'Siril kept 83 of 178'")
_sev_s, _msg_s = _note_f(83, 178, True, engine="Siril")
check("pixel out of range" in _msg_s and "pixel out of range" not in _msg_n,
      "and Siril's reason codes are quoted only when Siril measured — "
      "they do not exist on the native path")
_sev_ok, _msg_ok = _note_f(170, 178, False, engine="This script")
check(_msg_ok is None, "a healthy yield still says nothing")

# --- source honesty: gain provenance and centred magnitudes ------------
check("gain_src" in nat_src and "assumed" in nat_src,
      "the gain line says where the number came from — it used to print "
      "'from the header' even when no header card was usable and 1.0 was "
      "an assumption")
check('float(hdr.get(card))' in nat_src
      and '("GAIN", 10.0)' in nat_src,
      "and GAIN (the camera SETTING, 0-500 arbitrary units) is only "
      "believed in the range real e-/ADU conversion factors live in — "
      "GAIN=100 read as e-/ADU would multiply every error bar tenfold")
check("np.nanmedian(mag)" in nat_src,
      "native magnitudes are centred on their median — the raw zero point "
      "sits near -10 and reads as broken in every plot and CSV")

# --- fit_transit end to end against synthetic truth --------------------
_rngF = np.random.default_rng(11)
_nF = 140
_tF = np.linspace(0.0, 0.22, _nF)
_XF = 1.1 + 1.4 * (_tF / 0.22) ** 2
_tmplF = ns["ld_template"](0.10, 0.0)
_shapeF = ns["ld_shape"](_tF, 0.11, 0.055, _tmplF)
_magF = (0.004 * _rngF.standard_normal(_nF) + 0.020 * _shapeF
         + 0.008 * (_XF - _XF.mean()))
_fitF = ns["fit_transit"](_tF, _magF, bases={"airmass": _XF})
check(_fitF is not None and abs(_fitF["depth_mmag"] - 20.0) < 3.0,
      "a 20 mmag limb-darkened transit on a quadratic airmass ramp is "
      "recovered to better than 3 mmag with the systematics fitted "
      "simultaneously", f"{_fitF['depth_mmag']:.1f} mmag")
check(abs(_fitF["t0"] - 0.11) * 86400.0 < 3.0 * _fitF["t0_sigma_s"],
      "the mid-time lands within 3 error bars of the truth",
      f"off by {abs(_fitF['t0'] - 0.11) * 86400.0:.0f} s, "
      f"bar {_fitF['t0_sigma_s']:.0f} s")
check(_fitF["significance"] > 10.0 and _fitF["detected"],
      "and the detection is unambiguous",
      f"{_fitF['significance']:.1f} sigma")
check(abs(_fitF["airmass_slope"] - 0.008) < 0.004,
      "the airmass coefficient comes back in readable units near its true "
      "value", f"{_fitF['airmass_slope']:.4f} vs 0.0080")
_mag0 = 0.004 * _rngF.standard_normal(_nF) + 0.008 * (_XF - _XF.mean())
_fit0 = ns["fit_transit"](_tF, _mag0, bases={"airmass": _XF})
check(_fit0 is None or not _fit0["detected"],
      "the same night WITHOUT a transit is not claimed — the two-sided "
      "in/out test and the red-noise correction hold the floor",
      "" if _fit0 is None else f"{_fit0['significance']:.2f} sigma")

print("\n8q4) both measurement paths feed the results dict completely")
# The native engine's first FULL run — comps ranked, aperture chosen,
# transit FITTED — died one line before writing its results:
# UnboundLocalError on `aperture`, a name born only inside the Siril
# fallback branch. This walks the actual AST of _run: any name assigned
# ONLY in the fallback branch and read after the merge is a crash waiting
# for whichever path skipped it.
_tree_q4 = ast.parse(src)
_run_fn = next(n for n in ast.walk(_tree_q4)
               if isinstance(n, ast.FunctionDef) and n.name == "_run")
_branch = None
for n in ast.walk(_run_fn):
    if isinstance(n, ast.If):
        t = ast.get_source_segment(src, n.test) or ""
        if "native is not None" in t:
            _branch = n
            break
check(_branch is not None,
      "the native/fallback branch exists in _run at all")

def _q4_assigned(nodes):
    out = set()
    for nd in nodes:
        for x in ast.walk(nd):
            if isinstance(x, ast.Assign):
                for tgt in x.targets:
                    for y in ast.walk(tgt):
                        if isinstance(y, ast.Name):
                            out.add(y.id)
            elif isinstance(x, (ast.AugAssign, ast.AnnAssign)):
                if isinstance(x.target, ast.Name):
                    out.add(x.target.id)
            elif isinstance(x, ast.For) and isinstance(x.target, ast.Name):
                out.add(x.target.id)
    return out

if _branch is not None:
    _only_else = _q4_assigned(_branch.orelse)
    _only_if = _q4_assigned(_branch.body)
    _before, _after, _seen = [], [], False
    for stmt in _run_fn.body:
        if stmt.lineno <= _branch.lineno <= (stmt.end_lineno or stmt.lineno):
            _seen = True
            continue
        (_after if _seen else _before).append(stmt)
    _pre = _q4_assigned(_before)
    _post_loads = set()
    for stmt in _after:
        for x in ast.walk(stmt):
            if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load):
                _post_loads.add(x.id)
    _risky = sorted((_only_else - _only_if - _pre) & _post_loads)
    check(not _risky,
          "no name is assigned only in the Siril fallback branch and read "
          "after the merge — `aperture` and `dat` both were, and the "
          "first one crashed a run AFTER the transit fit had succeeded",
          str(_risky))
    check("aperture" in _pre and "dat" in _pre,
          "and the two that crashed are now initialised before the branch")

print("\n8s) a submission is held to a higher bar than the report")
src = open(SRC).read()
gate = src[src.index("def _write_aavso"):]
gate = gate[:gate.index("\n    def ", 10)]
for token, why in (
        ('r.get("target_saturated")',
         "a saturated target means the core carries no flux information, so "
         "the depth is not a measurement and must not reach a public "
         "database"),
        ('r.get("yield_severity") == "bad"',
         "and neither must a run whose surviving frames are the ones seeing "
         "happened to favour"),
        ('r.get("time_system") != "BJD_TDB"',
         "and the header declares BJD_TDB, so JD_UTC under it would be an "
         "8-minute error nobody downstream can see")):
    check(token in gate, why, token)
# Measured on the WASP-75 run this was written for.
n_pts, n_frm = 11, 178
sev, note = ns["photometry_yield_note"](n_pts, n_frm, True)
print(f"   {n_pts} of {n_frm} frames, target saturated -> severity {sev!r}")
check(sev == "bad",
      "the real run that exposed this — 11 of 178 frames, saturated target — "
      "is judged 'bad', which is what now stops the submission",
      f"{sev!r}")

print("\n8t) the aperture scan cannot be won by measuring less")
# Identical underlying noise, a night whose seeing swings 3x. An aperture
# surviving only on the quiet frames shows LOWER scatter for that reason
# alone, so least-scatter alone would crown the one that measured least.
rng8t = np.random.default_rng(7)
n8t = 150
seeing = 1.0 + 1.8 * np.abs(np.sin(np.linspace(0.0, 3.1, n8t)))
quiet = np.argsort(seeing)
sc = {}
for frac in (1.0, 0.8, 0.07):
    keep = quiet[: max(5, int(frac * n8t))]
    vals = [float(ns["_mad_std"](rng8t.normal(0, 0.004, n8t)[keep] * seeing[keep])
                  * 1000.0) for _ in range(200)]
    sc[frac] = float(np.median(vals))
    print(f"   measured {frac:5.0%} of frames -> {sc[frac]:5.2f} mmag")
check(sc[0.07] < 0.6 * sc[1.0],
      "a candidate surviving on 7% of frames reads far quieter than the full "
      "sample on THE SAME noise — selection, not a better aperture",
      f"{sc[0.07]:.2f} vs {sc[1.0]:.2f} mmag")
check(sc[0.8] > 0.85 * sc[1.0],
      f"at {ns['APERTURE_MIN_YIELD_RATIO']:.0%} yield the bias is small "
      "enough to live with, which is why that is the cut",
      f"{sc[0.8]:.2f} vs {sc[1.0]:.2f} mmag")
scan = src[src.index("def _scan_aperture"):]
scan = scan[:scan.index("\n    def ", 10)]
check("APERTURE_MIN_YIELD_RATIO * top" in scan,
      "so candidates are compared only against the best YIELD, not ranked on "
      "scatter alone")
check("not compared" in scan,
      "and the ones dropped are named with the reason, because a silent "
      "exclusion looks like it was never a candidate")

print("\n8i) every name a method uses actually resolves")
# `_log_swallowed` was called from three exception handlers and never
# defined.  Nothing noticed for weeks: all three are fallbacks for cases
# that had not come up, and when one finally did, the handler would have
# raised NameError over the top of the error it existed to absorb.
_builtin = set(dir(__builtins__)) | set(dir(__builtins__.__dict__ if hasattr(
    __builtins__, "__dict__") else {}))
try:
    import builtins as _b
    _builtin |= set(dir(_b))
except ImportError:
    pass
_defined = set(_builtin)
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        _defined.add(node.name)
    elif isinstance(node, (ast.Import, ast.ImportFrom)):
        for a in node.names:
            _defined.add((a.asname or a.name).split(".")[0])
    elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for t in targets:
            for sub in ast.walk(t):
                if isinstance(sub, ast.Name):
                    _defined.add(sub.id)

def _unresolved(fn):
    """Free names in one function that nothing defines anywhere."""
    local = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
    if fn.args.vararg:
        local.add(fn.args.vararg.arg)
    if fn.args.kwarg:
        local.add(fn.args.kwarg.arg)
    used = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Name):
            (local.add(n.id) if isinstance(n.ctx, ast.Store) else used.add(n.id))
        elif isinstance(n, ast.ExceptHandler) and n.name:
            local.add(n.name)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not fn:
            local.add(n.name)
            local |= {a.arg for a in n.args.args}
        elif isinstance(n, (ast.Lambda,)):
            local |= {a.arg for a in n.args.args}
        elif isinstance(n, ast.comprehension):
            for sub in ast.walk(n.target):
                if isinstance(sub, ast.Name):
                    local.add(sub.id)
    return sorted(used - local - _defined)

# Top-level functions and methods only. A NESTED function is already
# covered by scanning its parent -- and scanning it on its own would flag
# every closure variable, which is exactly what a closure is for.
_scan = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
for _c in tree.body:
    if isinstance(_c, ast.ClassDef):
        _scan += [n for n in _c.body if isinstance(n, ast.FunctionDef)]
missing = []
for node in _scan:
    bad = _unresolved(node)
    if bad:
        missing.append((node.name, bad))
print(f"   scanned {len(_scan)} functions and methods")
check(not missing,
      "no function calls a name that is defined nowhere in the module",
      "; ".join(f"{fn}: {', '.join(names)}" for fn, names in missing))
check("_log_swallowed" in _defined,
      "and _log_swallowed in particular exists, since three handlers call it")

print("\n8q) one satellite must not cost the detection")
clipper = ns["sigma_clip_series"]
fitq = ns["fit_transit"]
shpq = shape
tq = np.linspace(0.0, 5 / 24, 150)
T0Q, DURQ, DEPTHQ = 0.5 * 5 / 24, 0.30 * 5 / 24, 0.012
trq = DEPTHQ * shpq(tq, T0Q, DURQ, 0.15)
insideq = trq > 0.0

# The failure this closes, measured before the fix: a single 100 mmag
# point on a real 12 mmag transit took the significance from 12.1 to 3.2
# sigma -- under the 4.0 floor, so a measured transit read as "not
# claimed". The parameters barely moved; it was the divisor. Two changes
# fix it: a robust post-fit scatter (12.1 -> 6.9) and removing the point
# (6.9 -> 12.1).
rng = np.random.default_rng(77)
sig_clean, sig_hit = [], []
for _ in range(12):
    base = trq + rng.normal(0.0, 0.004, tq.size)
    f = fitq(tq, base)
    if f:
        sig_clean.append(f["significance"])
    hit = base.copy()
    hit[int(rng.integers(20, 130))] -= 0.10
    keep, n, note = clipper(tq, hit)
    f2 = fitq(tq[keep], hit[keep])
    if f2:
        sig_hit.append(f2["significance"])
print(f"   clean {np.median(sig_clean):.1f}s   with a 100 mmag spike, "
      f"clipped {np.median(sig_hit):.1f}s")
check(np.median(sig_hit) > 0.8 * np.median(sig_clean),
      "a 100 mmag spike costs almost nothing once it is removed — it used "
      "to cost 12.1 sigma down to 3.2",
      f"{np.median(sig_clean):.1f} -> {np.median(sig_hit):.1f}")

# It must not eat the transit. The reference is a running median far
# shorter than any transit, so a smooth multi-point dip passes through.
for depth in (0.012, 0.030, 0.060):
    y = depth * shpq(tq, T0Q, DURQ, 0.15) + rng.normal(0.0, 0.004, tq.size)
    keep, n, _note = clipper(tq, y)
    eaten = int((~keep & (depth * shpq(tq, T0Q, DURQ, 0.15) > 0)).sum())
    check(eaten <= 1,
          f"a real {depth*1000:.0f} mmag transit keeps its points",
          f"{eaten} clipped inside")

# And it must not quietly delete a bad night into a good-looking one.
noisy = trq + rng.standard_t(2, tq.size) * 0.004
_k, n_noisy, note_noisy = clipper(tq, noisy)
print(f"   heavy-tailed night: {n_noisy} removed")
# A third of the run beyond the threshold is not an outlier population.
# (Noise on top matters: without it the running median follows the pattern
# exactly, the residual MAD is zero and the function correctly reports it
# has nothing to measure a threshold against.)
huge = trq + rng.normal(0.0, 0.004, tq.size)
huge[::3] += 0.05
_k2, n_huge, note_huge = clipper(tq, huge)
print(f"   a third of the run outlying: {n_huge} removed — '{note_huge}'")
check(n_huge == 0 and "not an outlier population" in note_huge,
      "refused, with the reason — removing a third of a light curve to "
      "make it look better is the opposite of the job", note_huge)
flat = np.zeros(tq.size)
_k3, n_flat, note_flat = clipper(tq, flat)
check(n_flat == 0 and "zero" in note_flat,
      "and a series with no scatter at all has nothing to clip against, "
      "which is said rather than divided by", note_flat)

print("\n8r) the comparison ensemble is judged by measurement, and the "
      "aperture is chosen")
# Both of these run Siril, so what is pinned here is the arithmetic and
# the guards, not the I/O.
check(ns["COMP_VARIABILITY_RATIO"] >= 2.0,
      "the variability threshold is a RATIO to the ensemble median, not an "
      "absolute mmag — a good night and a poor one differ by a factor")
aps = ns["APERTURE_SCAN_FWHM"]
print(f"   aperture ladder: {aps} x FWHM")
check(len(aps) >= 4 and min(aps) < 1.0 < max(aps),
      "the ladder brackets 1 FWHM on both sides, so the optimum is inside "
      "it rather than at an end", str(aps))
check(ns["APERTURE_INNER_RATIO"] > 1.0
      and ns["APERTURE_OUTER_RATIO"] > ns["APERTURE_INNER_RATIO"],
      "and the sky annulus sits outside the aperture, in that order")
src_all = open(SRC).read()
check("_scan_aperture" in src_all and "-aperture=" in src_all,
      "the scan drives Siril's own setphot rather than reimplementing "
      "photometry")
check("autoring=(aperture is None)" in src_all,
      "and -autoring is switched OFF when a scanned aperture is in use — "
      "leaving it on would silently discard the whole scan")

print("\n8o) T0 carries an error bar, and it is calibrated")
# T0 is the number ExoClock and ETD exist for, and it used to be printed to
# six decimals -- 0.09 s -- with nothing beside it.
t0err = ns["t0_uncertainty"]
chi2nu = ns["chi2_per_dof"]
fitt2 = ns["fit_transit"]
shp2 = shape
mad2 = ns["_mad_std"]

rng = np.random.default_rng(5)
tt2 = np.linspace(0.0, 5 / 24, 150)
T0T, DURT = 0.5 * 5 / 24, 0.30 * 5 / 24
# Measured over 50 runs per depth at 4 mmag on a 120 s cadence:
#     depth   sigma reported   MAD(T0) recovered   ratio   chi2/nu
#      20mm         53.4 s            46.7 s        1.14     1.06
#      12mm         91.4 s            89.5 s        1.02     1.01
#       8mm        133.6 s           136.2 s        0.98     0.97
#       6mm        173.4 s           190.7 s        0.91     0.99
# Twelve runs here is enough to catch a bar that is wrong by a factor,
# which is what the two rejected designs below were.
t0s, sig = [], []
for _ in range(12):
    y = 0.012 * shp2(tt2, T0T, DURT, 0.15) + rng.normal(0.0, 0.004, tt2.size)
    f = fitt2(tt2, y)
    if f and np.isfinite(f["t0_sigma_d"]):
        t0s.append(f["t0"])
        sig.append(f["t0_sigma_d"])
t0s, sig = np.array(t0s), np.array(sig)
scatter = mad2(t0s)
ratio = float(np.median(sig) / scatter) if scatter > 0 else float("inf")
print(f"   sigma {np.median(sig)*86400:.0f} s vs recovered scatter "
      f"{scatter*86400:.0f} s  ->  ratio {ratio:.2f}")
check(len(sig) >= 8, "the probe produced fits with a finite bar", str(len(sig)))
check(0.5 < ratio < 2.0,
      "the bar tracks the run-to-run scatter within a factor of two — the "
      "delta-chi2 walk it replaced plateaued at 0.7 cadences and read 0.50 "
      "of the truth on an 8 mmag dip", f"{ratio:.2f}")
check(np.median(sig) * 86400 < 300,
      "and it is a useful number, not the whole run")

# The coarse grid quantised T0 to (0.7*span)/120 = 105 s on a 5 h run: over
# 60 runs of a deep transit EVERY fit returned the same value, and the MAD
# at every lower depth was exactly 1.4826 x one grid step. The refinement
# pass is what removed that.
step = (0.7 * (tt2.max() - tt2.min())) / (ns["FIT_T0_STEPS"] - 1)
uniq = len(set(np.round(np.array(t0s) / step).astype(int)))
print(f"   coarse grid step {step*86400:.0f} s; {len(t0s)} fits landed on "
      f"{len(set(np.round(np.array(t0s), 9)))} distinct T0 values")
check(len(set(np.round(np.array(t0s), 9))) > 2,
      "T0 is no longer rounded onto the coarse grid")

# chi2/nu needs a MODEL-INDEPENDENT noise floor, or it is 1 by construction.
resid = rng.normal(0.0, 0.004, 200)
oot = np.ones(200, dtype=bool)
c_ok = chi2nu(resid, 5, oot)
print(f"   chi2/nu on pure noise: {c_ok:.2f}")
check(0.7 < c_ok < 1.4, "pure noise gives about 1", f"{c_ok:.2f}")
bad = resid.copy()
bad[80:120] += 0.02                       # a 20 mmag lump the model missed
c_bad = chi2nu(bad, 5, oot)
print(f"   chi2/nu with an unmodelled 20 mmag lump: {c_bad:.2f}")
check(c_bad > 2.0,
      "and a feature the model did not describe drives it well above 1 — "
      "which is the whole point of measuring the noise elsewhere",
      f"{c_bad:.2f}")
check(not np.isfinite(chi2nu(np.zeros(3), 5, None)),
      "fewer points than parameters is NaN, not a number")

print("\n8p) the transit and the systematics are fitted TOGETHER")
matcher = ns["match_frames_to_curve"]
n2 = 150
t3 = np.linspace(0.0, 5 / 24, n2)
T0T3, DURT3 = 0.5 * 5 / 24, 0.30 * 5 / 24
transit = 0.012 * shape(t3, T0T3, DURT3)
rng = np.random.default_rng(21)

# The failure a sequential detrend has to guard against, and a
# simultaneous fit cannot have: a basis that CORRELATES with the transit.
# Fitted first and subtracted, such a basis eats the depth. Fitted
# alongside, it cannot -- the transit is its own column.
ramp = (t3 - t3.min()) / np.ptp(t3)          # rises across the run
corr = -shape(t3, T0T3, DURT3) + 0.3 * ramp  # deliberately transit-shaped
for label, basis in (("a plain rising ramp", ramp),
                     ("a basis SHAPED like the transit", corr)):
    depths = []
    for k in range(6):
        y = transit + 0.02 * basis + rng.normal(0.0, 0.003, n2)
        f = fit(t3, y, bases={"probe": basis})
        if f:
            depths.append(f["depth_mmag"])
    got = float(np.median(depths)) if depths else float("nan")
    print(f"   {label:<34} depth {got:6.2f} mmag of 12.00")
    check(abs(got - 12.0) < 2.5,
          f"the depth survives {label} — a sequential detrend would have "
          f"absorbed it", f"{got:.2f} mmag")

# Systematics are still removed, not merely tolerated.
fwhm = 2.0 + 1.2 * ramp + rng.normal(0, 0.05, n2)
sky = 300 + 900 * ramp ** 2 + rng.normal(0, 5, n2)
sysd = (0.010 * (fwhm - fwhm.mean()) / fwhm.std()
        + 0.008 * (sky - sky.mean()) / sky.std())
y3 = transit + sysd + rng.normal(0.0, 0.004, n2)
f3 = fit(t3, y3, bases={"fwhm": fwhm, "sky": sky})
oot3 = transit == 0.0
before = float(np.std(y3[oot3]) * 1000.0)
after = float(np.std(f3["detrended"][oot3]) * 1000.0)
print(f"   out-of-transit RMS {before:.2f} -> {after:.2f} mmag, "
      f"bases {f3['base_note']}")
check(after < before / 3.0,
      "a seeing plus sky trend comes out down to the noise floor",
      f"{before:.2f} -> {after:.2f} mmag")
check(set(f3["bases"]) == {"fwhm", "sky"}, "and both bases were used",
      str(f3["bases"]))

# Guards on the design matrix.
bd = ns["build_design"]
_fx, names, note, _o, _s = bd(n2, {"flat": np.ones(n2)})
check(names == [] and "no spread" in note,
      "a basis with no spread is dropped and named", note)
_fx, names, note, _o, _s = bd(n2, {"short": np.ones(5)})
check(names == [] and "wrong length" in note,
      "and so is one of the wrong length", note)
_fx, names, _n, _o, scales = bd(n2, {"big": sky})
check(abs(float(np.std(_fx[:, 1])) - 1.0) < 1e-9,
      "every basis is scaled to unit spread, so airmass (1-3) and sky "
      "(hundreds of ADU) can share one matrix without wrecking it")

# Siril photometers a SUBSET, and light_curve.dat carries no frame number.
jd_f = np.linspace(2461267.8, 2461267.9, 20)
picked = [0, 3, 4, 9, 15, 19]
got_idx = matcher(jd_f[picked], jd_f)
check(list(got_idx) == picked,
      "rows are paired with their frames by time, exactly", str(list(got_idx)))
check(matcher(np.array([2461200.0]), jd_f)[0] == -1,
      "a row with no frame within tolerance is -1, not the nearest one")

print("\n9) the target snaps to a detected star, never to a typed number")
pick = ns["pick_target"]


class _S2(_Star):
    def __init__(self, x, y, snr, ra=0.0, dec=0.0):
        super().__init__(x, y, snr)
        self.ra, self.dec = ra, dec


field = [_S2(100, 100, 50, 10.0, 20.0), _S2(800, 600, 900, 10.5, 20.5)]
check(pick(field, "brightest")[:2] == (800, 600), "brightest picks the brightest")
got = pick(field, "pixel", want_xy=(104, 97))
check(got[:2] == (100, 100) and "px from the position" in got[2],
      "a pixel guess snaps to the nearby star and says how far it moved")
got = pick(field, "radec", want_radec=(10.49, 20.49))
check(got[:2] == (800, 600), "RA/Dec finds the right star")
check(pick([], "brightest") is None, "an empty field yields None, not a crash")
check(pick([_Star(1, 2, 3)], "radec", want_radec=(1.0, 2.0)) is None,
      "RA/Dec without a plate solve declines rather than guessing")

print("\n10) binning is presentation, and says so by construction")
binner = ns["bin_series"]
bt, bm, be, bn = binner(np.linspace(0, 1, 100), np.linspace(0, 1, 100), 10)
check(bt.size == 10 and int(bn.sum()) == 100,
      "every point lands in exactly one bin", f"{bt.size} bins, {bn.sum()} pts")
check(np.all(np.diff(bt) > 0), "bin centres increase")
check(binner(np.empty(0), np.empty(0), 5)[0].size == 0, "empty in, empty out")

print("\n8q9) suite parity and honest log lines "
      "(from the first fully successful run's feedback)")
# The 12:38 run worked end to end — what was left to fix was presentation:
# the panel title lacked the version, the bottom of the panel didn't match
# the other Svenesis scripts (no coffee button, a lone "?" for help), the
# gain line printed the x65535 float scaling AS the gain ("gain 65535
# e-/ADU assumed"), and the not-used tally printed its masked grouping
# template literally ("607 x N mag fainter than the target").
check('QLabel(f"Svenesis LightCurve {VERSION}")' in src,
      "the left-panel title carries the version like every other script "
      "in the suite — the window title alone is hidden on macOS full-screen")
check('setObjectName("CoffeeButton")' in src
      and "def _show_coffee_dialog" in src
      and "buymeacoffee.com/sramuschkat" in src,
      "the coffee button and its dialog exist, matching the rest of the "
      "suite")
check('QPushButton("Help")' in src and 'QPushButton("?")' not in src,
      "help is a full-width Help button, not the lone '?'")
check("gain_hdr" in nat_src and "gain {gain_hdr:g} e-/ADU" in nat_src,
      "the gain line prints the HEADER gain in e-/ADU — after the x65535 "
      "float scaling the working number is no longer in ADU, and printing "
      "it claimed 'gain 65535 e-/ADU assumed'")

# The tally's group label, run as shipped: extract the nested function.
_gl_src = src[src.index("def _group_label"):]
_gl_src = _gl_src[:_gl_src.index("if len(comps) < MIN_COMPS")]
_gl_ns = {"re": re}
exec(textwrap.dedent(_gl_src), _gl_ns)                 # noqa: S102
_gl = _gl_ns["_group_label"]
check(_gl(["3 mag fainter than the target",
           "6.8 mag fainter than the target"])
      == "3–6.8 mag fainter than the target",
      "a group's numbers come back as a min-max range, not a literal 'N'")
check(_gl(["usable, but only 5 were needed",
           "usable, but only 5 were needed"])
      == "usable, but only 5 were needed",
      "a constant collapses to the single value")
check(_gl(["neighbour 3 px away, inside its own 12 px annulus",
           "neighbour 11 px away, inside its own 12 px annulus"])
      == "neighbour 3–11 px away, inside its own 12 px annulus",
      "each numeric slot ranges independently")
check(_gl(["saturated"]) == "saturated",
      "a reason with no numbers passes through untouched")

print("\n8q10) the frames' OBJECT outranks a stale Target box")
# The box is restored from QSettings, so after switching targets it holds
# the PREVIOUS name — a WASP-75b run was analysed under HAT-P-32's
# ephemeris because 'typed or from_hdr' let the stale box win over an
# OBJECT card that was right all along.
res_src = src[src.index("def _resolve_from_name"):]
res_src = res_src[:res_src.index("def _target_cache")]
check("name = from_hdr or typed" in res_src,
      "the name from the lights' OBJECT card is preferred; the box is the "
      "fallback, not the master")
check("The headers win" in res_src and "OBJECT = {planet!r}" in res_src,
      "a disagreement between box and headers is said out loud, with both "
      "names, not resolved silently")
check("trying the Target box name instead" in res_src,
      "an OBJECT the archive does not know falls back to the typed name — "
      "junk OBJECT cards ('Target', mosaic panels) are what the box is for")
check('opts["resolved_target_name"]' in res_src,
      "the name that actually resolved is recorded for downstream writers")
_aav2 = src[src.index("def _write_aavso"):]
_aav2 = _aav2[:_aav2.index("#DATE,DIFF")]
check('"resolved_target_name"' in _aav2
      and _aav2.index('"resolved_target_name"')
      < _aav2.index('"target_name"'),
      "#TARGET= carries the resolved name first — a submission under the "
      "previous target's name is worse than one under UNKNOWN")

# The UI half of the same trap: the box SHOWED 'HATP-32' on WASP-75
# frames even after the worker learned to prefer OBJECT.  Folder analysis
# now replaces a name that keys to a DIFFERENT target and leaves any
# spelling of the SAME target exactly as typed.
_tk = ns["target_key"]
check(_tk("WASP-75 b") == _tk("WASP-75b") == _tk("wasp75")
      == _tk("WASP 75") == "WASP75",
      "every spelling of one target — planet letter or not — keys the same")
check(_tk("HATP-32") != _tk("WASP-75") and _tk("") == "",
      "different targets key differently, and empty stays empty")
check(_tk("HAT-P-32") == _tk("HATP-32"),
      "survey-prefix hyphens do not split a target from itself")
_probe_src = src[src.index("def _probe_target"):]
_probe_src = _probe_src[:_probe_src.index("def _on_pick_folder")]
check("target_key(existing) != target_key(name)" in _probe_src
      and "replacing {existing!r}" in _probe_src,
      "the Target box is updated when OBJECT names another target, and "
      "the replacement is logged — never swapped silently")
check("self.ed_ra.setText" in _probe_src
      and "replacing {old_ra or '?'}" in _probe_src,
      "the RA/Dec fields are updated too when the headers sit beyond the "
      "disagreement threshold — a stale coordinate is the same trap as a "
      "stale name")
check("agrees with the fields" in _probe_src,
      "coordinates that already agree stay exactly as typed")

print("\n8q11) stale coordinates cannot strand the run on a guess")
# The HAT-P-32 re-run: frames carry OBJECT but no OBJCTRA/OBJCTDEC.  The
# previous target's coordinates sat in the form, silently blocked the
# archive-position branch, went unused in auto mode, and the run fell to
# the brightest-star guess — an edge star the 273 px drift carried off
# the sensor.  Hard abort on a measurable night.
res_src2 = src[src.index("def _resolve_from_name"):]
res_src2 = res_src2[:res_src2.index("def _target_cache")]
check("where the archive puts {planet}" in res_src2
      and "the archive position is used" in res_src2,
      "with no header position, a form coordinate far from where the "
      "archive puts the frames' own OBJECT is the previous target and is "
      "replaced, in RED — it used to silently block the archive branch")
check("agrees with the " in res_src2
      and res_src2.count('self.opts["radec_auto"] = True') >= 3,
      "a form coordinate that AGREES is used, and every auto-to-RA/Dec "
      "upgrade (headers, archive, agreeing form) is marked radec_auto")
run_src2 = src[src.index("def _run("):src.index("def _write_aavso")]
check('self.opts.get("radec_auto")' in run_src2
      and "BRIGHTEST star is used instead" in run_src2,
      "an auto-derived RA/Dec mode falls back to the brightest guess when "
      "the field cannot be plate-solved — only a user-chosen RA/Dec mode "
      "still hard-fails there")
check("the guess moves" in run_src2
      and 'self.opts.get("target_mode") == "brightest"' in run_src2,
      "a brightest-star GUESS that drifts off the sensor guesses again "
      "among the stars that stay on it; a named or placed target remains "
      "a hard stop")
check(run_src2.index("stays_in_frame(tx, ty")
      < run_src2.index("_target_saturation(ref_path"),
      "the drift check runs before the saturation and crowding reports, "
      "so every verdict describes the star actually measured")
_probe2 = src[src.index("def _probe_target"):]
_probe2 = _probe2[:_probe2.index("def _on_pick_folder")]
check("name_switched" in _probe2
      and "cleared the RA/Dec fields" in _probe2,
      "the probe clears stale RA/Dec fields when the target name switches "
      "and the new headers carry no position to replace them with")

print("\n8q12) depth in the convention EXOTIC, HOPS and AIJ quote")
# On EXOTIC's own HAT-P-32 sample set the two tools "disagreed" by
# 30.2 vs 26.1 mmag — pure convention: we quoted the limb-darkened
# CENTRAL depth, they quote (Rp/Rs)^2.  The fit now reports both,
# through the same LD model it fitted with.
_lcd = ns["ld_central_depth"]
_r2d = ns["rprs_from_depth"]
check(abs(_lcd(0.10, 0.0, 0.0, 0.0) / 0.01 - 1.0) < 0.02,
      "with no limb darkening the central depth is exactly (Rp/Rs)^2",
      f"{_lcd(0.10, 0.0, 0.0, 0.0):.5f} vs 0.01000")
_boost = _lcd(0.15) / 0.15 ** 2
check(1.05 < _boost < 1.35,
      "with the default quadratic LD the centre is deeper than (Rp/Rs)^2 "
      "by a plausible solar-type factor", f"boost {_boost:.3f}")
_rt = _r2d(_lcd(0.15))
check(_rt is not None and abs(_rt - 0.15) < 1e-3,
      "depth -> Rp/Rs inverts the forward model (round trip at 0.15)",
      f"{_rt:.5f}" if _rt else "None")
check(_r2d(0.0) is None and _r2d(-0.01) is None and _r2d(None) is None
      and _r2d(1.0) is None,
      "unphysical depths come back as None, not as a made-up radius")
_fitC = ns["fit_transit"](_tF, _magF, bases={"airmass": _XF})
check(_fitC is not None and _fitC.get("rprs") is not None
      and _fitC["depth_rprs2_pct"] < _fitC["depth_pct"],
      "the fit carries Rp/Rs, and (Rp/Rs)^2 is shallower than the "
      "central depth — the LD boost points the right way",
      f"rprs {_fitC['rprs']:.4f}, {_fitC['depth_rprs2_pct']:.2f}% vs "
      f"central {_fitC['depth_pct']:.2f}%")
check(abs(_lcd(_fitC["rprs"], _fitC["impact_b"]) * 100.0
          - _fitC["depth_pct"]) < 0.02,
      "and the two conventions are consistent through the forward model "
      "at the fitted impact parameter")

# The report bug this comparison exposed: the whole measurement block
# (depth, duration, shape, points, RMS) sat INSIDE the
# `if time_system != BJD_TDB` warning branch — every run with CORRECT
# timestamps saved a report without its own depth.
check('\n        A(f"   depth          ' in src,
      "the text report prints the depth at function level, not inside "
      "the wrong-time-system warning branch")
check('"engine": "native" if native is not None else "siril"' in src,
      "the results dict records which engine measured")
check('r.get("engine") == "native"' in src,
      "and the report's Method section describes the engine that "
      "actually ran — it used to claim light_curve unconditionally")
check("#RPRS=" in src and "#DEPTH_RPRS2_PCT=" in src,
      "the AAVSO header carries Rp/Rs and (Rp/Rs)^2 alongside the "
      "central depth")
check("DOCS_URL_EN" in src and "DOCS_URL_DE" in src
      and "Instructions/Svenesis-LightCurve-Instructions" in src
      and src.count("href='{DOCS_URL_EN}'") == 1,
      "the help dialog links the full manuals on GitHub, both languages")
_help = src[src.index("def _show_help"):src.index("def closeEvent")]
check("second, worse photometry engine" not in _help
      and "A trapezoid, not a limb-darkened model" not in _help,
      "the in-app help no longer describes the light_curve era — it "
      "claimed the fit was 'a trapezoid, not a limb-darkened model' and "
      "warned against the very engine that now measures")
check("From the frames" in _help and "(Rp/R★)²" in _help,
      "and it covers the frames-first target mode and both depth "
      "conventions")
check("Why not Siril's own light-curve tool?" in _help,
      "the help answers the most fundamental question head-on, pointing "
      "at the manual's FAQ for the point-by-point comparison")
check("_resource_tracker.ensure_running()" in src
      and src.index("ensure_running()") < src.index("import numpy"),
      "multiprocessing's resource tracker starts at script load, before "
      "sirilpy's shared-memory transport can spawn it mid-run — the lazy "
      "spawn died with PermissionError on macOS and sprayed harmless-but-"
      "alarming tracebacks into Siril's log")

print("\n8r) a skipped airmass basis says WHY, in the log")
# On a real run with borrowed sample data and a wrong site the target sat
# below the horizon for every frame; the basis was rightly dropped, but
# the log showed three fit bases where four were expected — commentless.
# The reason lived only in the Result tab.  Now the log carries it at the
# moment of the decision.
_bases = src[src.index('bases["airmass"] = X'):]
_bases = _bases[:_bases.index("quality = ")]
check("Airmass basis skipped: {airmass_note}" in _bases,
      "the skip is announced in the log, with the reason the series "
      "builder returned")
check('elif self.opts.get("detrend_airmass", True) and airmass_note:'
      in _bases,
      "and only when the user asked for the detrend — an unticked "
      "checkbox is a decision, not a surprise")

print("\n8s) per-point error bars are a plot switch, not a recompute")
# HOPS draws every raw point with its 1-sigma whisker; ours carried the
# same numbers (err_mag in the CSV, weights in the fit) but only drew
# them on the binned overlay.  Now a checkbox toggles them on the raw
# points too — presentation only, so the fit never notices.
_render = src[src.index("def render(self, r: dict"):]
_render = _render[:_render.index("\n    def ")]
check("show_err: bool = False" in _render,
      "render() takes the switch, defaulting to off")
check('r.get("err")' in _render
      and "np.size(err) == jd.size" in _render,
      "and draws only when a per-point error exists for every point — "
      "a mismatched array is silently possible after the finite filter")
check('fmt="none"' in _render and "zorder=1" in _render,
      "whiskers only, drawn UNDER the points, so the curve stays legible")
check("axr.errorbar(x, resid, yerr=err_mmag" in _render,
      "the residual panel carries the SAME whiskers — subtracting the "
      "model shifts a point, never its uncertainty")
check(_render.count("err_mmag = np.asarray(err) * 1000.0") == 1,
      "one error array feeds both panels, so they can never disagree")
check("self.chk_errbars.toggled.connect(self._redraw)" in src,
      "the checkbox redraws immediately, like the binning control")
check("self.chk_errbars.setChecked(False)" in src,
      "and defaults to off — a few hundred whiskers bury the transit")
check("self.chk_errbars.isChecked())" in
      src[src.index("def _redraw"):src.index("def _redraw") + 400],
      "_redraw passes the switch through to render")

print("\n8t) the chart tells the whole story — expected model, outliers, "
      "numbers")
_render2 = src[src.index("def render(self, r: dict"):]
_render2 = _render2[:_render2.index("\n    def save_png")]

# Expected model from the archive ephemeris, honest about time systems.
check('r.get("time_system") == "BJD_TDB"' in _render2,
      "the expected curve is drawn only on BJD_TDB — on JD_UTC the "
      "offset would be the 8-minute time-system error posing as O−C")
check("ld_central_depth(rp_exp" in _render2
      and "math.sqrt(float(depth_pct) / 100.0)" in _render2,
      "the catalogue depth ((Rp/Rs)² convention) is mapped through the "
      "same limb darkening as the fit, not pasted in raw")
check("expected (archive)" in _render2 and "o_minus_c(" in _render2,
      "and the legend quotes the O−C in minutes next to the curve")
check('eph.get("duration_h")' in _render2,
      "the archive duration is used when the archive has one")

# Outlier crosses.
check('"x", color="#dd5555"' in _render2
      and "outlier(s), not fitted" in _render2,
      "spike-rejected points appear as red crosses instead of silently "
      "vanishing")
_worker_clip = src[src.index("keep, n_clipped, clip_note ="):]
_worker_clip = _worker_clip[:2500]
check("clip_jd = jd[~keep]" in _worker_clip,
      "the worker keeps the rejected points for the plot")
check("clip_mag = clip_mag - _zero" in src,
      "and shifts them by the SAME median as the kept points — else "
      "their crosses would float on the old zero point")

# Legend numbers and residual verdict.
check("Rp/R★ {fit['rprs']:.4f}" in _render2,
      "the model legend carries T0 and Rp/R★ with errors — a "
      "screenshot is a complete result")
check("lag-1 autocorr" in _render2
      and "white-noise-like" in _render2,
      "the residual panel reports STD and the lag-1 autocorrelation "
      "with a verdict")
check('r.get("title_bits")' in _render2,
      "and the title carries the provenance line the worker assembled "
      "from the headers")

print("\n8u) the model overlay is paired with the data it is drawn over")
# The first cut drew fit["model_mag"] — baseline + TREND + transit —
# over DETRENDED points: the line wiggled with the seeing, drooped where
# the trend went, and the residual panel subtracted the trend twice.
check('fit["model_mag"][order]' not in _render2
      and 'np.interp(jd, fit["model_t"]' not in _render2,
      "the trend-carrying model array is no longer drawn or subtracted "
      "(the name may survive in a comment explaining why)")
check('fit["baseline"] + fit["depth_mag"]' in _render2
      and "ld_shape(tt_fit" in _render2,
      "the overlay is baseline + transit on a dense grid — smooth, like "
      "the expected curve always was")
check("ld_shape(jd" in _render2,
      "and the residuals subtract the SAME transit-only model — the "
      "trend comes off the data once, never twice")
check('"mild structure"' in _render2 and "abs(r1) < 0.15" in _render2,
      "the autocorrelation verdict has a middle grade — 0.25 announced "
      "as white-noise-like was generous")
check("T0 {t0_pred:.5f}" in _render2
      and "Rp/R★ {rp_exp:.4f}" in _render2,
      "the expected legend quotes predicted T0 and catalogue Rp/R★, as "
      "HOPS does")
check('bits.append(f"{span_h:.1f} h run")' in src,
      "and the title line carries the run duration")
check('"\\ndetrend: " + "+".join(bases_used)' in _render2
      and '"\\ndetrend: none"' in _render2,
      "the model legend names the detrending bases, or says none — a "
      "curve detrended with airmass reads differently from one that "
      "never had the chance")
check('self.opts["site_name"] = str(' in src
      and 'SITENAME' in src[src.index("def _resolve_site"):
                            src.index("def _resolve_site") + 3000],
      "_resolve_site keeps the observatory's SITENAME for the title")
check('if self.opts.get("site_name"):' in src,
      "and the title appends it only when the frames state one — "
      "typed-in coordinates carry no name")

print("\n8v0) TESS candidates resolve through the TOI list")
# The fixture row is the archive's REAL answer for TOI-3540.01 (fetched
# 2026-08-31): depth in ppm, duration in hours, disposition CP.
_TOI_CSV = ("toi,tid,tfopwg_disp,ra,dec,pl_orbper,pl_tranmid,pl_trandurh,"
            "pl_trandep,st_teff,st_logg,st_tmag\n"
            '"3540.01",17865622,"CP",328.9113710,28.1795000,3.1198404,'
            "2459826.7364280,1.7646723,8016.8009531,6011.2000000,,"
            "10.9541000\n")
_toi_calls = []


def _toi_fake(url, timeout=None):
    _toi_calls.append(url)
    return _Resp(_TOI_CSV)


llt = ns["looks_like_toi"]
for raw, want in (("TOI-3540.01", True), ("toi 3540.01", True),
                  ("TOI-3540", True), ("TOI3540.1", True),
                  ("WASP-75 b", False), ("HAT-P-32", False), ("", False)):
    check(llt(raw) is want, f"looks_like_toi({raw!r}) is {want}")

toi_eph, toi_note = ns["toi_lookup"]("TOI-3540.01", opener=_toi_fake)
check(toi_eph is not None and not toi_note,
      "TOI-3540.01 resolves from the toi table", toi_note)
check("toi+where+toi+%3D+3540.01" in _toi_calls[-1].replace("%20", "+")
      or "toi = 3540.01" in __import__("urllib.parse", fromlist=["parse"])
      .unquote_plus(_toi_calls[-1]),
      "the WHERE clause is built from parsed integers, numerically")
check(abs(toi_eph["depth_pct"] - 0.80168) < 0.001,
      f"8016.8 ppm becomes {toi_eph['depth_pct']:.4f} % — the unit the "
      "rest of the script speaks")
check(abs(toi_eph["duration_h"] - 1.76467) < 0.001,
      "the duration stays in hours, which the toi table already uses")
check(toi_eph["disposition"] == "CP"
      and toi_eph["name"] == "TOI-3540.01",
      "disposition and name ride along")

_two = ('toi,tid,tfopwg_disp,ra,dec,pl_orbper,pl_tranmid,pl_trandurh,'
        'pl_trandep,st_teff,st_logg,st_tmag\n'
        '"3540.01",1,"PC",1,1,1,1,1,1,1,1,1\n'
        '"3540.02",1,"PC",1,1,1,1,1,1,1,1,1\n')
e2, n2 = ns["toi_lookup"]("TOI-3540",
                          opener=lambda u, timeout=None: _Resp(_two))
check(e2 is None and "2 candidates" in n2 and "TOI-3540.02" in n2,
      "a bare TOI number with several candidates lists them and asks "
      "which — the multi-planet contract")

_resolver_src = src[src.index("def _lookup(pl, src):"):]
_resolver_src = _resolver_src[:_resolver_src.index("eph, note = _lookup")]
check("looks_like_toi(pl)" in _resolver_src
      and "toi_lookup(pl)" in _resolver_src,
      "the worker falls back to the TOI list only when the planet "
      "lookup misses AND the name is a candidate designation")
check('disp in ("FP", "FA")' in _resolver_src
      and "NOT a planet" in _resolver_src,
      "a false-positive disposition gets a red warning, not a quiet "
      "green ephemeris")
check('hit.get("disposition")' in _resolver_src,
      "and the warning repeats on cache hits — a cached false positive "
      "is still a false positive")

print("\n8w) the expected curve no longer needs a detection")
# On the TOI-3540.01 run the fit claimed nothing and the expected curve
# vanished with it — exactly backwards: on a non-detection the
# prediction is the more valuable half, answering "was a transit even
# due in this window?".
check('fit["detected"] and r.get("time_system")' not in _render2,
      "the curve's gate is the ephemeris and BJD_TDB, not the fit's "
      "verdict")
check("int(round((t_center" in _render2,
      "the epoch comes from the window's centre — a wandering fit "
      "cannot drag the prediction with it")
check('if fit["detected"]:' in _render2 and "O−C {drift:+.1f}" in _render2,
      "the O−C line appears only when there is a fitted T0 to compare")
check("(no transit claimed by the fit)" in _render2,
      "an in-window prediction without a detection states both facts")
check("predicted in this window" in _render2
      and "nearest mid-transit" in _render2
      and "h from this run" in _render2,
      "and a prediction outside the window says so, naming the nearest "
      "mid-transit in hours from the run")

print("\n8v) the measured duration is drawn as a time arrow")
check('arrowstyle="<->"' in _render2
      and "xy=(c - half, y_arrow)" in _render2
      and "xytext=(c + half, y_arrow)" in _render2,
      "a double arrow spans first to last contact of the FITTED transit")
check("transit {hh} h {mm:02d} min" in _render2,
      "labelled with the measured duration in hours and minutes")
check('fit["detected"] and np.isfinite(fit.get("duration_h"' in _render2,
      "drawn only for a claimed detection — the duration of a "
      "non-detection is noise wearing a number")
check("hh, mm = hh + 1, 0" in _render2,
      "and 59.6 minutes rounds to the next hour, not to '1 h 60 min'")

print("\n8x) the chart speaks the planning tool's language — wall "
      "clock, contacts, flip")
# The user plans the night in astro-pm ("start 21:50 … flip 00:55",
# local time); the measurement must let them find those anchors again.

uoh = ns["utc_offset_hours"]
check(uoh("2026-08-31T05:23:11", "2026-08-31T00:23:11") == -5.0,
      "DATE-OBS vs DATE-LOC yields the site's UTC offset (Texas CDT)")
check(uoh("2026-08-31T05:23:11", "2026-08-31T10:53:11") == 5.5,
      "half-hour zones survive the quarter-hour rounding")
check(uoh("2026-08-31T05:23:11", "2026-08-31T00:23:10") == -5.0,
      "one second of write skew between the stamps rounds away")
check(uoh("", "") is None and uoh("garbage", "junk") is None,
      "no DATE-LOC (or unreadable stamps) means None, never a guess")
check(uoh("2026-08-31T20:00:00", "2026-09-01T20:00:00") is None,
      "a 24 h difference is no time zone on Earth — refused")

chh = ns["clock_hhmm"]
check(chh(2451545.0) == "12:00",
      "JD 2451545.0 is J2000 NOON — the +0.5 convention is right")
check(chh(2451545.5) == "00:00", "and the half day later is midnight")
check(chh(2451545.0, -5.0) == "07:00",
      "the UTC offset shifts the reading to local time")
check(chh(2451545.5 - 29.0 / 86400.0) == "00:00",
      "23:59:31 rounds to 00:00, not 24:00 — the modulo after rounding")
check(chh(float("nan")) == "" and chh(None) == "",
      "an unknown time prints as nothing, not as a wrong clock")


class _H:
    def __init__(self, h00, h10):
        self.h00, self.h10 = h00, h10


fbi = ns["flip_boundary_index"]
check(fbi([_H(1, 0), _H(1, 0), _H(-1, 0), _H(-1, 0)]) == 2,
      "the boundary is the FIRST frame on the far side of the flip")
check(fbi([_H(1, 0)] * 5) is None, "no flip, no boundary")
check(fbi([None, _H(0, 0), _H(1, 0), _H(-1, 0)]) == 3,
      "unset registrations are skipped, and the base is the first "
      "READABLE frame")
check(fbi([_H(1, 0), _H(math.cos(math.radians(10)),
                        math.sin(math.radians(10)))]) is None,
      "10° of genuine field rotation is not called a flip")
check(fbi([]) is None and fbi(None) is None,
      "empty input answers None instead of raising")

check('"date_loc"' in src and '"DATE-LOC"' in src,
      "inspect_frame captures N.I.N.A.'s DATE-LOC next to DATE-OBS")
check('"utc_offset_h"' in src and '"flip_jd_utc"' in src,
      "the result dict carries the offset and the flip time to the "
      "chart")
check("flip_boundary_index(homs)" in src,
      "the flip TIME is measured in the same pass that measures the "
      "flip ANGLE")
check('secondary_xaxis("top")' in _render2,
      "a second time axis sits across the top of the chart")
check("- bjd_off" in _render2 and 'r.get("jd_utc")' in _render2,
      "clock labels take the BJD_TDB correction OFF again — a clock "
      "reading in barycentric time would be minutes wrong")
check('else "clock (UTC)"' in _render2 and "local clock (UTC" in _render2,
      "the axis SAYS whether it shows local time or UTC")
check("flip {_clock_at(xf)}" in _render2
      and "FLIP_ROTATION_DEG" in _render2,
      "the flip marker is stamped with its clock time and drawn only "
      "for a real flip")
check('(t0_pred, "mid")' in _render2 and '"start"' in _render2
      and '"end"' in _render2,
      "predicted start/mid/end contacts are labelled like the planner's")
check("xmin <= xc <= xmax" in _render2,
      "contact labels outside the run are dropped, not pinned to the "
      "edge")
check('(r.get(\'time_system\') or \'UTC\').replace' in _render2
      or '(r.get("time_system") or "UTC").replace' in _render2,
      "the bottom axis names the ACTUAL time system of its values")
_seg = _render2[_render2.index("ax.plot(mx, my"):]
_seg = _seg[:_seg.index("axvline")]
check('if fit["detected"]:' in _seg and "axvspan" in _seg,
      "an unclaimed fit gets no mid-transit line or window shading — a "
      "dashed line in this chart must mean exactly one thing")
_help2 = src[src.index("def _show_help"):src.index("def closeEvent")]
check('_tab("Reading the chart"' in _help2,
      "the in-app help grew a chart tab — the features exist where the "
      "user looks for them, not only in the manual")
check("TESS candidates are a different table." in _help2,
      "and the help covers the TOI fallback with its FP warning")
check("no transit claimed by the" in _help2
      and "mid-transit line exists only" in _help2,
      "the help states the three expected-curve cases and the dashed-"
      "line grammar")

print("\n8y) a ranking key never prints as an SNR")
# The Stars tab and the report showed "SNR 2, 1, 1, 1, 1" on a run whose
# log had just said "no SNR from findstar" — the third tuple field was
# -Δmag, the brightness RANKING key, dressed up as a measurement.
c_blind, _rb, _nb = choose(blind, (500, 500), 5, fwhm_px=1.91,
                           min_snr=20.0)
check(len(c_blind) == 5
      and all(not np.isfinite(c[2]) for c in c_blind),
      "with no findstar SNR the chosen tuples carry NaN — the table and "
      "the report both render that as '—', never as a number")
_snr_field = [_Star(500, 500, 300), _Star(900, 100, 250),
              _Star(100, 100, 120), _Star(700, 300, 60)]
c_snr, _rs, _ns2 = choose(_snr_field, (500, 500), 5, fwhm_px=3.0,
                          min_snr=20.0)
check(all(np.isfinite(c[2]) and c[2] >= 20.0 for c in c_snr),
      "with a real SNR it is passed through untouched")
check('"SNR —" if not np.isfinite(snr)' in src,
      "the text report guards the NaN instead of printing 'SNR nan'")
check("survivors.sort(key=lambda r: r[2], reverse=True)" in src,
      "the ranking still happens on the raw score BEFORE the NaN "
      "replacement — order is preserved, only the label is honest")

print()
if fails:
    print(f"{len(fails)} FAILURE(S)")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ALL FLUX HELPER PROBES PASSED")
