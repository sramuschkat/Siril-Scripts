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


def _fn_src(name):
    return "from __future__ import annotations\n" + ast.get_source_segment(
        src, next(n for n in tree.body
                  if isinstance(n, ast.FunctionDef) and n.name == name))


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
ns["_sig_sort_key"] = lambda sig: tuple(str(x) for x in sig)
for _m in ("_flat_offset_pick", "_flat_offset_preview"):
    exec("from __future__ import annotations\n"
         + _method("ImageMonoTrainWindow", _m), ns)


class W:
    _flat_offset_pick = ns["_flat_offset_pick"]
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
ns2 = dict(ns)
ns2["_path_date"] = lambda path: path.split("/")[0]
# The night a frame belongs to comes from its own DATE-OBS where discovery
# recorded one, and from the folder otherwise.  These fixtures carry no
# headers, so every lookup falls through to the stubbed `_path_date` --
# which is what the previews did unconditionally before 1.7.15.
ns2["_night_of"] = lambda path, nights=None: (
    (nights or {}).get(path) or ns2["_path_date"](path))
exec("from __future__ import annotations\n"
     + _method("ImageMonoTrainWindow", "_flat_offset_preview"), ns2)
# The cell asks the WORKER which nights qualify, so the preview and the
# run can never drift apart.  Give the namespace the real method.
exec("from __future__ import annotations\n"
     + _method("StackWorker", "_flats_per_night"), ns2)


class _SW:
    _flats_per_night = staticmethod(ns2["_flats_per_night"])


ns2["StackWorker"] = _SW
ns2["DARK_EXPOSURE_TOLERANCE"] = 0.05
ns2["_sig_sort_key"] = lambda sig: tuple(str(x) for x in sig)
for _m in ("_flat_offset_pick", "_flat_files", "_flats_cell", "_flat_rows",
           "_calib_detail",
           "_dark_for_filter", "_dark_preview", "_dark_rows", "_dark_gaps"):
    exec("from __future__ import annotations\n"
         + _method("ImageMonoTrainWindow", _m), ns2)


class T:
    # path -> observing night, as the analysis fills it in.  Empty here:
    # the fixtures below are bare paths, so the folder date answers.
    _nights: dict = {}
    _flat_offset_preview = ns2["_flat_offset_preview"]
    _flat_offset_pick = ns2["_flat_offset_pick"]
    _flat_files = ns2["_flat_files"]
    _flats_cell = ns2["_flats_cell"]
    _flat_rows = ns2["_flat_rows"]
    _calib_detail = staticmethod(ns2["_calib_detail"])
    _dark_for_filter = ns2["_dark_for_filter"]
    _dark_preview = ns2["_dark_preview"]
    _dark_rows = ns2["_dark_rows"]
    _dark_gaps = ns2["_dark_gaps"]


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

print("\n5c) the darks table says what the LIGHTS will be given")
# The old Calibration column counted flats in the folder.  Every filter on
# a rig with an automatic panel read the same "20 x 3s", while the fact
# that mattered -- these 300 s lights get no dark at all -- appeared
# nowhere in the window and only once, mid-run, in the log.  The rule now
# feeds a table of its own, and what it cannot show it says underneath.
t._groups = {"HA": {"dates": ["2026-08-12", "2026-08-13", "2026-08-14"],
                    "info": {"exp_s": 300.0, "gain_v": 125, "binning": 1,
                             "temp_v": -10.0, "instrument": "Ares-M"}}}
t._calib = {"flat": {"HA": three_nights}, "darkflat": {},
            "dark": {("d3",): {"files": ["d"] * 442,
                               "info": {"exp_s": 3.0, "gain_v": 125,
                                        "binning": 1, "temp_v": -10.0,
                                        "instrument": "Ares-M"}}},
            "bias": {}}
t.chk_calibrate, t.chk_cosmetic = _cb(True), _cb(True)
t.chk_flats_by_date = _cb(True)

rows, gaps = t._dark_rows(), t._dark_gaps()
print(f"   442 darks, all 3s vs 300s lights: rows={len(rows)} "
      f"gaps={[f for f, _ in gaps]}")
check(not rows,
      "a library full of darks that fit nothing produces no dark row", rows)
