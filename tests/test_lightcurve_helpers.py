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

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "Svenesis-LightCurve.py")
src = open(SRC).read()
tree = ast.parse(src)

ns = {"np": np, "math": math, "re": re, "datetime": datetime, "os": os,
      "csv": __import__("csv"), "shutil": __import__("shutil")}
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
fit, shape = ns["fit_transit"], ns["trapezoid_shape"]
rng = np.random.default_rng(20260818)
t = np.linspace(0.0, 8.0 / 24.0, 480)
TRUE_T0, TRUE_DUR, TRUE_DEPTH = 4.0 / 24.0, 2.5 / 24.0, 0.015
truth = TRUE_DEPTH * shape(t, TRUE_T0, TRUE_DUR, 0.15)
check(abs(float(np.max(truth)) - TRUE_DEPTH) < 1e-12,
      "the shape reaches exactly 1 at the flat bottom")
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
check(args[3] == "-autoring" and args[4].startswith("-at="),
      "-autoring precedes the positions", str(args[3:5]))

plain = lc("lights", 1, False, (10.4, 20.6), [])
check("-autoring" not in plain and plain[2] == "1",
      "autoring is omitted when off, and the channel is honoured",
      str(plain))
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

print("\n8n) the detection floor is calibrated, not chosen")
# The significance is the best of 121 x 41 x 8 = 39 688 grid nodes and the
# formula does not know it. Measured over 1200 transit-free white-noise
# runs (150 points, 5 h, 4 mmag) through this same search:
#
#     floor   false alarm | 4mmag 5mmag 6mmag 8mmag 12mmag
#       3.0         4.42% |  91%   94%  100%  100%   100%
#       4.0         0.17% |  53%   81%   98%  100%   100%
#       5.0         0.00% |  19%   53%   86%   99%   100%
#
# Running that here would take twenty minutes, so what is pinned is the
# arithmetic that made the old floor wrong and the shape of the fix.
nodes = (ns["FIT_T0_STEPS"] * ns["FIT_DURATION_STEPS"]
         * len(ns["FIT_INGRESS_FRACTIONS"]))
print(f"   grid: {ns['FIT_T0_STEPS']} x {ns['FIT_DURATION_STEPS']} x "
      f"{len(ns['FIT_INGRESS_FRACTIONS'])} = {nodes} nodes")
check(nodes > 10000,
      "the search really is large enough for the look-elsewhere effect to "
      "dominate — that is WHY the floor needs calibrating", str(nodes))
check(abs(ns["MIN_DETECTION_SIGMA"] - 4.0) < 1e-9,
      "the floor is the calibrated 4.0, not the Gaussian-looking 3.0",
      str(ns["MIN_DETECTION_SIGMA"]))
check(ns["MEASURED_FALSE_ALARM"] < 0.002,
      "and the measured rate at that floor is under 0.2%",
      f"{100*ns['MEASURED_FALSE_ALARM']:.2f}%")
# The point of the whole exercise: the floor must be justified by its
# MEASURED rate, so the constant carrying that rate has to exist and be
# reported. A floor without one is a number the reader has to trust.
check(ns["MEASURED_FALSE_ALARM_RUNS"] >= 1000,
      "measured over enough runs to resolve a rate that small",
      str(ns["MEASURED_FALSE_ALARM_RUNS"]))
src_txt = open(SRC).read()
check(src_txt.count("MEASURED_FALSE_ALARM") >= 4,
      "and it reaches the reports, not just the constant block",
      f"{src_txt.count('MEASURED_FALSE_ALARM')} uses")

print("\n8m) the noise model is one model, applied everywhere")
rnb2 = ns["red_noise_beta"]
binner2 = ns["bin_series"]
fitt = ns["fit_transit"]
shape_of = ns["trapezoid_shape"]

# (a) The binned error bar is a SAMPLE standard error. numpy's default
# ddof=0 makes it 29% too small at two points per bin, 11% at five -- and
# a curve with small error bars looks more convincing than it is.
rng = np.random.default_rng(7)
for n, tol in ((2, 0.29), (5, 0.10)):
    got, want = [], []
    for _ in range(4000):
        y = rng.normal(0.0, 1.0, n)
        got.append(np.std(y, ddof=1) / math.sqrt(n))
        want.append(np.std(y) / math.sqrt(n))
    ratio = float(np.mean(want) / np.mean(got))
    tb, mb, eb, nb = binner2(np.arange(n, dtype=float),
                            np.array([0.0, 1.0] + [0.5] * (n - 2)), 1)
    ref = float(np.std(np.array([0.0, 1.0] + [0.5] * (n - 2)), ddof=1)
                / math.sqrt(n))
    check(abs(float(eb[0]) - ref) < 1e-12,
          f"the error bar at {n} points per bin uses ddof=1",
          f"{eb[0]:.6f} vs {ref:.6f}")
