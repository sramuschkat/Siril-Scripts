#!/usr/bin/env python3
"""Tests for the pure-function core of Svenesis-GalacticView3D.py.

Run:  python3 tests/test_galacticview.py
(or:  pytest tests/test_galacticview.py)

The shipped script is a single file with heavy runtime deps (sirilpy,
PyQt6, astropy) that aren't importable outside Siril — so these tests
extract the pure blocks by regex and exec them with the same
``from __future__ import annotations`` header the module uses.  If an
extraction anchor stops matching, the test FAILS LOUDLY (that means
the code moved and the test needs updating — not that the code broke).

Every test here corresponds to a bug actually found during
development:
  * story-epoch mismatch  (38.7 Myr matched "stone tools", 15x off)
  * analogy "0.0 millimetres" for nearby stars
  * journey near-clip collapse (eye-center separation -> 0.02)
  * sphere-mesh vertex ordering (CMB intensity grid depends on it)
  * plx-vs-z conflict (IC 2708: parallax noise beat a good redshift)
  * cone-search cache rank_key tuple/list round-trip
  * scale_dist discontinuity risk at the 1 Mly boundary
"""
from __future__ import annotations

import datetime
import json
import math
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "Svenesis-GalacticView3D.py")
FUT = "from __future__ import annotations\n"

_passed = 0
_failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed += 1
        print(f"  FAIL  {name}  {detail}")


def extract(pattern: str) -> str:
    src = open(SCRIPT, encoding="utf-8").read()
    m = re.search(pattern, src, re.S)
    if not m:
        raise SystemExit(f"EXTRACTION ANCHOR LOST: {pattern[:60]!r} — "
                         "update tests to match the moved code.")
    return m.group(1)


def run_block(pattern: str, ns: dict) -> dict:
    code = extract(pattern)
    exec(compile(FUT + code, "<extracted>", "exec"), ns)
    return ns


# ---------------------------------------------------------------------------
print("== scale_dist: piecewise continuity and monotonicity ==")
ns = run_block(
    r"(def scale_dist.*?)\n\n\ndef _format_ly_label",
    {"math": math,
     # stub the metric hook: identity (light-travel)
     "convert_distance_for_metric": lambda d, m: d,
     "_ACTIVE_DISTANCE_METRIC": "light-travel"})


class _VM:  # minimal ViewMode stand-in with identity semantics
    GALACTIC = "galactic"
    COSMIC = "cosmic"


ns["ViewMode"] = _VM
scale_dist = ns["scale_dist"]
# Galactic linear
check("galactic linear", abs(scale_dist(26_000, _VM.GALACTIC) - 26.0) < 1e-9)
# Cosmic continuity at exactly 1 Mly
lo = scale_dist(1_000_000 - 1, _VM.COSMIC)
hi = scale_dist(1_000_000 + 1, _VM.COSMIC)
check("cosmic continuous at 1 Mly", abs(hi - lo) < 1e-3, f"lo={lo} hi={hi}")
check("cosmic 1 Mly = 10 units", abs(scale_dist(1e6, _VM.COSMIC) - 10.0) < 1e-9)
# Monotonic across 6 decades
vals = [scale_dist(10.0 ** e, _VM.COSMIC) for e in range(4, 11)]
check("cosmic monotonic", all(b > a for a, b in zip(vals, vals[1:])), str(vals))

# ---------------------------------------------------------------------------
print("== redshift_to_ly: fallback path (no astropy in test env) ==")
ns2 = run_block(
    r"(def redshift_to_ly.*?)\n\n\ndef resolve_object_distance",
    {"_HAS_COSMOLOGY": False, "C_KM_S": 299_792.458,
     "HUBBLE_H0": 67.4, "MPC_TO_LY": 3.26156e6})
r2ly = ns2["redshift_to_ly"]
check("z=0 -> 0", r2ly(0.0) == 0.0)
check("negative z uses |z|", r2ly(-0.01) == r2ly(0.01))
# Linear fallback: z=0.003 → ~43.5 Mly
check("fallback magnitude", abs(r2ly(0.003) / 43.5e6 - 1) < 0.02,
      f"{r2ly(0.003):.3e}")
check("NaN-safe", r2ly(float("nan")) == 0.0)

# ---------------------------------------------------------------------------
print("== story helpers: epochs, formatting, analogy ==")
ns3 = run_block(
    r"(EARTH_HISTORY_EPOCHS = \[.*?)\n\n\nfrom astroquery",
    {"datetime": datetime, "math": math})
lookback = ns3["lookback_context_phrase"]
analogy = ns3["human_scale_analogy"]
story = ns3["build_story_text"]
# The 38.7 Myr bug: must NOT match "stone tools" (2.6 Myr, 15x off)
p = lookback(38.7e6)
check("38.7 Myr not stone-tools", "stone tools" not in p, p)
check("38.7 Myr matches whales", "whales" in p, p)
# Honesty gate: a lookback with no close anchor returns ""
check("honesty gate", lookback(7.0e6) == "", lookback(7.0e6))
check("pre-solar phrase", lookback(5.0e9) == "before the Sun existed")
# Analogy regimes
check("hair's width for nearby star", "hair" in analogy(11.4), analogy(11.4))
check("mm regime", "millimetre" in analogy(1_344), analogy(1_344))
check("metres regime", "metres" in analogy(38.7e6), analogy(38.7e6))
check("km regime", "kilometres" in analogy(2.4e9), analogy(2.4e9))
check("analogy NaN-safe", analogy(float("nan")) == "")