check([f for f, _ in gaps] == ["HA"],
      "and the channel that gets none is named underneath", gaps)
note = gaps[0][1]
check("442 dark(s)" in note and "3s" in note and "300s lights" in note,
      "the note gives the count, the exposures and the mismatch", note)
check("NOT be dark-corrected" in note, "and states the consequence plainly")

# The same library with a matching set: the gap has to disappear.
t._calib["dark"][("d300",)] = {"files": ["d"] * 30,
                               "info": {"exp_s": 300.0, "gain_v": 125,
                                        "binning": 1, "temp_v": -10.0,
                                        "instrument": "Ares-M"}}
rows, gaps = t._dark_rows(), t._dark_gaps()
print(f"   ...plus a 300s set:                {rows}")
check(not gaps, "a matching set closes the gap", gaps)
check(len(rows) == 1 and rows[0][0] == "Dark" and rows[0][1] == "30",
      "and the set that will be opened is the one listed — not all 442", rows)
check(rows[0][2] == "300s" and rows[0][4] == "HA",
      "with the exposure it covers and the filter it covers", rows)
check("gain 125" in rows[0][3] and "-10 °C" in rows[0][3],
      "and the camera state that had to agree", rows[0][3])

# 290s against 300s is inside the 5% band the run itself accepts.
t._calib["dark"][("d300",)]["info"]["exp_s"] = 290.0
check(not t._dark_gaps() and len(t._dark_rows()) == 1,
      "a dark inside the documented exposure band still counts")
t._calib["dark"][("d300",)]["info"]["exp_s"] = 200.0
check([f for f, _ in t._dark_gaps()] == ["HA"] and not t._dark_rows(),
      "one outside it does not")

# Same exposure, wrong gain: refused, exactly as the run refuses it.
t._calib["dark"][("d300",)]["info"].update({"exp_s": 300.0, "gain_v": 0})
check([f for f, _ in t._dark_gaps()] == ["HA"],
      "a dark at the right exposure but the wrong gain is refused")

# Bias is listed whatever the darks do: where a dark covers every filter
# it is still the flats' offset, and that is not nothing.
t._calib["dark"][("d300",)]["info"]["gain_v"] = 125
t._calib["bias"] = {("b",): {"files": ["b"] * 100,
                             "info": {"exp_s": 0.0, "gain_v": 125,
                                      "binning": 1, "temp_v": -10.0,
                                      "instrument": "Ares-M"}}}
rows = t._dark_rows()
kinds = [r[0] for r in rows]
print(f"   with a bias set:                   {kinds}")
check(kinds == ["Dark", "Bias"], "dark first, then bias", kinds)
check(rows[1][4] == "flats' offset only",
      "and where every filter has a dark, the bias says what it is still "
      "for — it must not read as unused", rows[1][4])
del t._calib["dark"][("d300",)]
check(t._dark_rows()[-1][4] == "HA",
      "with no dark for HA the bias is what reaches it, and says so")

print("\n5d) the flats table lists what each filter will be divided by")
t._calib["dark"][("d300",)] = {"files": ["d"] * 30,
                               "info": {"exp_s": 300.0, "gain_v": 125,
                                        "binning": 1, "temp_v": -10.0,
                                        "instrument": "Ares-M"}}
rows = t._flat_rows()
print(f"   3s darks, no DARKFLAT keyword:     {[r[:5] for r in rows]}")
check(len(rows) == 1 and rows[0][0] == "HA", "one row per filter", rows)
check("2026-08-12" in rows[0][4] and "2026-08-14" in rows[0][4],
      "the nights the flats come from are named", rows[0][4])
# The reported case: a session with 160 darks at the flat exposure and no
# frame labelled DARKFLAT.  Reading the keyword left this column empty
# while the Offset column beside it named the very same frames -- the
# column has to show what will be STACKED as the dark-flat, not what
# IMAGETYP happens to call it.
check(rows[0][2] == "442 × 3s",
      "a dark at the flat exposure IS the dark-flat, and is counted as one",
      rows[0][2])
check(rows[0][3] == "3s dark",
      "while Offset still says which KIND of set it is", rows[0][3])