print("   (numpy's default ddof=0 is 29% low at n=2, 11% at n=5)")

# (b) sigma1 inside beta must be robust. It was np.std -- the one place in
# this file that was not -- and an inflated sigma1 DIVIDES beta, switching
# the red-noise correction off exactly when the data are bad enough to
# need it.
rng = np.random.default_rng(11)
t_lin = np.linspace(0.0, 0.25, 150)
clean = rng.normal(0.0, 0.004, 150)
dirty = clean.copy()
dirty[rng.choice(150, 3, replace=False)] += 0.05      # three satellite trails
b_clean, _ = rnb2(t_lin, clean, 0.06)
b_dirty, _ = rnb2(t_lin, dirty, 0.06)
print(f"   beta clean {b_clean:.2f}, with three 50 mmag outliers {b_dirty:.2f}")
check(b_dirty >= b_clean * 0.85,
      "three outliers no longer halve beta — with np.std they cut it to "
      "0.47x, which is the correction disabling itself when it is needed",
      f"{b_clean:.2f} -> {b_dirty:.2f}")

# (c) The expected scatter of the SET of bin means is sigma*sqrt(mean(1/k)),
# not sigma/sqrt(mean(k)). Equal bins hide the difference; unequal ones do
# not -- 55% apart on [2,4,8,16,32], 86% on [2,2,2,30].
for counts in ([2, 4, 8, 16, 32], [2, 2, 2, 30]):
    k = np.array(counts, dtype=float)
    old_way = 1.0 / math.sqrt(k.mean())
    new_way = math.sqrt(float(np.mean(1.0 / k)))
    check(new_way > old_way,
          f"unequal bins {counts}: the correct expected scatter is larger, "
          f"so the old form over-stated beta by {100*(new_way/old_way-1):.0f}%")
check(abs(math.sqrt(float(np.mean(1.0 / np.array([10.0]*8))))
          - 1.0/math.sqrt(10.0)) < 1e-12,
      "and on equal bins the two agree exactly, which is why this hid")

# (d) One noise model. The significance is divided by beta; the depth error
# must be multiplied by it, or the same report says "1.6 sigma" and
# "depth/error = 9.5" about one fit.
def _red(n, rho=0.85, s=0.004, gen=None):
    g = gen or np.random.default_rng(3)
    e = g.normal(0.0, s, n)
    out = np.empty(n)
    out[0] = e[0]
    for i in range(1, n):
        out[i] = rho * out[i - 1] + math.sqrt(1 - rho ** 2) * e[i]
    return out

gen = np.random.default_rng(3)
tt = np.linspace(0.0, 5 / 24, 150)
worst = 0.0
seen = 0
for _ in range(10):
    y = 0.012 * shape_of(tt, 0.5 * 5 / 24, 0.3 * 5 / 24, 0.15) + _red(150, gen=gen)
    f = fitt(tt, y)
    if not f or f["red_noise_beta"] <= 1.05:
        continue
    seen += 1
    implied = f["depth_mmag"] / f["depth_sigma_mmag"]
    worst = max(worst, implied / max(f["significance"], 1e-9))
print(f"   {seen} correlated-noise fits; worst depth/error over significance "
      f"= {worst:.1f}x")
check(seen >= 3, "the probe actually produced correlated fits", str(seen))
# They are still not the same number, and should not be: the significance
# uses the MEASURED contrast against the WEAKER of two baselines and counts
# diluted ingress points as "inside", while depth is the FITTED amplitude
# against one baseline. What the fix removed is the part that was pure
# inconsistency -- one number scaled by beta and the other not. The report
# now says which of the two to quote.
check(worst < 4.0,
      "the beta inconsistency is gone; the residual gap is structural, and "
      "was 6.0x when only one of the two carried the red-noise scaling",
      f"{worst:.1f}x")

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

print()
if fails:
    print(f"{len(fails)} FAILURE(S)")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ALL FLUX HELPER PROBES PASSED")
