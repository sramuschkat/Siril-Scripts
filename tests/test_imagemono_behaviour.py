"""Behaviour of the run itself — Svenesis ImageMono Train.

Drives the real per-filter pipeline with a stubbed Siril and asserts the
commands it issues, then checks the invariants of the report, the
calibration chain and the colour composition that no static sweep can see.

Run:  python3 tests/test_imagemono_behaviour.py
"""
import ast
import os
import re
import shutil
import sys
import tempfile
import textwrap
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "Svenesis-ImageMono-Train.py")
src = open(SRC).read()
tree = ast.parse(src)
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
           and n.name == "StackWorker")
win_cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == "ImageMonoTrainWindow")

fails = []


def check(ok, msg, detail=""):
    print(("   ok   " if ok else "   FAIL ") + msg
          + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(msg)


def body(name, klass=cls):
    return ast.get_source_segment(
        src, next(m for m in klass.body
                  if isinstance(m, ast.FunctionDef) and m.name == name))


# --------------------------------------------------------------------
# A stubbed Siril, and the real _stack_all_filters running on top of it
# --------------------------------------------------------------------
class CommandError(Exception):
    pass


class DataError(Exception):
    pass


class SirilError(Exception):
    pass


ns = {"os": os, "shutil": shutil, "re": __import__("re"),
      "math": __import__("math"),
      "CommandError": CommandError, "DataError": DataError,
      "SirilError": SirilError,
      "LogColor": types.SimpleNamespace(BLUE=0, GREEN=1, SALMON=2, RED=3),
      "WORK_DIRNAME": "_work", "MASTERS_DIRNAME": "masters",
      "MIN_STACK_FRAMES": 4, "KIND_DARK": "dark", "KIND_FLAT": "flat",
      "KIND_DARKFLAT": "darkflat", "KIND_BIAS": "bias",
      "DARKFLAT_EXPOSURE_TOLERANCE": 0.20,
      "_log_swallowed": lambda exc: None,
      "_is_fits_like": lambda e: True, "_fits_ext": lambda p: ".fit",
      "_safe": lambda t: t.replace(" ", "_"),
      "_DATE_SEGMENT_RE": __import__("re").compile(r"^\d{4}-\d{2}-\d{2}"),
      "_fits_filter": lambda p: "",
      "_rejection_args": lambda n, e: (["rej", "sigma", "3", "3"], "sigma")}
code = "from __future__ import annotations\n" + "\n".join(
    textwrap.dedent(body(n)) for n in
    ("_stack_all_filters", "_calib_split", "_calibrate_in_parts",
     "_master_stem", "_release_work", "_find_fullframe",
     "_drop_generation", "_drop_staged", "_drop_parts"))
for _fn in ("_exp_tag", "_path_date"):
    code += "\n" + textwrap.dedent(
        ast.get_source_segment(src, next(
            n for n in tree.body if isinstance(n, ast.FunctionDef)
            and n.name == _fn)))
exec(code, ns)


class Worker:
    for _n in ("_stack_all_filters", "_calib_split", "_calibrate_in_parts",
               "_master_stem", "_release_work", "_drop_generation",
               "_drop_staged", "_drop_parts"):
        locals()[_n] = ns[_n]

    def __init__(self, tmp, groups, masters, fail_merge=False,
                 flat_nights=None):
        self._out_dir, self._groups, self._masters = tmp, groups, masters
        self._flat_nights = flat_nights or {}
        self._night_notes = {}
        self._opts = {"calibrate": True, "cosmetic": False,
                      "cleanup_work": False, "skip_blank": False,
                      "bg_extract": False, "bg_master": False,
                      "rejmap": False}
        self._ext, self._ftok, self._target = ".fit", {}, "M 16"
        self._calib_notes, self._split_filters = {}, {}
        self._part_cleanup = {}
        self._blank_skipped, self._stacked_counts = 0, {}
        self._qf_decision, self._rej_labels = {}, {}
        self._measured, self._reg_stats = {}, {}
        self._current_n_frames, self._aborted = 0, False
        self.cmds, self.log, self._fail_merge = [], [], fail_merge
        self.progress = types.SimpleNamespace(emit=lambda *a: None)

    def isInterruptionRequested(self):
        return False

    def _unused_by_palette(self, filters):
        return set()

    def _tok(self, f):
        return f

    def _emit(self, m, c=0):
        self.log.append(m)

    def _cmd(self, *a):
        self.cmds.append(" ".join(str(x) for x in a))
        if a[0] == "merge" and self._fail_merge:
            raise CommandError("merge unavailable")

    def _link_frames(self, files, d):
        os.makedirs(d, exist_ok=True)
        for f in files:
            open(os.path.join(d, os.path.basename(f)), "w").close()
        return len(files)

    def _calibrate_args(self, filt, info, warn_mixed=True, night=""):
        args, note = [], []
        if abs(float(info.get("exp_s") or 0) - 300.0) < 0.01:
            args.append("-dark=/lib/master_dark_300s.fit")
            note.append("dark=master_dark_300s.fit")
        flat = ((self._flat_nights.get(filt) or {}).get(night)
                or (self._masters.get("flat") or {}).get(filt))
        if flat:
            args.append(f"-flat={flat}")
            note.append(f"flat={os.path.basename(flat)}")
        if note:
            self._calib_notes[filt] = ", ".join(note)
        return args

    def _register(self, seq, filt):
        return f"r_{seq}"

    def _count_seq_frames(self, d, seq):
        return 0

    def _seq_quality(self, d, seq, filt, expect=0):
        return None

    def _effective_frame_count(self, n):
        return n

    def _quality_filter_args(self, n):
        return []

    def _stack(self, seq, out, n, filt):
        p = os.path.join(self._out_dir, "_work", "sequences", filt, "process")
        os.makedirs(p, exist_ok=True)
        open(os.path.join(p, out + ".fit"), "w").close()

    def _bg_extract_master(self, p):
        pass

    def _collect_rejmaps(self, d, n):
        pass


def group(by_exp, info=None):
    files = [f for v in by_exp.values() for f in v]
    return {"files": files, "by_exp": by_exp, "exps": sorted(by_exp),
            "info": info or {"exp_s": list(by_exp)[0], "gain_v": 100,
                             "temp_v": -10.0},
            "exp_total": sum(e * len(v) for e, v in by_exp.items())}


def run(groups, masters, fail_merge=False, flat_nights=None):
    tmp = tempfile.mkdtemp()
    w = Worker(tmp, groups, masters, fail_merge, flat_nights)
    res, err, _last = w._stack_all_filters()
    return w, res, tmp


print("1) one exposure: the ordinary single pass")
w, res, tmp = run({"HA": group({300.0: [f"a{i}" for i in range(10)]})},
                  {"dark": {("s",): ("/d.fit", {})}})
cmds = "\n".join(w.cmds)
check("link lights -out=../process" in cmds, "one `link lights` sequence")
check("merge" not in cmds, "no merge for a single exposure")
check("calibrate lights -dark=/lib/master_dark_300s.fit" in cmds,
      "one calibrate on the pooled sequence")
name = os.path.basename(res["HA"])
check(name == "M_16_HA_10x300s_G100_-10C_fullframe.fit",
      "the master name carries the recipe", name)
check(not w._split_filters, "not recorded as split")
shutil.rmtree(tmp)

print("\n2) mixed exposures: calibrate in parts, then merge")
w, res, tmp = run({"HA": group({120.0: ["b1", "b2"],
                                300.0: [f"a{i}" for i in range(8)]})},
                  {"dark": {("s",): ("/d.fit", {})}})
cmds = "\n".join(w.cmds)
check("link lights_120s -out=../process" in cmds, "120s staged apart")
check("link lights_300s -out=../process" in cmds, "300s staged apart")
check("calibrate lights_300s -dark=/lib/master_dark_300s.fit" in cmds,
      "the 300s part gets the 300s dark")
check("calibrate lights_120s" not in cmds,
      "the 120s part is NOT given the 300s dark")
check("merge lights_120s pp_lights_300s merged_HA" in cmds,
      "both parts merged into one sequence")
check(w._split_filters == {"HA": "exposures"},
      "recorded as split, and WHY, for the report", str(w._split_filters))
check("300s: dark=" in w._calib_notes.get("HA", ""),
      "the note names the part", w._calib_notes.get("HA", ""))
name = os.path.basename(res["HA"])
check("10subs" in name and "x300s" not in name,
      "mixed exposures give a count, not a false NxT", name)
shutil.rmtree(tmp)

print("\n3) a failed merge falls back and says so")
w, res, tmp = run({"HA": group({120.0: ["b1", "b2"],
                                300.0: [f"a{i}" for i in range(8)]},
                               info={"exp_s": 300.0, "gain_v": 100,
                                     "temp_v": -10.0})},
                  {"dark": {("s",): ("/d.fit", {})}}, fail_merge=True)
cmds = "\n".join(w.cmds)
check("link lights -out=../process" in cmds, "re-staged as one sequence")
check(list(res) == ["HA"], "the filter still produces a master")
check(not w._split_filters, "no split is claimed after the fallback")
check(any("falling back to one pass" in m for m in w.log), "the log says so")
shutil.rmtree(tmp)

print("\n4) no darks: nothing is split even with mixed exposures")
w, res, tmp = run({"HA": group({120.0: ["b1"], 300.0: ["a1", "a2"]})}, {})
check("merge" not in "\n".join(w.cmds) and "lights_120s" not in
      "\n".join(w.cmds), "only the dark depends on exposure")
shutil.rmtree(tmp)


print("\n5) every exposure uncalibrated: no calibration is claimed")


class Worker2(Worker):
    def _calibrate_args(self, filt, info, warn_mixed=True, night=""):
        return []


tmp = tempfile.mkdtemp()
w = Worker2(tmp, {"HA": group({120.0: ["b1", "b2"], 300.0: ["a1", "a2"]})},
            {"dark": {("s",): ("/d.fit", {})}})
w._stack_all_filters()
check("HA" not in w._calib_notes,
      "no note, so the report cannot print a calibration step")
check(not w._split_filters, "and no split claim either")
shutil.rmtree(tmp)

# --------------------------------------------------------------------
# Per-night flats: each night's lights divided by that night's own flat
# --------------------------------------------------------------------
print("\n5b) nights kept apart: one calibrate per night, then merge")


def nightly(nights, exp=300.0):
    """A filter whose frames sit in N.I.N.A.'s per-night folders."""
    files = [f"/data/{n}/HA/{n}_{i}.fit"
             for n, k in nights.items() for i in range(k)]
    return {"HA": group({exp: files})}


FN = {"HA": {"2026-08-12": "/c/HA_2026-08-12_flat.fit",
             "2026-08-14": "/c/HA_2026-08-14_flat.fit"}}
w, res, tmp = run(nightly({"2026-08-12": 10, "2026-08-14": 12}),
                  {"dark": {("s",): ("/d.fit", {})}}, flat_nights=FN)
cmds = "\n".join(w.cmds)
check("link lights_n20260812 -out=../process" in cmds, "the 12th staged apart")
check("link lights_n20260814 -out=../process" in cmds, "the 14th staged apart")
check("-flat=/c/HA_2026-08-12_flat.fit" in cmds
      and "-flat=/c/HA_2026-08-14_flat.fit" in cmds,
      "each night is calibrated with ITS OWN master flat")
check(cmds.count("Running") == 0 and cmds.count("calibrate") == 2,
      "exactly two calibrate calls, one per night",
      str([c for c in w.cmds if c.startswith("calibrate")]))
check("merge pp_lights_n20260812 pp_lights_n20260814 merged_HA" in cmds,
      "both nights merged back into one sequence before registration")
check(w._split_filters == {"HA": "nights"},
      "the report is told the NIGHT is what split", str(w._split_filters))
check(list(res) == ["HA"], "and the filter still yields exactly one master")
name = os.path.basename(res["HA"])
check("22x300s" in name, "over all 22 frames of both nights", name)
shutil.rmtree(tmp)

print("\n5c) a light night without flats falls back, and is not hidden")
w, res, tmp = run(nightly({"2026-08-12": 8, "2026-08-13": 6,
                           "2026-08-14": 8}),
                  {"dark": {("s",): ("/d.fit", {})},
                   "flat": {"HA": "/c/HA_pooled_flat.fit"}}, flat_nights=FN)
cmds = "\n".join(w.cmds)
check("link lights_n20260813 -out=../process" in cmds,
      "the night without its own flats is still staged on its own")
check("calibrate lights_n20260813 -dark=/lib/master_dark_300s.fit "
      "-flat=/c/HA_pooled_flat.fit" in cmds,
      "and takes the pooled master, not another night's")
check("-flat=/c/HA_2026-08-12_flat.fit" in cmds,
      "while the nights that have their own keep them")
shutil.rmtree(tmp)

print("\n5d) exposures AND nights split together, as a cross product")
files_12 = [f"/data/2026-08-12/HA/a{i}.fit" for i in range(6)]
files_14 = [f"/data/2026-08-14/HA/b{i}.fit" for i in range(6)]
w, res, tmp = run(
    {"HA": group({300.0: files_12[:3] + files_14[:3],
                  120.0: files_12[3:] + files_14[3:]})},
    {"dark": {("s",): ("/d.fit", {})}}, flat_nights=FN)
cmds = "\n".join(w.cmds)
for tag in ("300s_n20260812", "300s_n20260814",
            "120s_n20260812", "120s_n20260814"):
    check(f"link lights_{tag} -out=../process" in cmds,
          f"part {tag} staged on its own")
check(w._split_filters == {"HA": "exposures and nights"},
      "both dimensions are named", str(w._split_filters))
check("calibrate lights_300s_n20260812 -dark=/lib/master_dark_300s.fit "
      "-flat=/c/HA_2026-08-12_flat.fit" in cmds,
      "a part gets the dark of ITS exposure and the flat of ITS night")
check("calibrate lights_120s_n20260812 -flat=/c/HA_2026-08-12_flat.fit"
      in cmds,
      "the 120s part keeps its night's flat — the flat does not care "
      "about exposure")
check(not any(c.startswith("calibrate lights_120s") and "-dark=" in c
              for c in w.cmds),
      "but no 120s part is given the 300s dark",
      str([c for c in w.cmds if c.startswith("calibrate lights_120s")]))
shutil.rmtree(tmp)

print("\n5f) the merged parts outlive the merge — `merge` SYMLINKS them")
# Siril's `merge` wrote 30 frames in 4 ms, which no real copy of 30 x
# 36 MB can do: it symlinks its sources.  Freeing the parts right after
# it therefore turned merged_<filt> into dangling links, and EVERY filter
# died with "failed to find or open merged_HA_00001.fit".  Latent since
# the split existed; universal once every run splits by night.
class Worker3(Worker):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.events = []

    def _drop_generation(self, d, seq):
        self.events.append(("drop", seq))

    def _drop_staged(self, d):
        self.events.append(("staged", os.path.basename(d)))

    def _register(self, seq, filt):
        self.events.append(("register", seq))
        return f"r_{seq}"


tmp = tempfile.mkdtemp()
w = Worker3(tmp, nightly({"2026-08-12": 10, "2026-08-14": 12}),
            {"dark": {("s",): ("/d.fit", {})}}, False, FN)
w._opts["cleanup_work"] = True
w._stack_all_filters()
reg = next(i for i, e in enumerate(w.events) if e[0] == "register")
early = [e for e in w.events[:reg]
         if e[0] == "staged" or "lights_n" in str(e[1])]
print(f"   before register: {w.events[:reg]}")
check(not early,
      "nothing the merged sequence points at is freed before registration",
      str(early))
check(("drop", "pp_lights_n20260812") in w.events[reg:]
      and ("staged", "lights_n20260814") in w.events[reg:],
      "and all of it IS freed once registration wrote frames of its own",
      str(w.events[reg:]))
shutil.rmtree(tmp)

parts = body("_calibrate_in_parts")
check("_drop_generation" not in parts and "_drop_staged" not in parts,
      "the merge step frees nothing itself — that was the bug")
check("self._part_cleanup[filt]" in parts,
      "it records what to free instead")
drv = body("_stack_all_filters")
check(drv.index("self._register(seq, filt)") < drv.index("_drop_parts(filt)"),
      "and the driver frees it strictly after registration")

print("\n5e) one night only: nothing is split")
w, res, tmp = run(nightly({"2026-08-12": 10}),
                  {"dark": {("s",): ("/d.fit", {})}},
                  flat_nights={"HA": {"2026-08-12": "/c/f.fit"}})
cmds = "\n".join(w.cmds)
check("merge" not in cmds and "lights_n" not in cmds,
      "a single night needs no parts and no merge")
check(not w._split_filters, "and claims no split")
shutil.rmtree(tmp)

# --------------------------------------------------------------------
# Invariants that live in the source, not in a run
# --------------------------------------------------------------------
print("\n6) the integrated count is measured, never double-filtered")
drv, st = body("_stack_all_filters"), body("_stack")
check("effective = n_reg or self._effective_frame_count(n_linked)" in drv,
      "the estimate is the fallback, not the rule")
check("_effective_frame_count" not in st,
      "_stack does not re-apply the filters' share")
check("self._measured[filt] = bool(n_reg)" in drv,
      "the run records whether it measured at all")
wd = body("_write_docs")
check(wd.index("if self._measured.get(filt):")
      < wd.index("elif k_sigma and self._quality_filter_args(staged)"),
      "a measurement is not presented as an estimate")

print("\n6a) the linear composite stays linear — no SCNR in the pipeline")
# Siril computes SCNR as green = min(green, (red + blue) / 2).  On an
# assignment palette the green channel IS an emission line -- Ha in SHO --
# so that clips measured flux, not a cast.  It is also non-linear, which
# would break the property the very next step promises.
fin = body("_finish_composite")
check('"rmgreen"' not in fin,
      "the finish step does not run rmgreen")
check("still-LINEAR" in fin,
      "and still promises a linear composite — the two must not both hold")
check("scnr.c" in fin,
      "the reason is recorded where the call used to be, with its source")
todo = body("_todo_text")
check(todo.count("rmgreen") >= 2,
      "todo.md hands green removal to the user, in both palette branches",
      str(todo.count("rmgreen")))
check("min(green" in todo or "(red + blue) / 2" in todo,
      "and states what it computes, so the cost is visible before it runs")

print("\n6b) the colour solution's quality survives into the report")
cc = body("_colour_calibrate")
check(cc.index("before = self._log_snapshot()") < cc.index("self._cmd(*cmd)"),
      "the log is snapshotted before the command, not after")
check("self._read_spcc_fit(before, label)" in cc,
      "and read back only once the command succeeded")
rd = body("_read_spcc_fit")
check("_log_delta_or_warn(log_before" in rd
      and "_log_delta_or_warn(log_before" in body("_read_align_pairs"),
      "both readers ask the same helper for their step's own output")
warn = body("_log_delta_or_warn")
check("_log_read_warned" in warn and "self._emit(" in warn,
      "which says so ONCE when it cannot, instead of returning in silence")
check("Nothing about the image changes" in warn,
      "and names the consequence, so the note cannot read as a failure")
check("if not fit:\n            return" in rd,
      "an unparseable log stays silent rather than reporting a guess")
check("SPCC_SIGMA_LIMIT" in rd,
      "a weak solution is named at the time it happens")
check("self._spcc_fit = fit" in rd and "_spcc_fit" in body("_write_docs"),
      "and reaches output.md, where two runs can be compared")
doc = body("_write_docs")
check("insensitive" in doc,
      "the report warns that a small sigma on neighbouring wavelengths "
      "means an insensitive measurement, not a good one")

print("\n7) the disk is freed generation by generation, honestly")
dg = body("_drop_generation")
check("os.lstat(path).st_size" in dg,
      "lstat — getsize would follow a symlink and over-report")
check('self._opts.get("cleanup_work", False)' in dg,
      "gated on the same option as _work/ itself")
check(r"(_\d*)?" in dg,
      "the pattern also catches Siril's own <seq>_.seq")
check(drv.count("self._drop_generation(") >= 3,
      f"{drv.count('self._drop_generation(')} call sites in the chain")

print("\n8) composition: in memory first, rgbcomp as the fallback")
comp, push = body("_compose"), body("_push_composite")
check(comp.index("self._push_composite(") < comp.index("self._rgbcomp("),
      "rgbcomp is the fallback, not the first choice")
check("if not use_lum:" in comp,
      "the -lum= combine is left to Siril entirely")
for need in ("get_image_pixeldata", "set_image_pixeldata",
             'self._cmd("new"', "is_image_loaded", "return None"):
    check(need in push, f"push: {need}")
check("_pm_stage(paths[m_red]" in comp,
      "PixelMath inputs are staged under safe names")

print("\n9) the flats' offset follows the panel, per filter")
build = body("_build_calib_masters")
check("self._flat_offset_for(filt, grp, c)" in build,
      "each filter asks for its own offset")
pick = body("_flat_offset_for")
check(pick.index("KIND_DARKFLAT) or {}).get(filt)")
      < pick.index("for sig, grp in (c.get(KIND_DARK)")
      < pick.index("bias = self._masters.get(KIND_BIAS)"),
      "dark-flat, then a dark at that exposure, then bias")
check("self._offset_cache" in pick,
      "filters sharing an exposure stack it once")

print("\n9b) the flat check compares nights, not single frames")
fc = body("_check_flat_consistency")
# The bug this section exists for: `setdefault(night, path)` kept ONE sub
# per night, so the spread was shot noise -- 1.78% against a 0.30% limit,
# on every dataset.  A whole night has to reach the measurement.
check("setdefault(_path_date(path) or \"?\", []).append(path)" in fc,
      "every frame of a night is collected, not the first one")
shape = src[src.index("def _flat_shape"):src.index("def _flat_normalise")]
check("stack + frame" in shape and "stack / used" in shape,
      "and the night is averaged before anything is measured")
check("_rebin_mean" in src[src.index("def _flat_normalise"):
                           src.index("def _flat_ratio_spread")],
      "then binned down, the way the thresholds' own source tool does")
# The floor, and the branch that uses it, must come BEFORE the thresholds:
# a difference inside the error bar is not a small mismatch, it is none.
check(fc.index("floor = _flat_ratio_spread") < fc.index("<= FLAT_MATCH_GOOD"),
      "the noise floor is measured before any threshold is applied")
check("worst <= floor" in fc, "and a difference under it is reported as none")
check("base[:cut]" in fc and "base[cut:]" in fc,
      "the floor comes from one night split in half — zero shape difference")
# Written as a 4-tuple, read as a 4-tuple.  These sit ~1200 lines apart.
wrote = re.search(r"self\._flat_warn\[filt\] = \(([^)]*)\)", fc).group(1)
read = re.search(r"for filt, \(([^)]*)\) in sorted\(\s*self\._flat_warn",
                 wd).group(1)
check(len(wrote.split(",")) == len(read.split(",")),
      "the warning tuple is written and read with the same arity",
      f"({wrote}) vs ({read})")

oapi_src = src[src.index("OPTIONAL_API = ("):
                src.index("def _missing_capabilities")]

print("\n9c) calibration masters go through the same rejection bands")
scg = body("_stack_calib_group")
# A bare `rej 3 3` is Siril's DEFAULT, winsorized -- the band meant for
# 11-30 frames, and it used to be sent for a 5-frame flat and a 442-frame
# dark alike.
check('"rej", "3", "3"' not in scg, "the fixed winsorized 3/3 is gone")
check("_rejection_args(staged, True)" in scg,
      "the algorithm follows the frame count, as it does for the lights")
check("_rejection_fallback(rej_tokens)" in scg,
      "and an older build that refuses GESDT still gets its retry")
# Always on: the user's rejection switch is about integrating HIS frames.
check("_rejection_args(staged, self._opts" not in scg
      and 'self._opts.get("rejection"' not in scg,
      "rejection is not optional for a master every light is divided by")
check("rej_label" in scg and "Built master" in scg,
      "and the log names the algorithm that ran")

print("\n9d) the synthetic luminance says what it is")
sl = body("_synthetic_luminance")
# It IS an equal-weight average.  A weighted version was tried and taken
# back out: w ~ s/n**2 is not scale-invariant, and every master arriving
# here has been rescaled by -output_norm (and maybe linear_match).  The
# docstring has to carry that reason, or the next reader re-adds the bug.
check("/{len(terms)}" in sl, "the combination is a plain average")
for phrase, why in (
        ("UNWEIGHTED", "the docstring calls the average what it is"),
        ("output_norm", "and names the rescale that breaks a weighting"),
        ("invariant", "and why scale-dependence is the disqualifier"),
        ("bgnoise", "and what a defensible version would need")):
    check(phrase in sl, why)
check("combined signal-to-noise" in sl and "only SNR-optimal" in sl,
      "the old claim is qualified where it is made, not just removed")
# And the user-facing text must not promise optimality either.
wd_lum = wd[wd.index("Synthetic luminance"):][:600]
check("equal-weight" in wd_lum and "pulls the result down" in wd_lum,
      "output.md states the limitation instead of implying optimality")
# The DEFINITIONS must be gone; the CHANGELOG names both helpers on
# purpose, so a bare substring test would fail on its own explanation.
check("def _matched_weights" not in src and "def _master_snr" not in src,
      "no half-reverted weighting helper is left behind")

print("\n9e) an unreadable log is not mistaken for an empty one")
# get_siril_log() returns None WITHOUT raising when Siril declines the
# shared-memory transfer.  An `or ""` there claims a successful read of an
# empty log; _log_delta then fails its anchor search and the run blamed a
# scrolled buffer while the numbers sat two lines up in Siril's console.
check('get_siril_log() or ""' not in src,
      "no snapshot launders a failed read into an empty string")

log_ns = {"LOG_ANCHOR_CHARS": 400, "_log_swallowed": lambda e: None,
          "LogColor": types.SimpleNamespace(SALMON=2)}
exec(ast.get_source_segment(src, next(
    n for n in tree.body if isinstance(n, ast.FunctionDef)
    and n.name == "_log_delta")), log_ns)
exec("from __future__ import annotations\n" + "\n".join(
    textwrap.dedent(body(n)) for n in ("_log_snapshot",
                                       "_log_delta_or_warn")), log_ns)


class _Siril:
    def __init__(self, answers):
        self.answers, self.calls = answers, 0

    def get_siril_log(self):
        v = self.answers[min(self.calls, len(self.answers) - 1)]
        self.calls += 1
        return v


class _LogW:
    _log_snapshot = log_ns["_log_snapshot"]
    _log_delta_or_warn = log_ns["_log_delta_or_warn"]

    def __init__(self, answers):
        self.siril, self.msgs = _Siril(answers), []
        self._log_read_warned = False

    def _emit(self, m, c=0):
        self.msgs.append(m)


_before = "x\n" * 300 + "Setting CWD to '/x/align/process'\n"
_after = _before + "Initial pair matches: 1393\n"


def _drive(answers):
    w = _LogW(answers)
    delta = w._log_delta_or_warn(w._log_snapshot(), "the star-pair counts")
    return delta, " ".join(w.msgs)


d, msg = _drive([_before, _after])
check(d is not None and "1393" in d, "the healthy path still reads the delta")
# The run that prompted this: the SECOND call was declined.  One retry
# recovers it, which is the whole point of retrying.
d, msg = _drive([_before, None, _after])
check(d is not None and "1393" in d,
      "a single refused transfer is retried, not reported as a failure")
d, msg = _drive([_before, None, None])
check(d is None and "transfer was refused" in msg,
      "a persistently refused transfer is named as such")
check("scrolled past" not in msg,
      "and is NOT blamed on the buffer, which was the wrong explanation")
d, msg = _drive([_before, "unrelated tail\n" * 50])
check(d is None and "scrolled past" in msg,
      "a genuinely scrolled buffer still gets the buffer explanation")
check("transfer was refused" not in msg, "and only that one")

print("\n10) the capability report names what is missing")
oapi = src[src.index("OPTIONAL_API = ("):src.index("def _missing_capabilities")]
for call in ("get_seq", "set_image_pixeldata", "get_siril_log"):
    check(f'"{call}"' in oapi, f"{call} is declared optional")
mc = src[src.index("def _missing_capabilities"):src.index("def _median")]
check("hasattr" in mc and "check_module_version" not in mc,
      "probed by capability, not by a version table")
rc = body("report_capabilities", win_cls)
check("if not missing:" in rc, "silent when there is nothing to say")
check('opts.get("missing_api")' in wd,
      "and output.md explains why a number is an estimate")

print()
if fails:
    print(f"{len(fails)} FAILURE(S)")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ALL BEHAVIOUR CHECKS PASSED")