check("whatever IMAGETYP calls it" in rows[0][5],
      "and the tooltip explains why the two columns name one set")

# A real dark-flat set outranks it, exactly as `_flat_offset_for` does.
t._calib["darkflat"] = {"HA": {"files": ["df"] * 20,
                               "info": {"exp_s": 3.0, "gain_v": 125,
                                        "binning": 1, "temp_v": -10.0,
                                        "instrument": "Ares-M"}}}
rows = t._flat_rows()
check(rows[0][2] == "20 × 3s" and rows[0][3] == "dark-flat",
      "a labelled dark-flat set wins over the dark", rows[0][2:4])

# A bias is an offset but NOT a dark-flat: it carries no dark current, so
# counting it in that column would claim a correction that is not there.
t._calib["darkflat"] = {}
saved = t._calib["dark"].pop(("d3",))
t._calib["bias"] = {("b",): {"files": ["b"] * 100,
                             "info": {"exp_s": 0.0, "gain_v": 125,
                                      "binning": 1, "temp_v": -10.0,
                                      "instrument": "Ares-M"}}}
rows = t._flat_rows()
print(f"   only a bias to offset with:        {[r[:5] for r in rows]}")
check(rows[0][2] == "—" and rows[0][3] == "bias",
      "the bias is named as the offset, not counted as a dark-flat",
      rows[0][2:4])
check("No dark-flat and no dark at the flat exposure" in rows[0][5],
      "and the tooltip says so rather than leaving a bare dash")
t._calib["bias"] = {}
check(t._flat_rows()[0][3] == "synthetic",
      "with nothing at all it falls to Siril's synthetic offset")
t._calib["dark"][("d3",)] = saved
# A filter with neither has nothing to show; padding the table with
# dashes would make "no flats for OIII" look like a row that was checked.
t._groups["OIII"] = dict(t._groups["HA"])
check([r[0] for r in t._flat_rows()] == ["HA"],
      "a filter with neither flats nor dark-flats gets no row")
del t._groups["OIII"]

print("\n5e) the two switches reach the run, not just the tables")
build = _method("StackWorker", "_build_calib_masters")
check('use_flats = self._opts.get("use_flats", True)' in build
      and 'use_darks = self._opts.get("use_darks", True)' in build,
      "the run reads both switches")
# Not applying is not enough: a master that will not be used must not be
# STACKED either — that is minutes and hundreds of reads, and it is the
# whole reason for switching it off.
check("if use_flats else {}" in build,
      "no flat master is stacked when flats are off")
check("if use_darks else {}" in build,
      "no dark master is stacked when darks are off")
check("(use_darks or use_flats)" in build,
      "but the bias is still built for the flats' offset — switching the "
      "darks off must not silently downgrade every flat to a synthetic "
      "offset")
args = _method("StackWorker", "_calibrate_args")
i_bias = args.index("self._masters.get(KIND_BIAS)")
check('self._opts.get("use_darks", True)' in args[i_bias:i_bias + 200],
      "and that bias reaches the LIGHTS only while darks are on")
# The dark and flat arguments need no gate of their own: with the masters
# unbuilt there is nothing for them to name.  Assert that, so a later
# change that builds them anyway cannot pass unnoticed.
check(build.index("use_flats = ") < build.index("KIND_BIAS) or {})"),
      "the switches are read before the first master is built")

print("\n5f) the three tables are built the same way")
mk = _method("ImageMonoTrainWindow", "_new_table")
for who in ("_build_filters_group", "_build_calibration_group"):
    body = _method("ImageMonoTrainWindow", who)
    check("self._new_table(" in body, f"{who} uses the shared factory")
check("NoEditTriggers" in mk and "NoSelection" in mk
      and "ResizeMode.Stretch" in mk,
      "which is where read-only, no-selection and the stretch now live")
lights = _method("ImageMonoTrainWindow", "_build_filters_group")
check("QGroupBox(DISCOVERED_TITLE" in lights,
      "the box names what it holds — and its target, in the title")
check('DISCOVERED_TITLE = "Lights, Flats, Dark-Flats for Target: "' in src,
      "spelled out once, so the box and the run cannot disagree about "
      "which target is being stacked")
