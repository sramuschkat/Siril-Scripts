"""Per-filter offset for flats — Svenesis ImageMono Train.

An automatic flat panel sets the exposure PER FILTER to reach the same
level: a narrowband flat runs seconds where a Luminance flat runs a
fraction of one.  The offset those flats are calibrated against has to
match that exposure, so it must be chosen per filter.

Run:  python3 tests/test_imagemono_flat_offset.py
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "Svenesis-ImageMono-Train.py")
src = open(SRC).read()
tree = ast.parse(src)


def _method(cls_name, fn_name):
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == cls_name)
    return ast.get_source_segment(
        src, next(m for m in cls.body
                  if isinstance(m, ast.FunctionDef) and m.name == fn_name))


fails = []


def check(ok, msg, detail=""):
    print(("   ok   " if ok else "   FAIL ") + msg
          + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(msg)


print("1) the offset is picked per filter, not once for the run")
build = _method("StackWorker", "_build_calib_masters")
check("self._flat_offset_for(filt, grp, c)" in build,
      "the flat loop asks per filter")
check("flat_offset = self._masters.get(KIND_DARKFLAT)" not in build,
      "the single run-wide offset is gone")
# The old code gave up entirely when two filters differed in exposure.
# Search the CODE only: the CHANGELOG is a historical record and names
# the removed method when it describes an earlier fix to it.
code = src[src.index("VERSION = "):]
check("_dark_as_darkflat" not in code,
      "the all-flats-share-one-exposure path is gone")

print("\n2) the order of preference is dark-flat, matching dark, bias")
pick = _method("StackWorker", "_flat_offset_for")
i_df = pick.index("KIND_DARKFLAT) or {}).get(filt)")
i_dark = pick.index("for sig, grp in (c.get(KIND_DARK)")
i_bias = pick.index('bias = self._masters.get(KIND_BIAS)')
check(i_df < i_dark < i_bias,
      "dark-flat, then a dark at the flat exposure, then bias")
check("DARKFLAT_EXPOSURE_TOLERANCE" in pick,
      "the dark has to sit within the documented tolerance")
check("self._offset_cache" in pick,
      "two filters sharing an exposure stack it once")

print("\n3) the preview answers the same question before the run")
ns = {"KIND_FLAT": "flat", "KIND_DARKFLAT": "darkflat", "KIND_DARK": "dark",
      "KIND_BIAS": "bias", "DARKFLAT_EXPOSURE_TOLERANCE": 0.20,
      "CALIB_TEMP_TOLERANCE_C": 2.0}
# The offset has to agree with the flats in camera state, not just in
# exposure — the same judge the dark matching uses.
exec("from __future__ import annotations\n" + ast.get_source_segment(
    src, next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "_signature_matches")), ns)
exec("from __future__ import annotations\n"
     + _method("ImageMonoTrainWindow", "_flat_offset_preview"), ns)


class W:
    _flat_offset_preview = ns["_flat_offset_preview"]


def grp(n, exp):
    return {"files": ["f"] * n, "info": {"exp_s": exp}}


w = W()

# The rig this was built for: SHO flats at 3 s, library darks at 3 s.
w._calib = {"flat": {"HA": grp(10, 3.0), "OIII": grp(10, 3.0),
                     "SII": grp(10, 3.0)},
            "darkflat": {},
            "dark": {("s1",): grp(30, 3.0), ("s2",): grp(25, 300.0)},
            "bias": {}}
got = {f: off for f, _n, _e, off in w._flat_offset_preview()}
print(f"   SHO, 3s flats + 3s darks: {got}")
check(all(v == "3s dark" for v in got.values()),
      "every filter finds the 3 s dark, the 300 s one is ignored")

# LRGB through a panel: one exposure per filter, only 3 s darks stored.
w._calib = {"flat": {"L": grp(20, 0.5), "R": grp(20, 1.2),
                     "G": grp(20, 1.2), "B": grp(20, 2.0),
                     "HA": grp(20, 3.0)},
            "darkflat": {}, "dark": {("s1",): grp(30, 3.0)}, "bias": {}}
got = {f: off for f, _n, _e, off in w._flat_offset_preview()}
print(f"   LRGB+HA, only 3s darks:   {got}")
check(got["HA"] == "3s dark",
      "the filter whose flats match keeps its dark")
check(all(got[f] == "synthetic" for f in ("L", "R", "G", "B")),
      "the others are named as unserved instead of silently synthetic "
      "for all five")

# With a bias in the library the unserved ones fall back to it, not below.
w._calib["bias"] = {("b",): grp(50, 0.0)}
got = {f: off for f, _n, _e, off in w._flat_offset_preview()}
print(f"   ...plus a bias:           {got}")
check(got["HA"] == "3s dark" and got["L"] == "bias",
      "an exposure-matched dark still outranks the bias")

# A real dark-flat for a filter wins over everything.
w._calib["darkflat"] = {"L": grp(20, 0.5)}
got = {f: off for f, _n, _e, off in w._flat_offset_preview()}
check(got["L"] == "dark-flat", "a real dark-flat for that filter wins")

print("\n3b) the offset must match the camera state, not just the exposure")
# A panel that sets a different gain per filter is exactly the case:
# 3 s at G0 and 3 s at G125 are the same exposure and different pedestals.
w._calib = {"flat": {"L": {"files": ["f"] * 20,
                           "info": {"exp_s": 3.0, "gain_v": 0,
                                    "binning": 1, "temp_v": -10.0,
                                    "instrument": "Ares-M"}}},
            "darkflat": {},
            "dark": {("g125",): {"files": ["d"] * 30,
                                 "info": {"exp_s": 3.0, "gain_v": 125,
                                          "binning": 1, "temp_v": -10.0,
                                          "instrument": "Ares-M"}}},
            "bias": {}}
got = {f: off for f, _n, _e, off in w._flat_offset_preview()}
print(f"   flats G0, only a G125 dark: {got}")
check(got["L"] == "synthetic",
      "a dark at the right exposure but the wrong gain is refused")

w._calib["dark"][("g0",)] = {"files": ["d"] * 30,
                             "info": {"exp_s": 3.0, "gain_v": 0,
                                      "binning": 1, "temp_v": -10.0,
                                      "instrument": "Ares-M"}}
got = {f: off for f, _n, _e, off in w._flat_offset_preview()}
print(f"   ...and a G0 one added:      {got}")
check(got["L"] == "3s dark", "the matching gain is taken")

w._calib["dark"][("g0",)]["info"]["temp_v"] = 20.0
got = {f: off for f, _n, _e, off in w._flat_offset_preview()}
check(got["L"] == "synthetic", "30 °C too warm is refused as well")

w._calib["dark"][("g0",)]["info"].update(
    {"temp_v": -10.0, "instrument": "ASI533"})
got = {f: off for f, _n, _e, off in w._flat_offset_preview()}
check(got["L"] == "synthetic", "and so is another camera")

runtime = _method("StackWorker", "_offset_fits")
check("_signature_matches(probe, flat_info)" in runtime,
      "the run uses the same judge as the dark matching")
check("exp_s=flat_info.get(\"exp_s\")" in runtime,
      "with the exposure overridden, so it is not weighed twice")

print("\n4) degenerate input does not raise")
for calib in ({}, {"flat": {}}, {"flat": {"HA": grp(0, 0.0)}},
              {"flat": {"HA": grp(5, 0.0)}, "dark": {("s",): grp(5, 3.0)}}):
    w._calib = calib
    try:
        w._flat_offset_preview()
    except Exception as exc:                     # noqa: BLE001
        check(False, f"{calib} raised {type(exc).__name__}: {exc}")
        break
else:
    check(True, "empty, no flats, zero exposure — all answered")

print("\n5) the discovered-filters table shows the flats per filter")
cell = _method("ImageMonoTrainWindow", "_flats_cell")
ns2 = dict(ns)
ns2["_path_date"] = lambda path: path.split("/")[0]
exec("from __future__ import annotations\n"
     + _method("ImageMonoTrainWindow", "_flat_offset_preview"), ns2)
# The cell asks the WORKER which nights qualify, so the preview and the
# run can never drift apart.  Give the namespace the real method.
exec("from __future__ import annotations\n"
     + _method("StackWorker", "_flats_per_night"), ns2)


class _SW:
    _flats_per_night = staticmethod(ns2["_flats_per_night"])


ns2["StackWorker"] = _SW
exec("from __future__ import annotations\n" + cell, ns2)


class T:
    _flat_offset_preview = ns2["_flat_offset_preview"]
    _flats_cell = ns2["_flats_cell"]


def _cb(v):
    class C:
        @staticmethod
        def isChecked():
            return v
    return C


t = T()
t.chk_calibrate, t.chk_flats_by_date = _cb(True), _cb(False)
three_nights = {"files": [f"2026-08-{d}/{i}.fits"
                          for d in (12, 13, 14) for i in range(10)],
                "info": {"exp_s": 3.0}}
t._calib = {"flat": {"HA": three_nights}, "darkflat": {},
            "dark": {("s",): grp(30, 3.0)}, "bias": {}}
t._groups = {"HA": {"dates": ["2026-08-14"]}, "LUM": {"dates": []}}

text, tip = t._flats_cell("HA")
print(f"   pooled:        [{text}]")
check(text == "30 × 3s", "the count and the exposure are shown", text)
check("Offset-corrected with: 3s dark" in tip,
      "and the tooltip names what will offset-correct them")
check("Pooled across nights" in tip,
      "pooling across nights is stated where it is happening")

t.chk_flats_by_date = _cb(True)
text, tip = t._flats_cell("HA")
print(f"   same night:    [{text}]")
check(text == "10 × 3s",
      "the switch changes the number, so the table follows it", text)
check("Pooled across nights" not in tip, "and the pooling note goes away")

print("\n5b) two lit nights with flats each: one master per night")
t._groups = {"HA": {"dates": ["2026-08-12", "2026-08-14"]},
             "LUM": {"dates": []}}
t.chk_flats_by_date = _cb(True)
text, tip = t._flats_cell("HA")
print(f"   per night:     [{text}]")
check(text == "20 × 3s",
      "both lit nights' flats are counted; the unlit 13th is not", text)
check("One master per night" in tip and "2026-08-12 ×10" in tip
      and "2026-08-14 ×10" in tip,
      "and the tooltip breaks the count down per night", tip)
check("Pooled across nights" not in tip, "nothing claims pooling")

# A lit night whose flats are missing must be named, not absorbed.
t._calib["flat"]["HA"] = {
    "files": [f"2026-08-{d}/{i}.fits" for d in (12, 14) for i in range(10)],
    "info": {"exp_s": 3.0}}
t._groups["HA"]["dates"] = ["2026-08-12", "2026-08-13", "2026-08-14"]
_text, tip = t._flats_cell("HA")
check("No flats for 2026-08-13" in tip and "pooled master" in tip,
      "a lit night without flats is named, with what it falls back to", tip)

# One lit night with flats cannot be split, and must not pretend it was.
t._groups["HA"]["dates"] = ["2026-08-12", "2026-08-13"]
t._calib["flat"]["HA"] = {"files": [f"2026-08-12/{i}.fits" for i in range(10)],
                          "info": {"exp_s": 3.0}}
_text, tip = t._flats_cell("HA")
check("One master per night" not in tip and "cannot be kept apart" in tip,
      "one night's flats are pooled, and the tooltip says why", tip)

t._calib["flat"]["HA"] = three_nights
t._groups = {"HA": {"dates": ["2026-08-14"]}, "LUM": {"dates": []}}
t.chk_flats_by_date = _cb(False)
text, tip = t._flats_cell("LUM")
print(f"   no flats:      [{text}]")
check(text == "—" and "No flats found" in tip,
      "a filter without flats says so, with the consequence")

t.chk_calibrate = _cb(False)
text, tip = t._flats_cell("HA")
print(f"   calibration off: [{text}]")
# "none found" and "switched off" must not look identical -- that is the
# ambiguity that made a working discovery look like a broken one.
check(text == "30 × 3s (off)",
      "flats found stay visible when calibration is off", text)
check("switched off" in tip and "will not be used" in tip,
      "and the tooltip says they will not be used, and how to change it")
check(t._flats_cell("LUM")[0] == "—",
      "while a filter with no flats still reads —")

table = _method("ImageMonoTrainWindow", "_refresh_filter_table")
check('setHorizontalHeaderLabels' not in table
      and "self._flats_cell(filt)" in table,
      "the table renderer asks for the cell")
build = _method("ImageMonoTrainWindow", "_build_filters_group")
check('"Filter", "Lights", "Flats", "Integration", "Details"' in build,
      "the column exists in the header")
check("QTableWidget(0, 5)" in build, "and the table has five columns")

print("\n6) the panel says what a filter will get, and warns where nothing "
      "matches")
summary = _method("ImageMonoTrainWindow", "_show_calib_summary")
check("_flat_offset_preview()" in summary, "the label is built from it")
check("synthetic" in summary and "Library" in summary,
      "and an unserved filter is named with what would fix it")

print()
if fails:
    print(f"{len(fails)} FAILURE(S)")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ALL ASSERTIONS PASSED")