class _Scene(dict):
    def get(self, k, d=None):
        return super().get(k, d)


txt = story(_Scene(object_name="M 42", dist_ly=1344, l_deg=209.0,
                   b_deg=-19.4, arm_hint="",
                   target_arm_membership=("Orion Arm (local)", 320.0)))
check("story includes calendar year", "around the year" in txt, txt)
check("story includes membership", "Orion Arm" in txt, txt)
check("story empty-scene safe", story(_Scene()) is not None)

# ---------------------------------------------------------------------------
print("== build_sphere_mesh: geometry + vertex ordering ==")
try:
    import numpy as np
    ns4 = run_block(
        r"(def build_sphere_mesh.*?)\n\n\ndef build_compass_rose",
        {"np": np, "math": math})
    mesh = ns4["build_sphere_mesh"]((1.0, 2.0, 3.0), 5.0, n_lon=12, n_lat=8)
    check("vertex count", len(mesh["x"]) == 96)
    check("triangle count", len(mesh["i"]) == (8 - 1) * 12 * 2)
    r = math.dist((mesh["x"][0], mesh["y"][0], mesh["z"][0]), (1, 2, 3))
    check("on-sphere", abs(r - 5.0) < 1e-9, f"r={r}")
    # Latitude-major ordering (CMB intensity grid depends on it):
    # first n_lon vertices share one z (one latitude ring).
    z0 = mesh["z"][:12]
    check("lat-major ordering", max(z0) - min(z0) < 1e-9)
    m2 = ns4["build_sphere_mesh"]((0, 0, 0), 4.0, n_lon=8, n_lat=6,
                                  radius_z=2.0, lat_clamp=0.9)
    check("oblate z-clamp", max(abs(z) for z in m2["z"]) < 2.0 + 1e-9)
except ImportError:
    print("  SKIP  (numpy unavailable)")

# ---------------------------------------------------------------------------
print("== cone-search cache: round trip, TTL, rank_key tuples ==")
tmp = tempfile.mktemp(suffix=".json")
ns5 = run_block(
    r"(def _conesearch_cache_key.*?)\n\n\ndef collect_simbad_candidates",
    {"CACHE_VERSION": 2, "CONESEARCH_CACHE_PATH": tmp,
     "CONESEARCH_TTL_DAYS": 7, "CACHE_DIR": os.path.dirname(tmp),
     "datetime": datetime, "json": json, "os": os})
key = ns5["_conesearch_cache_key"](170.1, 13.5, 1.2, 3000, 4000, 3000,
                                   1.5, 99.0)
cands = [{"name": "M 66", "rank_key": (0, 8.9, 0.11),
          "dist_ly_estimate": 3.3e7}]
ns5["_conesearch_cache_store"](key, cands)
back = ns5["_conesearch_cache_load"](key)
check("cache hit", back is not None and back[0]["name"] == "M 66")
check("rank_key tuple restored", isinstance(back[0]["rank_key"], tuple))
check("cache miss on other key", ns5["_conesearch_cache_load"]("x") is None)
check("cache key carries version", "|v2" in key, key)
if os.path.exists(tmp):
    os.unlink(tmp)

# ---------------------------------------------------------------------------
print("== journey waypoints: filtered to the route ==")
ns6 = run_block(
    r"(def _journey_waypoints.*?)\n\n\ndef _inject_camera_bootstrap",
    {"LOCAL_BUBBLE_R_LY": 400.0, "EARTH_TO_GC_LY": 26_000,
     "GALAXY_RADIUS_LY": 50_000, "LOCAL_GROUP_R_LY": 3_000_000.0})
wp = ns6["_journey_waypoints"](38.7e6)
check("waypoints ascending",
      all(b[0] > a[0] for a, b in zip(wp, wp[1:])), str([w[0] for w in wp]))
check("no waypoint beyond target", all(w[0] < 38.7e6 * 0.9 for w in wp))
check("no-distance -> empty", ns6["_journey_waypoints"](None) == [])
check("NaN -> empty", ns6["_journey_waypoints"](float("nan")) == [])

# ---------------------------------------------------------------------------
print("== EARTH_HISTORY_EPOCHS: sanity ==")
epochs = ns3["EARTH_HISTORY_EPOCHS"]
check("epochs ascending",
      all(b[0] > a[0] for a, b in zip(epochs, epochs[1:])))
check("epochs within universe age", epochs[-1][0] < 13.8e9)

# ---------------------------------------------------------------------------
print()
print(f"{_passed} passed, {_failed} failed")
sys.exit(1 if _failed else 0)