check("lbl_target" not in src,
      "and the separate Target: line is gone — one place to keep in step")
# The header string, not the word: the comment above it explains why the
# column left, and that explanation is the point of keeping it.
check("_calib_cell" not in lights and '"Calibration"' not in lights,
      "and no longer answers the calibration question too")
check('"Nights"' in lights,
      "the lights table names the observing nights they came from")
check("_build_flats_group" not in src,
      "flats live in that same box now — they come from the same session, "
      "and an empty group of their own was one border too many")
calib = _method("ImageMonoTrainWindow", "_build_calibration_group")
check('QGroupBox("Calibration with Darks and Bias")' in calib,
      "the calibration group is named for what is left in it")
check("chk_use_darks" in calib and "tbl_darks" in calib,
      "and holds the darks switch and its table")
flats = lights
check("chk_use_flats" in flats and "tbl_flats" in flats,
      "with their own switch and table inside it")
# A table nobody redraws is a table that lies after the first click.
for sw, body in (("chk_use_flats", flats), ("chk_flats_by_date", flats),
                 ("chk_use_darks", calib)):
    check(f"self.{sw}.toggled.connect(self._on_calib_kind_toggled)" in body,
          f"{sw} redraws the tables it changes")
# The master switch is gone: every gate it held was about darks, flats or
# bias, so it said what these two say together -- and it could contradict
# them, off with both of these on being a reachable state where the panel
# showed two armed switches and the run calibrated nothing.
check("chk_calibrate" not in src,
      "no third switch is left to disagree with the two")
on = _method("ImageMonoTrainWindow", "_calibration_on")
check("chk_use_flats" in on and "chk_use_darks" in on,
      "the run's calibrate flag is derived from the two boxes")
opts = _method("ImageMonoTrainWindow", "_current_opts")
check('"calibrate": self._calibration_on()' in opts,
      "and that is what reaches the run, so it cannot drift")
tog = _method("ImageMonoTrainWindow", "_on_calib_kind_toggled")
check("self.chk_flats_by_date.setEnabled(flats)" in tog
      and "self.chk_cosmetic" in tog,
      "each dependent control follows its OWN kind — one switch greyed "
      "them all together, so per-night flats went dead over unusable darks")
load = _method("ImageMonoTrainWindow", "_load_settings")
check("legacy_off" in load,
      "a settings file that switched calibration off keeps it off — "
      "honouring only the new keys would turn it back on silently")

print("\n6) the panel says what the LIBRARY holds, and warns about the gap")
summary = _method("ImageMonoTrainWindow", "_show_calib_summary")
check("_dark_preview(filt)" in summary,
      "the no-dark gap is computed for every filter")
# It is SHOWN under the darks table, where the filter that lacks one is
# missing from the rows and an empty table would read as "all fine".
gap = _method("ImageMonoTrainWindow", "_refresh_darks_table")
check("No dark for" in gap and "lbl_dark_gap" in gap,
      "and shown under the table whose silence it explains")
lbl = _method("ImageMonoTrainWindow", "_build_calibration_group")
check("lbl_dark_gap" in lbl and "_tc('warn')" in lbl,
      "in the theme's warning colour rather than buried in the run log")
# Per-filter prose belonged in the table, not in a 9pt paragraph that
# said "→ 3s dark" once per filter and "3 master(s)" once per filter.
for gone in ('bits.append("flat offset: ', 'bits.append("per night: '):
    check(gone not in summary,
          f"per-filter prose is out of the label ({gone.strip()}…)")
check("_flat_offset_preview()" in summary and "synthetic" in summary,
      "the offset detail survives — in the log, where length is free")

print("\n6b) the library's contribution is visible, not inferred")
ns3 = dict(ns, os=os)
exec("from __future__ import annotations\n"
     + _method("ImageMonoTrainWindow", "_count_from"), ns3)


class L:
    _count_from = ns3["_count_from"]


lw = L()
lw._library = "/Work/_CALIB"
here = ["/Work/M16/FLAT/a.fit", "/Work/M16/FLAT/b.fit"]
there = ["/Work/_CALIB/DARK/x.fit"]
check(lw._count_from(here + there, "lib") == 1
      and lw._count_from(here + there, "near") == 2,
      "frames are split by where they physically sit")
