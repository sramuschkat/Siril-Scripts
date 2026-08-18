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