check(lw._count_from(["/Work/_CALIBRATION/y.fit"], "lib") == 0,
      "a folder that merely starts with the library's name is not inside it")
lw._library = ""
check(lw._count_from(here + there, "lib") == 0
      and lw._count_from(here + there, "near") == 3,
      "with no library set every frame counts as local")

summary = _method("ImageMonoTrainWindow", "_show_calib_summary")
check("Next to the lights:" in summary and "From the library:" in summary,
      "the label names both origins separately")
check("nothing usable found" in summary,
      "and a library that contributed nothing says so — the case where "
      "picking a folder looked identical to not picking one")

print("\n6c) the table is sized and stretched for the columns it shows")
fit = _method("ImageMonoTrainWindow", "_fit_table_height")
check("sizeHintForRow(" not in fit and "sectionSize(i)" in fit,
      "row heights come from the rows, not from their content hint")
check("frameWidth()" in fit, "and the frame is counted, or the last row "
      "is clipped behind a scroll bar with nothing to scroll")
table = _method("ImageMonoTrainWindow", "_refresh_filter_table")
check("ResizeMode.Stretch" in table,
      "hiding Details moves the stretch, so the table does not end in a "
      "blank panel")

print("\n7) the switches sit above the summary they change")
grp = _method("ImageMonoTrainWindow", "_build_calibration_group")
check(grp.index("self.chk_cosmetic = QCheckBox")
      < grp.index("lbl_calib_found"),
      "chk_cosmetic comes before the label describing its effect")
# "Match flats to the same night" is a FLATS option.  It stayed behind in
# the darks box when the flats moved out, under a blue line that no
# longer described it.
lights = _method("ImageMonoTrainWindow", "_build_filters_group")
check("chk_flats_by_date" in lights and "chk_flats_by_date" not in grp,
      "the per-night flat switch sits with the flats it splits")
# Under the table, not over it: the table is the finding and the
# switches are what you do about it -- and above, they stood between the
# lights table and the flats table they belong to.
check(lights.index("self.tbl_flats = ")
      < lights.index("self.chk_use_flats = QCheckBox")
      < lights.index("self.chk_flats_by_date = QCheckBox"),
      "both flat switches sit under the table they change")
check(lights.index("self.tbl_filters = ") < lights.index("self.tbl_flats = "),
      "with the lights table above and nothing wedged between the two")

print("\n7b) the Nights column leaves room for the one beside it")
ref = _method("ImageMonoTrainWindow", "_refresh_filter_table")
check("_short_nights(" in ref,
      "the shared year is dropped — 380 px of panel does not carry it "
      "four characters per row for nothing")
check("NIGHTS_NAMED = 2" in src,
      "and two dates are named before it gives the count instead: three "
      "ISO dates squeezed Details to a strip too narrow to read")
check('item.setToolTip("\\n".join(nights))' in ref,
      "the full dates stay in the tooltip either way")
ns7 = {}
exec(_fn_src("_short_nights"), ns7)
short = ns7["_short_nights"]
check(short(["2026-09-05", "2026-09-06"]) == ["09-05", "09-06"],
      "one shared year is dropped")
check(short(["2025-12-31", "2026-01-01"]) == ["2025-12-31", "2026-01-01"],
      "two years are not — that is exactly when the year matters")
check(short([]) == [] and short(["odd"]) == ["odd"],
      "and anything that is not an ISO date is left alone")
# The blue line keeps only what no table can answer.  Stating the missing
# dark here as well put one sentence twice on a single screen.
summary = _method("ImageMonoTrainWindow", "_show_calib_summary")
check("Next to the lights:" in summary and "From the library:" in summary,
      "the line that is left answers WHERE the frames came from")
check("no dark for" not in summary,
      "and no longer repeats the warning the darks table carries")
check("switched off — found, not applied" not in summary,
      "nor the switched-off note the tables already grey and annotate")
# A switch changes the LABEL, not the record: the summary was re-logged on
# every click, and eleven repetitions of "Flat offset — …" in seventeen
# seconds of ticking boxes buried the run it was meant to document.
check("quiet: bool = False" in summary and "if quiet else self._log" in summary,
      "the summary can update the label without writing to the log")
check("self._log(" not in summary,
      "and every line in it goes through that switch")
tog2 = _method("ImageMonoTrainWindow", "_on_calib_kind_toggled")
check("_show_calib_summary(quiet=True)" in tog2,
      "a toggle updates the label quietly")
done = _method("ImageMonoTrainWindow", "_on_analyze_done")
check("_show_calib_summary(payload" in done and "quiet" not in done.split(
      "_show_calib_summary(payload")[1][:40],
      "while a fresh analysis still writes the record once")
# A real run reported "100 biass": the count line built every plural by
# appending "s" to the label, and bias is its own plural.
check('(KIND_BIAS, "bias", "bias")' in summary,
      "bias carries its own plural instead of growing an s")
check("else 's'" not in summary,
      "and no label gets one appended blindly")

print("\n8) a dark used as a dark-flat is not reported as \'not stacked\'")
# The NGC 6946 shape: darks at 3s (next to the lights) plus 60s, 180s and
# 600s from the library, against 60s and 180s lights.  Flats run BEFORE
# darks, so the 3s set has already been stacked as the dark-flat by the
# time this counts -- 160 frames the log shows being built and used.
ns8 = dict(ns)
ns8["DARK_EXPOSURE_TOLERANCE"] = 0.05
ns8["LogColor"] = __import__("types").SimpleNamespace(
    BLUE=0, GREEN=1, SALMON=2, RED=3)
exec("from __future__ import annotations\n"
     + _method("StackWorker", "_darks_in_demand"), ns8)


def _g(exp):
    return {"files": ["x"], "info": {"exp_s": exp, "gain_v": 125,
                                     "temp_v": -10.0}}


class D:
    _darks_in_demand = ns8["_darks_in_demand"]

    def __init__(self, offset_cache):
        self._groups = {"LUMINOS": _g(60.0), "RED": _g(180.0)}
        self._offset_cache = offset_cache
        self.log = []

    def _emit(self, msg, colour=None):
        self.log.append(msg)


darks = {"s3": _g(3.0), "s60": _g(60.0), "s180": _g(180.0),
         "s600": _g(600.0)}

w = D({("dark", "s3"): "NGC_6946_-10C_3s_G125_darkflat.fit"})
wanted = w._darks_in_demand(darks)
text = " ".join(w.log)
print(f"   3s used as dark-flat: [{text.strip()}]")
check(wanted == {"s60", "s180"},
      "only the exposures the lights can use are stacked as darks")
check("s3" not in wanted,
      "the dark-flat set is NOT stacked a second time as a dark master")
check("1 dark set(s)" in text,
      "only the genuinely unused 600s set is counted", text)
check("2 dark set(s)" not in text,
      "the 3s set is no longer reported as not stacked", text)

w = D({})
w._darks_in_demand(darks)
text = " ".join(w.log)
print(f"   3s never used:        [{text.strip()}]")
check("2 dark set(s)" in text,
      "without that use it really is two unused sets, and still says so",
      text)

w = D({("dark", "s3"): "df.fit", ("dark", "s600"): "df600.fit"})
w._darks_in_demand(darks)
check(not w.log,
      "when every skipped set went into a dark-flat there is nothing to "
      "report — silence, not a count of zero")

w = D({("dark", "s3"): ""})
w._darks_in_demand(darks)
check("2 dark set(s)" in " ".join(w.log),
      "a dark-flat stack that FAILED leaves an empty cache entry, and "
      "that set is unused after all")

print("\n9) reusable masters are only looked for when reuse is on")
run = _method("StackWorker", "run")
i_want = run.index("want_reuse = self._opts.get")
i_full = run.index("full_paths = (")
check(i_want < i_full, "the switch is read before the scan is decided")
check("if want_reuse else {}" in run[i_full:i_full + 400],
      "and a run with reuse off does not stat a masters/ directory that "
      "need not exist — four swallowed FileNotFoundError lines opened "
      "every fresh run")

print()
if fails:
    print(f"{len(fails)} FAILURE(S)")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ALL ASSERTIONS PASSED")
