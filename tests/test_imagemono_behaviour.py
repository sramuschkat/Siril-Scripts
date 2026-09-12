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


def _cls_method(cls_name, fn_name):
    """One method's source, addressed by class name rather than by `cls`."""
    k = next(n for n in tree.body
             if isinstance(n, ast.ClassDef) and n.name == cls_name)
    return body(fn_name, k)


def _fn_src(fn_name):
    """One module-level function's source."""
    return ast.get_source_segment(
        src, next(n for n in tree.body
                  if isinstance(n, ast.FunctionDef) and n.name == fn_name))


ns_presets: dict = {}
exec(src[src.index("PRESETS = {"):src.index("def _log_swallowed")],
     ns_presets)


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
      "_rejection_args": lambda n, e: (["rej", "sigma", "3", "3"], "sigma"),
      # The recorder is run for real, so the stub writes a genuine
      # commands.ssf into its temp folder and section 46 reads it back.
      "COMMANDS_FILENAME": "commands.ssf", "VERSION": "test",
      "SIRIL_MIN_VERSION": "1.4.0",
      "_SCRIPT_FORBIDDEN_COMMANDS": frozenset({"load_seq"}),
      "datetime": __import__("datetime"),
      "_atomic_write_text": lambda path, text: open(
          path, "w", encoding="utf-8").write(text)}
ns.update({"FILTER_MIN_FRAMES": 20, "MIN_STACK_FRAMES": 4,
           "FILTER_MAX_KSIGMA": 2, "PERCENTILE_MAX_FRAMES": 4})
code = "from __future__ import annotations\n" + "\n".join(
    textwrap.dedent(body(n)) for n in
    ("_stack_all_filters", "_calib_split", "_calibrate_in_parts",
     "_master_stem", "_release_work", "_find_fullframe",
     "_drop_generation", "_drop_staged", "_drop_parts",
     "_check_framing", "_reg_frame_sizes",
     "_clear_stale_dir", "_discard_dir", "_verify_outputs",
     "_quality_filter_plan", "_projected_frame_count",
     "_effective_frame_count", "_quality_filter_args",
     "_record_command", "_note_command", "_here", "_write_commands",
     "_part_tag", "_part_label"))
for _fn in ("_exp_tag", "_path_date", "_night_of", "_read_header"):
    code += "\n" + textwrap.dedent(
        ast.get_source_segment(src, next(
            n for n in tree.body if isinstance(n, ast.FunctionDef)
            and n.name == _fn)))
exec(code, ns)


class Worker:
    for _n in ("_stack_all_filters", "_calib_split", "_calibrate_in_parts",
               "_check_framing", "_reg_frame_sizes",
               "_master_stem", "_release_work", "_drop_generation",
               "_drop_staged", "_drop_parts",
               "_clear_stale_dir", "_discard_dir", "_verify_outputs",
               "_quality_filter_plan", "_projected_frame_count",
               "_effective_frame_count", "_quality_filter_args",
               "_record_command", "_note_command", "_here",
               "_write_commands"):
        locals()[_n] = ns[_n]
    # Both are @staticmethod in the real class; binding them as plain
    # functions would hand them `self` as the first argument.
    for _n in ("_part_tag", "_part_label"):
        locals()[_n] = staticmethod(ns[_n])

    def __init__(self, tmp, groups, masters, fail_merge=False,
                 flat_nights=None):
        self._out_dir, self._groups, self._masters = tmp, groups, masters
        # path -> observing night, as discovery fills it in.  Empty in these
        # fixtures, so `_night_of` falls through to the folder date -- the
        # rule the run used unconditionally before 1.7.15.
        self._nights: dict = {}
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
        # The stub's "frames" are not real FITS, so `_check_framing` reads
        # nothing and stays silent -- which is itself the contract: an
        # unreadable sequence is "cannot tell", never a warning.
        self._reg_degraded, self._reg_degraded_why = {}, {}
        self._current_n_frames, self._aborted = 0, False
        self.cmds, self.log, self._fail_merge = [], [], fail_merge
        self.cc_seen: dict = {}
        self._split_refused: dict = {}
        self._cc_said: dict = {}
        self._no_flat_said: set = set()
        self._commands: list = []
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
        # The real `_cmd` records before it calls Siril, and section 46
        # reads that file back — so the stub has to record too, or the
        # notes would sit in a record with no commands around them.
        self._record_command(*a)
        if a[0] == "merge" and self._fail_merge:
            raise CommandError("merge unavailable")

    def _link_frames(self, files, d):
        os.makedirs(d, exist_ok=True)
        for f in files:
            open(os.path.join(d, os.path.basename(f)), "w").close()
        return len(files)

    def _calibrate_args(self, filt, info, n_frames=0, warn_mixed=True,
                        night=""):
        args, note = [], []
        # Mirrors the real signature so the drivers' keyword call is
        # exercised, and records the count each path handed down.
        self.cc_seen[filt] = n_frames
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
        # Non-empty on purpose: `_verify_outputs` treats a zero-byte master
        # as a failure, because a `save` that creates the file and never
        # fills it is exactly the silent case it exists to catch.
        with open(os.path.join(p, out + ".fit"), "w") as fh:
            fh.write("stub")

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
    def _calibrate_args(self, filt, info, n_frames=0, warn_mixed=True,
                        night=""):
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
check("self._read_spcc_fit(before, label, cmd[0])" in cc
      and cc.index("self._cmd(*cmd)") < cc.index("self._read_spcc_fit("),
      "and read back only once the command succeeded, with that command")
rd = body("_read_spcc_fit")
asks = re.compile(r"_log_delta_or_warn\(\s*log_before")
check(asks.search(rd) and asks.search(body("_read_align_pairs")),
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
check("_night_of(path, self._nights) or \"?\", []).append(path)" in fc,
      "every frame of a night is collected, not the first one")
# 1.7.15: and the night is the frame's OWN (noon-to-noon from DATE-OBS),
# not its date folder -- the key that was computed and never read.
check("_path_date(path)" not in fc,
      "and the night comes from the header, not the folder")
shape = src[src.index("def _flat_shape"):src.index("def _flat_normalise")]
check("have[0] + frame" in shape and "stack / used" in shape,
      "and the night is averaged before anything is measured")
# 1.7.15: the reference size is the one MOST of the night agrees on.
# Taking it from the first frame read let a single mixed-binning frame at
# the head of the list skip every ordinary frame behind it.
check("sums[sh][1]" in shape,
      "on the size the majority of the night agrees on")
check("_rebin_mean" in src[src.index("def _flat_normalise"):
                           src.index("def _flat_ratio_spread")],
      "then binned down, the way the thresholds' own source tool does")
# The floor, and the branch that uses it, must come BEFORE the thresholds:
# a difference inside the error bar is not a small mismatch, it is none.
check(fc.index("floor = _flat_ratio_spread") < fc.index("<= FLAT_MATCH_GOOD"),
      "the noise floor is measured before any threshold is applied")
check("worst <= floor" in fc, "and a difference under it is reported as none")
check("base[0::2]" in fc and "base[1::2]" in fc,
      "the floor comes from one night split in half — zero shape difference")
# 1.7.17: and the halves INTERLEAVE.  The file list is sorted by path and
# a flat run is named by timestamp, so contiguous halves straddle time:
# drift in the flats' SHAPE (dew, a twilight gradient) landed in the
# "noise floor" as if it were noise, inflating the error bar that is
# supposed to reveal a real night-to-night difference.
check("base[:cut]" not in fc and "cut = len(base)" not in fc,
      "not the first half against the second, which straddles any drift")
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
scg = body("_build_calib_master")
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
        self._log_read_warned = set()

    def _emit(self, m, c=0):
        self.msgs.append(m)


PROC = "/tmp/out/_work/align/process"
SCOPE = "Checking sequences in the directory: " + PROC
# Verbatim shape of the step, tracebacks included: stderr from OTHER
# processes lands in Siril's log too, which is why neither snapshot-based
# path can be relied on alone.
STEP = (f"Running command: register\nChecking sequences in the directory: "
        f"{PROC}.\nTraceback (most recent call last):\n"
        "PermissionError: [Errno 1] Operation not permitted\n"
        "Trial #1: After sequence analysis, we are choosing image 2 as new "
        "reference for registration\n"
        "Matching stars in image 1: done\nInitial pair matches: 1376\n"
        "Matching stars in image 3: done\nInitial pair matches: 1392\n")
_before = "x\n" * 300 + f"Setting CWD to '{PROC}'\n"
_after = _before + STEP


def _drive(answers, scope=""):
    w = _LogW(answers)
    delta = w._log_delta_or_warn(w._log_snapshot(), "the star-pair counts",
                                 scope=scope)
    return delta, " ".join(w.msgs)


d, msg = _drive([_before, _after])
check(d is not None and "1376" in d, "the healthy path still reads the delta")
# The run that prompted the retry: the SECOND call was declined.
d, msg = _drive([_before, None, _after])
check(d is not None and "1376" in d,
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

print("\n9f) the readers anchor on a marker the step itself writes")
# Two consecutive runs of the same data failed the snapshot paths for two
# DIFFERENT reasons.  The scope marker does not depend on either snapshot.
pairs_of = {1: "HA", 2: "OIII", 3: "SII"}
parse = {}
exec(ast.get_source_segment(src, next(
    n for n in tree.body if isinstance(n, ast.FunctionDef)
    and n.name == "_parse_align_pairs")), {"re": re}, parse)
for label, answers in (("anchor lost mid-step", [_before, "junk\n" * 200 + STEP]),
                       ("first snapshot refused", [None, None, _after])):
    d, _msg = _drive(answers, scope=SCOPE)
    got, ref = parse["_parse_align_pairs"](d, pairs_of) if d else ({}, None)
    check(got == {"HA": 1376, "SII": 1392} and ref == "OIII",
          f"{label}: the counts are recovered anyway", str(got))
d, msg = _drive([_before, None, None], scope=SCOPE)
check(d is None, "but an unreadable log is still unreadable — no invention")

am = body("_read_align_pairs")
check("scope=scope" in am, "the alignment reader passes its marker through")
# The few-stars remedy used to be a fixed sentence naming "Stack only the
# filters this palette uses".  Under HaRGB that palette reads L, R, G, B
# and Ha, so the switch drops nothing: the advice pointed at a control
# that could not change the outcome.  It is now worked out per run.
check("palette uses" not in am and "_align_ref_advice(self._opts" in am,
      "the remedy is derived from the run's own palette, not hard-coded",
      am[am.find("if weak"):][:400])
sf = body("_read_spcc_fit")
check("Running command: {command}" in sf,
      "and the colour reader anchors on the COMMAND it issued")
check("cmd[0]" in body("_colour_calibrate"),
      "taken from the command list, not split out of a display label")
# One shared flag meant the first failing reader silenced the second's
# message -- on one run that swallowed an SPCC sigma of 5.5 against a
# limit of 1.0.
warn = body("_log_delta_or_warn")
check("what not in self._log_read_warned" in warn
      and "self._log_read_warned.add(what)" in warn,
      "the warn-once flag is per diagnostic, not per run")

print("\n9g) the quality-filter floor holds for the COMBINATION")
qf_ns = {"FILTER_MIN_FRAMES": 20, "MIN_STACK_FRAMES": 4,
         "FILTER_MAX_KSIGMA": 2}
for _m in ("_quality_filter_args", "_quality_filter_plan",
           "_projected_frame_count", "_effective_frame_count"):
    exec("from __future__ import annotations\n"
         + textwrap.dedent(body(_m)), qf_ns)


class _QF:
    _quality_filter_args = qf_ns["_quality_filter_args"]
    _quality_filter_plan = qf_ns["_quality_filter_plan"]
    _projected_frame_count = qf_ns["_projected_frame_count"]
    _effective_frame_count = qf_ns["_effective_frame_count"]

    def __init__(self, o):
        self._opts = o


def _opts(mode, **vals):
    o = {"filter_mode": mode}
    for k, v in vals.items():
        o[k + "_on"], o[k + "_val"] = True, v
    return o


def _survivors(n, args):
    share = 1.0
    for a in args:
        if a.endswith("%"):
            share *= int(a.split("=")[1][:-1]) / 100
    return int(n * share)


# Siril keeps the frames passing EVERY filter, so the survivors are an
# intersection.  Guarding each filter on its own let four 60% cuts on 20
# frames through, projecting to 2 against a floor of 4.
got = _QF(_opts("percent", f_wfwhm=60, f_round=60,
                f_stars=60, f_bkg=60))._quality_filter_args(20)
check(len(got) == 3 and _survivors(20, got) >= 4,
      "four 60% cuts on 20 frames stop at three, projecting 4 not 2",
      f"{got} -> {_survivors(20, got)}")
got = _QF(_opts("percent", f_wfwhm=50, f_round=50,
                f_stars=50))._quality_filter_args(20)
check(len(got) == 2 and _survivors(20, got) >= 4,
      "and three 50% cuts stop at two")
# The ordinary setting must be untouched: a floor that fires on sane input
# is a regression, not a fix.
got = _QF(_opts("percent", f_wfwhm=90, f_round=90,
                f_stars=90))._quality_filter_args(30)
check(len(got) == 3 and _survivors(30, got) == 21,
      "three 90% cuts on 30 frames still all apply")
check(_QF(_opts("percent", f_wfwhm=90))._quality_filter_args(19) == [],
      "and nothing at all below FILTER_MIN_FRAMES")
# k-sigma cannot be projected, so the brake is on how many cuts combine.
got = _QF(_opts("k-sigma", f_wfwhm=3, f_round=3,
                f_stars=3, f_bkg=3))._quality_filter_args(30)
check(len(got) == qf_ns["FILTER_MAX_KSIGMA"] and all(a.endswith("k")
                                                     for a in got),
      "k-sigma stacks at most FILTER_MAX_KSIGMA cuts", str(got))

print("\n9h) HaRGB blends linearly, and the docs agree")
cp = body("_compose")
check("1-(1-$" not in cp and "1-(1-${" not in cp,
      "the non-linear screen blend is gone")
check("+{k:g}*$" in cp and "/{1.0 + k:g}" in cp,
      "Red is a weighted sum (R + k*Ha)/(1+k)")
# Bounded without a rescale, and R is never discarded.
for k in (0.0, 0.5, 1.0):
    for r, ha in ((0.0, 0.0), (1.0, 1.0), (0.8, 0.8), (0.002, 0.003)):
        v = (r + k * ha) / (1.0 + k)
        check(0.0 <= v <= 1.0, f"bounded at k={k}, R={r}, Ha={ha}", f"{v}")
check(abs((0.8 + 1.0 * 0.0) / 2.0 - 0.4) < 1e-12,
      "at 100% the mix is even, never pure Ha")
# The output tab claimed every composite was "calibrated and linear" while
# the pipeline tab correctly said HaRGB is excluded from calibration.
help_src = src[src.index("def _show_help_dialog"):]
check("— calibrated and linear" not in help_src,
      "the blanket 'calibrated and linear' claim is gone")
check("except <tt>_HaRGB</tt>" in help_src,
      "and the one exception is named where the files are listed")

print("\n9i) a mixed-exposure integration time is marked, not asserted")
wd_exp = wd[wd.index("exp_used = exp * effective"):][:900]
check("mixed_exp = len(g.get(\"by_exp\") or {}) > 1" in wd_exp,
      "the mixed-exposure case is detected")
check('("~" if mixed_exp else "")' in wd,
      "and its integration time carries a tilde")
check("their average length stands in" in wd,
      "with the footnote saying why it is only an estimate")

print("\n9j) zeros in the quality median are dropped ON PURPOSE")
# Not a defect, though it looks like one: sirilpy documents roundness as
# "0 when uninit, ]0, 1] when set", an FWHM of 0 is impossible, and a
# frame with no stars cannot be registered so it never reaches `included`.
sq = body("_seq_quality")
check("getattr(layer[i], attr, None)]" in sq,
      "the truthiness test is still there")
check("0 when uninit" in sq or "uninit" in sq,
      "and the reason is written down where the next reader will look")

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

print("\n17) the 1.7.11 audit fixes hold their shape")
# The floor is SCALED onto the real comparison's frame counts — raw, the
# half-vs-half spread overstates the true noise by sqrt(2) at equal
# counts, and "no shape difference detectable" then covered real
# differences as large as the noise itself.
check("floor *= _floor_rescale(" in fc,
      "the flat-check floor is rescaled before any verdict uses it")
check(fc.index("floor *= _floor_rescale(") < fc.index("worst <= floor"),
      "and the rescale happens before the floor judges anything")
check("left out of the night comparison" in fc,
      "flats of a different image size are named, not silently dropped")
shape2 = src[src.index("def _flat_shape"):src.index("def _flat_normalise")]
check("stats[\"used\"], stats[\"skipped\"] = used, skipped" in shape2,
      "_flat_shape reports how many frames it actually averaged")
mode = body("_on_filter_mode_changed", win_cls)
check("_restoring_settings" in mode and "_applying_preset" in mode,
      "the 'values were reset' line is silenced while stored settings or "
      "a preset are applied — it used to fire on every k-sigma startup, "
      "about constructor defaults, one moment before the real values "
      "were restored")
loads = body("_load_settings", win_cls)
check("self._restoring_settings = True" in loads
      and "self._restoring_settings = False" in loads,
      "and _load_settings sets and clears that flag around the restore")
warn_src = src[src.index("def _align_pairs_warn"):]
warn_src = warn_src[:warn_src.index("\ndef ")]
check("_median(" in warn_src and "ordered" not in warn_src,
      "_align_pairs_warn uses the module's _median instead of a second "
      "hand-rolled copy")

print("\n18) FITS reads survive astropy's memmap refusal")
# astropy refuses to memory-map BZERO/BSCALE/BLANK frames — every
# N.I.N.A. integer sub — and raises at `.data` access time.  One run
# swallowed that ~130 times while the flat consistency check silently
# skipped and the blank-frame check silently kept everything.  Every
# reader now goes through _with_fits, which reopens unmapped on that
# specific refusal.
def _mod_fn(name):
    return ast.get_source_segment(
        src, next(n for n in tree.body
                  if isinstance(n, ast.FunctionDef) and n.name == name))


check(src.count("memmap=True") == 1
      and "memmap=True" in _mod_fn("_with_fits"),
      "exactly one memmap=True remains, inside _with_fits itself")
for fn in ("_header_string", "_fits_filter", "_flat_shape",
           "_is_blank_frame"):
    check("_with_fits(" in _mod_fn(fn),
          f"{fn} reads through the retrying opener")
check('"memmap=False" not in str(exc)' in _mod_fn("_with_fits"),
      "and only astropy's own refusal triggers the retry — other "
      "ValueErrors still propagate")
# The resource tracker is started while the environment is clean, so
# sirilpy's lazy mid-run spawn no longer dies with PermissionError and
# sprays tracebacks into Siril's log (1.7.9 hardened the log readers
# against exactly those; this removes them at the source).
check("_resource_tracker.ensure_running()" in src
      and src.index("ensure_running") < src.index("import numpy as np"),
      "the multiprocessing resource tracker is started at import time, "
      "before the heavy imports")

print("\n19) a dead Siril fails the run once, not every fallback in turn")
# On a real run Siril crashed during seqplatesolve; the broken pipe then
# matched every fallback's `except (CommandError, DataError, SirilError)`
# and the log blamed plate solving, star alignment and single-pass
# registration in turn, for both filters — four diagnoses for one dead
# process.  A transport death is not a command failure.
cmd_body = body("_cmd")
check("_connection_dead(exc)" in cmd_body
      and "raise SirilGoneError" in cmd_body,
      "_cmd, the single funnel every command uses, converts a transport "
      "death into SirilGoneError")
check(src.count("raise SirilGoneError") == 1,
      "and only there — no other raise site to drift out of sync")
check(src.count("except SirilGoneError") == 1,
      "exactly one handler: the fallback chains never catch it, so it "
      "rises straight to the worker's top level")
run_body = body("run")
check("except SirilGoneError" in run_body
      and (run_body.index("except SirilGoneError")
           < run_body.index("except Exception as exc:")),
      "which catches it before the generic crash handler")
check("Reuse existing masters" in run_body,
      "and the message names the recovery: restart Siril, re-run, reuse "
      "the finished masters")


# ---------------------------------------------------------------------------
print("\n20) 1.7.15 — the quality-filter value is reset in BOTH directions")
# The reset used to be keyed on "the old value no longer fits the new
# range", which only ever fired one way: 90 does not fit 1..10, so
# % -> k-sigma was correct, while k-sigma -> % left a 3 in a box now
# reading "3 %" -- a filter keeping the best three percent of the frames.


class _Spin:
    """A QSpinBox that clamps on setRange and setValue, exactly as Qt does."""

    def __init__(self, v=90):
        self._lo, self._hi, self._v = 1, 100, v
        self.suffix = ""

    def setRange(self, lo, hi):
        self._lo, self._hi = lo, hi
        self._v = max(lo, min(hi, self._v))

    def setValue(self, v):
        self._v = max(self._lo, min(self._hi, v))

    def value(self):
        return self._v

    def setSuffix(self, sfx):
        self.suffix = sfx


mode_ns = {"getattr": getattr}
exec("from __future__ import annotations\n"
     + textwrap.dedent(_cls_method("ImageMonoTrainWindow",
                                   "_on_filter_mode_changed")), mode_ns)
_on_mode = mode_ns["_on_filter_mode_changed"]


class _ModeWin:
    def __init__(self):
        self._filter_spins = [_Spin() for _ in range(4)]
        self._applying_preset = False
        self._restoring_settings = False
        _on_mode(self, "% best")          # the constructor's own call


mw = _ModeWin()
check(all(s.value() == 90 and s.suffix == " %" for s in mw._filter_spins),
      "construction leaves the boxes at 90 %")
_on_mode(mw, "k-sigma")
check(all(s.value() == 3 and s.suffix == " σ" for s in mw._filter_spins),
      "% -> k-sigma resets to 3 sigma (this direction always worked)")
_on_mode(mw, "% best")
check(all(s.value() == 90 for s in mw._filter_spins),
      "k-sigma -> % resets to 90 % — it used to leave a 3, i.e. 'keep the "
      "best 3 %', which on 200 frames really integrates six of them")
mw._filter_spins[0].setValue(75)
_on_mode(mw, "% best")
check(mw._filter_spins[0].value() == 75,
      "re-applying the SAME mode leaves the user's own value alone")

print("\n20b) the presets say which mode their numbers are in")
for name, preset in ns_presets["PRESETS"].items():
    check(preset.get("filter_mode") == "% best",
          f"{name!r} names the mode its 90 belongs to")
ap = _cls_method("ImageMonoTrainWindow", "_apply_preset")
check("QComboBox" in ap and "isinstance(widgets.get(kv[0]), QComboBox)" in ap,
      "and _apply_preset applies the combos FIRST, so the mode sets the "
      "range before the values land in it")
check('"filter_mode": self.cmb_filter_mode' in _cls_method(
          "ImageMonoTrainWindow", "_preset_widgets"),
      "the preset widget map carries the mode combo")

print("\n21) 1.7.15 — a channel dropped by the alignment says why")
am = _cls_method("StackWorker", "_align_masters")
check(am.count("self._align_dropped[filt]") == 2,
      "both exclusions — missing file and a contradicting FILTER keyword — "
      "record their reason")
run_src = _cls_method("StackWorker", "run")
check("self._align_dropped.get(filt)" in run_src
      and "errors.setdefault(" in run_src,
      "and run() carries them into `errors`, so the report cannot fall "
      "through to 'not reached — the run was stopped' about a filter whose "
      "master is sitting in masters/")

print("\n22) 1.7.15 — the grid check reads the files, not the align flag")
check("if want_compose and len(final_paths) >= 2:" in run_src,
      "_mixed_grids runs whenever a composite is about to be built")
check("if want_compose and not did_align" not in run_src,
      "not only when alignment did NOT run — which was exactly the case "
      "the single-pass fallback (no -framing=min) slipped through")
check("self._align_framing_min = True" in am,
      "the alignment records whether -framing=min really applied")
check("_align_framing_min" in run_src,
      "and the message distinguishes the fallback from a plain failure")

print("\n23) 1.7.15 — smaller guards")
fin = _cls_method("StackWorker", "_finish_composite")
check("solved = inherited" in fin,
      "an inherited WCS survives a platesolve that refuses the composite")
spcc = _cls_method("StackWorker", "_spcc_args")
check("DEFAULT_NB_BANDWIDTH" in spcc and 'nb_bandwidth", 7' not in spcc,
      "the narrowband bandwidth falls back to the documented default")
sa = _cls_method("StackWorker", "_stack_all_filters")
check(sa.count("to register and stack.") == 2
      and "falling back from per-part calibration" in sa,
      "the two-frame guard is re-checked after the per-part fallback — the "
      "one above it ran on the count of the PARTS")
check(sa.index("falling back from per-part calibration")
      < sa.index("proc_dir = os.path.join(work, \"process\")"),
      "and it stops the filter BEFORE the conversion, so a re-stage that "
      "came back short becomes a clean skip, not a Siril error")


print("\n24) 1.7.15 — a crop that was asked for but did not happen")
# Siril ACCEPTS -framing=min on the astrometric (plate-solve) path, raises
# nothing, and exports frames of differing sizes anyway; `stack` then says
# "Forcing to maximize framing" and the master comes out LARGER than any
# sub.  Observed on an NGC 6946 run: 3008x3008 subs, r_ frames 3007x3008
# to 3013x3014, master 3060x3128.  Nothing raised, so nothing was recorded.
cf = _cls_method("StackWorker", "_check_framing")
check("_reg_frame_sizes(process_dir, seq)" in cf,
      "the frames themselves are asked — only they can answer this")
check("if len(sizes) < 2:\n            return" in cf,
      "one common size is silent")
check('self._reg_degraded[filt] = ["-framing=min"]' in cf,
      "a differing set records -framing=min as not applied")
check("self._reg_degraded_why[filt]" in cf and "accepted the argument" in cf,
      "...with its own reason, so the report cannot print the refusal "
      "wording for a case Siril never refused")
check("if filt in self._reg_degraded:\n            return" in cf,
      "a channel already recorded as degraded keeps its own story")
sizes_src = _cls_method("StackWorker", "_reg_frame_sizes")
check("_read_header(" in sizes_src and ".data" not in sizes_src,
      "sizes come from headers, never from pixel data")
check("if len(sizes) > 1:\n                break" in sizes_src,
      "...and the scan stops at the first disagreement")
check("self._check_framing(" in sa
      and 'if self._opts.get("crop_edges", True):' in sa,
      "the check runs where the exported frames are already being counted, "
      "and only when the crop was actually asked for")

print("\n24b) the report tells the two causes apart")
docs = _cls_method("StackWorker", "_write_docs")
check("self._reg_degraded_why.get(" in docs
      and "Siril refused the full argument set" in docs,
      "the refusal wording is the FALLBACK now, not the only sentence")

print("\n25) 1.7.15 — an inherited solution is not claimed as new work")
ps = _cls_method("StackWorker", "_platesolve_file")
check("inherited = _has_wcs(path)" in ps,
      "the header is asked before the command runs")
check("already carried an" in ps and "if inherited:" in ps,
      "an already-solved master says so instead of 'Plate-solved'")
check(ps.index('self._cmd("platesolve")') < ps.index("if inherited:"),
      "...and the command still runs — whether an existing solution is "
      "good enough is Siril's call, not this function's")

print("\n26) 1.7.15 — SPCC gets the solution it asks for")
# Siril asks for one twice per finish: "Found linear plate solve data,
# you may need to solve your image with distortions to ensure correct
# calibration of stars near image corners."  It does NOT fix the weak
# colour fit -- an A/B on one composite moved sigma(R/G) 2.2497 -> 2.2481
# -- so what is asserted here is the request being answered, and the
# guards that keep answering it from costing anything else.
fc = _cls_method("StackWorker", "_finish_composite")
check("_has_sip(path)" in fc,
      "the header is asked whether the inherited solution carries SIP")
check("-force" in fc,
      "and the re-solve is forced — Siril answers 'Nothing will be done' "
      "to a plain platesolve on a solved image")
check("-noflip" in fc,
      "...with the flip disabled: a forced solve may flip an image it "
      "reads as upside-down, and the composite must stay on the masters' "
      "grid")
check("f\"-order={SPCC_SIP_ORDER}\"" in fc,
      "the SIP order is passed explicitly, not left to Siril's preferences")
check("self._photometry_planned(palette)" in fc,
      "and it only runs when a photometric calibration really will")
check(fc.index("_has_sip(path)") < fc.index("_colour_calibrate"),
      "the solve happens BEFORE the calibration that needs it")
check("continuing with the solution the image still carries" in fc,
      "a refused solve does not abort the finish")
# The gate is a copy of _colour_calibrate's own refusals; if that method
# grows a new one, this must follow.
ns26: dict = {}
exec(src[src.index("_NB_PALETTES = {"):src.index("# The emission line")],
     ns26)
exec("from __future__ import annotations\n"
     + textwrap.dedent(_cls_method("StackWorker", "_photometry_planned")),
     ns26)


class _W:
    def __init__(self, **o):
        self._opts = o
    _photometry_planned = ns26["_photometry_planned"]


check(_W().  _photometry_planned("RGB") is True,
      "a plain RGB composite is calibrated photometrically")
check(_W()._photometry_planned("HaRGB") is False,
      "HaRGB is not — its Red carries blended Ha, so star colours are not "
      "physical, and a solve for it would be pure cost")
check(_W(use_spcc=False)._photometry_planned("HOO") is False,
      "narrowband with SPCC off leaves no attempt at all: PCC assumes "
      "broadband star colours")
check(_W(use_spcc=True)._photometry_planned("HOO") is True,
      "narrowband with SPCC on still measures stars")
check(_W(use_spcc=False)._photometry_planned("RGB") is True,
      "and SPCC off on broadband still falls through to PCC")

print("\n27) 1.7.16 — a drop is blamed on what actually caused it")
# A run with the quality filters on said "Frames without enough detectable
# stars (clouds, haze) cannot be aligned" about 15 frames, four seconds
# after the same log reported "74 images successfully platesolved out of
# 74 included".  Nothing had failed to align; the filters the user asked
# for had removed them.  Both causes still land in the same count, so the
# only honest fix is to say which one it was.
seg = src[src.index("Registration itself can drop frames"):]
seg = seg[:seg.index("_effective_frame_count")]
check("self._qf_decision.get(" in seg,
      "the message asks whether the quality filters fired")
check("removed by " in seg and "the quality filters ({flags})" in seg,
      "and names them as the cause when they did")
check("A frame that could not be " in seg
      and "aligned would count here too" in seg,
      "without claiming the other cause is impossible")
check("clouds, haze" in seg,
      "the weather wording survives for the case it was written for")
check(seg.index("if flags:") < seg.index("clouds, haze"),
      "and it is the fallback, not the default")
check("self._quality_filter_args(n_linked)" in seg,
      "the flags shown are the ones registration was actually given")
# ...and the short-channel warning used to hang off the same condition:
# it sat inside the drop branch, so a filter that STARTED below the floor
# and lost nothing was never warned.
guard = "if n_reg and n_reg <= PERCENTILE_MAX_FRAMES:"
short = seg[seg.index(guard):]
check(seg.index(guard) > seg.index("cannot be aligned"),
      "the short-channel warning stands on its own, after the drop branch")
# 1.7.17: and it is bound to the RIGHT number.  MIN_STACK_FRAMES is the
# floor the quality filters may not cross; the sentence is about what
# rejection can still do, which is the percentile band.  With `<` against
# the floor, a channel of exactly four frames -- percentile clipping, the
# weakest case there is -- said nothing at all.
check("MIN_STACK_FRAMES" not in guard,
      "the condition reads the percentile band, not the quality-filter "
      "floor, which means something else entirely")
check("<=" in guard,
      "and it includes its own edge: four frames IS the percentile band")
check("Only {n_reg} frame(s) for {filt}" in short,
      'and no longer says "left" — nothing need have been lost')
check(seg.count("                if n_reg") == 2,
      "both checks are top-level: neither is nested inside the other")

print("\n28) 1.7.16 — the SPCC panel shows the half the palette uses")
# A SHO run displayed three filled-in RGB filter boxes and calibrated by
# wavelength anyway; that the names were unused was said only in the Log,
# after the start.  Asserted here: the panel reads the SAME table the
# command line is built from, so the two cannot drift.
nsm: dict = {}
exec(src[src.index("HA_NM = "):src.index("# UI label")], nsm)
exec(src[src.index("_NB_PALETTES = {"):src.index("_ROLE_WORDS = {")], nsm)
_tg, _pal = nsm["_nb_line_targets"], nsm["_NB_PALETTES"]
check(_tg("SHO") == {"ha": "G", "oiii": "B", "sii": "R"},
      "SHO puts SII in red, Ha in green, OIII in blue", str(_tg("SHO")))
check(_tg("HOO")["oiii"] == "G, B" and _tg("HOO")["sii"] == "",
      "HOO sends ONE OIII filter to two channels and uses no SII",
      str(_tg("HOO")))
check(all(sorted("".join(_tg(p).values()).replace(", ", ""))
          == sorted("RGB") for p in _pal),
      f"every channel of all {len(_pal)} narrowband palettes is accounted "
      "for exactly once")
check(not any(_tg("LRGB").values()) and not any(_tg("Auto").values()),
      "a broadband palette claims no line at all")

# Bandwidth belongs to the FILTER: the same OIII passband must reach both
# channels HOO maps it to.  Checked on the real command line, not on the
# source that builds it.
nsa = dict(nsm, DEFAULT_NB_BANDWIDTH=4.5,
           LogColor=type("L", (), {"SALMON": 0, "GREEN": 1, "BLUE": 2}))
exec(textwrap.dedent(_cls_method("StackWorker", "_spcc_args")), nsa)


class _SP:
    _opts = {"spcc_sensor": "Sony IMX411/455/461/533/571",
             "nb_bandwidths": {"ha": 4.5, "oiii": 6.5, "sii": 3.0}}
    def _check_spcc_name(self, *a):
        pass
    def _emit(self, *a, **k):
        pass
    _spcc_args = nsa["_spcc_args"]


_line = " ".join(_SP()._spcc_args("HOO"))
check("-gbw=6.5" in _line and "-bbw=6.5" in _line,
      "HOO gives green and blue the one OIII bandwidth", _line)
check("-rbw=4.5" in _line, "...and red the Ha one, independently")
_sho = " ".join(_SP()._spcc_args("SHO"))
check("-rbw=3" in _sho and "-gbw=4.5" in _sho and "-bbw=6.5" in _sho,
      "SHO carries three different widths through to three channels",
      _sho)
check(src.count('"nb_bandwidth"') == 1
      and '_legacy = float(st.value("nb_bandwidth"' in src,
      "the old single-value key survives in exactly one place: the "
      "migration that seeds the three new ones")

rf = _cls_method("ImageMonoTrainWindow", "_refresh_spcc_mode")
check("_NB_PALETTES" in rf and "spcc and (auto or not nb)" in rf,
      "the two halves are enabled by palette, not by one flat switch")
check("_nb_line_targets(palette)" in rf and "targets[_role]" in rf,
      "and a line the palette does not use greys out on its own")
check('palette == "Auto"' in rf,
      "Auto leaves both live — which applies is not knowable yet")
check("_refresh_spcc_mode()" in _cls_method("ImageMonoTrainWindow",
                                            "_on_palette_changed"),
      "a palette change refreshes the panel")

# ...and the greying itself was invisible.  A stylesheet rule naming
# `color` applies in every state unless a :disabled rule overrides it, and
# the shared theme has one only for QPushButton -- so every setEnabled
# (False) in this file changed nothing on screen.  1.7.16 answered that
# with six :disabled rules; 1.7.17 moved the answer to the PALETTE, which
# needs no rule per widget class.
nsd: dict = {}
exec(src[src.index("DISABLED_STYLESHEET = "):src.index("_THEME_MODE = ")],
     nsd)
dis = nsd["DISABLED_STYLESHEET"]
for _w in ("QLabel", "QCheckBox", "QLineEdit", "QComboBox", "QSpinBox"):
    check(f"{_w}:disabled" in dis, f"{_w} has a disabled state to render")
check("setStyleSheet(_window_stylesheet())" in src,
      "and the window applies whichever sheet the theme calls for")
theme = src[src.index("DARK_STYLESHEET = "):
            src.index("QScrollBar::sub-line:vertical{height:0}")]
check(":disabled" not in theme.replace("QPushButton:disabled", ""),
      "the shared theme is extended, not edited — it is copied verbatim "
      "between the Svenesis scripts")

# The palette is what makes this general: a :disabled CSS rule reaches only
# the widget classes it names, and the next widget added would be missed
# again.  ColorGroup.Disabled reaches every widget there is.
ap = _fn_src("_apply_theme")
check("QPalette.ColorGroup.Disabled" in ap,
      "the disabled colours live on the palette, not on a list of widgets")
for _r in ("WindowText", "Text", "ButtonText"):
    check(f"QPalette.ColorRole.{_r}" in ap,
          f"{_r} greys out for every widget, named or not")
check("Base" in ap and "Button" in ap,
      "and the backgrounds follow, so light mode needs no sheet at all")
check("_window_stylesheet" in src and 'if _THEME_MODE == "dark"' in
      _fn_src("_window_stylesheet"),
      "light mode drops the dark sheet instead of carrying a second copy")

# Following Siril matters because this script is launched FROM Siril.
tm = _fn_src("_siril_theme_mode")
check('get_siril_config("gui", "theme")' in tm,
      "the theme is read from Siril, not assumed")
check('{0: "dark", 1: "light"}' in tm,
      "0/1 are Siril's documented values")
check('return "dark"' in tm and "_log_swallowed" in tm,
      "an unreadable setting falls back to dark rather than failing")

check('setStyleSheet("color:#888888' not in src,
      "and no hint label keeps a bare colour that would outrank :disabled")

# --------------------------------------------------------------------
print("\n29) every run leaves a replayable record of what it told Siril")
# Reconstructing a run from a pasted GUI log is how command-level defects
# were bisected until now.  `_cmd` is the single funnel, so the record is
# complete by construction.
rc = _cls_method("StackWorker", "_record_command")
cmd = _cls_method("StackWorker", "_cmd")
check("self._record_command(*args)" in cmd,
      "the record is written from the one funnel every command goes through")
check(cmd.index("_record_command") < cmd.index("self.siril.cmd("),
      "and BEFORE the call — the command that kills a run is the "
      "interesting line, and it must not be the missing one")
wc = _cls_method("StackWorker", "_write_commands")
check("COMMANDS_FILENAME" in wc and "_atomic_write_text" in wc,
      "written atomically: it is rewritten after every command, so a "
      "crash mid-write is not hypothetical")
check("requires " in wc and "SIRIL_MIN_VERSION" in wc,
      "carries the `requires` line a Siril script needs")
check("_SCRIPT_FORBIDDEN_COMMANDS" in wc and "GUI-ONLY" in wc,
      "and marks the commands Siril refuses in a script instead of "
      "quietly rewriting them")
check("_write_commands()" in _cls_method("StackWorker", "_note_command"),
      "a note lands on disk as soon as it is made, like a command")
# The header used to read "Replay headless: siril-cli -s commands.ssf"
# with load_seq as the only caveat.  Three larger obstacles went unsaid,
# and the worst of them fails SILENTLY: `new` makes an empty canvas and
# the composed pixels arrive through sirilpy, so a replay saves a blank
# colour image under the right name.
check("Replay headless" not in wc,
      "the header no longer promises a replay the file cannot deliver")
for want, why in (("A RECORD", "says what it is: a record"),
                  ("BLANK colour image", "names the silent failure"),
                  ("WORK_DIRNAME", "and that the work folders are deleted")):
    check(want in wc, f"the header {why}")
ns_c: dict = {}
exec(src[src.index("COMMANDS_FILENAME = "):src.index("# Calibration masters")],
     ns_c)
check(ns_c["COMMANDS_FILENAME"].endswith(".ssf"),
      f'the record is a Siril script: {ns_c["COMMANDS_FILENAME"]}')
check("load_seq" in ns_c["_SCRIPT_FORBIDDEN_COMMANDS"],
      "load_seq is known to be GUI-only")

# --------------------------------------------------------------------
print("\n30) a cleanup that fails is never silent")
# Two cases that must NOT share a reaction.
clear = _cls_method("StackWorker", "_clear_stale_dir")
disc = _cls_method("StackWorker", "_discard_dir")
check("raise RuntimeError" in clear,
      "clearing a directory that is about to be REFILLED fails the run — "
      "leftovers get linked into the new sequence and stacked silently")
check("raise" not in disc and "_emit" in disc,
      "discarding one nothing reads again only warns and carries on")
check("ignore_errors=True" in clear and "os.path.isdir(path)" in clear,
      "both re-check the directory afterwards: ignore_errors hides the "
      "very failure being tested for")
drv = body("_stack_all_filters")
check("self._clear_stale_dir(" in drv,
      "the per-filter sequence tree is cleared through the strict path")
check("shutil.rmtree" not in drv,
      "and no call site reaches rmtree directly any more")
rw = _cls_method("StackWorker", "_release_work")
check("self._discard_dir(" in rw,
      "a finished filter's tree goes through the lenient path")

print("\n31) a stage that wrote nothing fails where it happened")
vo = _cls_method("StackWorker", "_verify_outputs")
check("getsize" in vo and "> 0" in vo,
      "a zero-byte file counts as missing — a `save` that creates the "
      "file and never fills it is the silent case")
check("stage" in vo and "raise RuntimeError" in vo,
      "and the message names the stage, not the step that tripped later")
check('self._verify_outputs([final], f"{filt} master")' in drv,
      "the master is checked AFTER the background extraction rewrote it, "
      "not only after the stack")
check("_verify_outputs" in _cls_method("StackWorker", "_align_masters"),
      "and every aligned channel is checked before it becomes a colour")


# --------------------------------------------------------------------
print("\n32) the hot-pixel threshold follows the stack size")
# Rejection only removes a hot pixel because dithering moves it to a
# different sky pixel each frame.  That argument needs frames, so the
# cosmetic map has to do more of the work when there are few.
ns_cc: dict = {}
for _k in ("COSMETIC_COLD_SIGMA", "COSMETIC_HOT_SIGMA",
           "COSMETIC_TIGHT_HOT_SIGMA"):
    ns_cc[_k] = re.search(rf'^{_k} = "(.+)"$', src, re.M).group(1)
ns_cc["COSMETIC_TIGHT_MAX_FRAMES"] = int(
    re.search(r"^SIGMA_MAX_FRAMES = (\d+)$", src, re.M).group(1))
exec(_fn_src("_cosmetic_args"), ns_cc)
_cc = ns_cc["_cosmetic_args"]
check(float(ns_cc["COSMETIC_TIGHT_HOT_SIGMA"])
      < float(ns_cc["COSMETIC_HOT_SIGMA"]),
      "the tight threshold is LOWER — a smaller sigma flags more pixels")
check(_cc(4)[0] == ["-cc=dark", "3", "2.5"],
      f"a 4-frame channel is corrected harder: {_cc(4)[1]}")
check(_cc(148)[0] == ["-cc=dark", "3", "3"],
      f"a 148-frame channel is not: {_cc(148)[1]}")
check(_cc(0)[1] == _cc(148)[1],
      "an UNKNOWN count takes the standard pair — never the tighter one "
      "on a guess")
_edge = ns_cc["COSMETIC_TIGHT_MAX_FRAMES"]
check(_cc(_edge)[1] != _cc(_edge + 1)[1],
      f"and the band edge is exactly at {_edge}")
check(_cc(1)[1] == _cc(_edge)[1],
      "every count in the band gets the same answer")

ca = _cls_method("StackWorker", "_calibrate_args")
check("n_frames: int = 0" in ca,
      "the count is a parameter, not read from mutable state — "
      "_current_n_frames is only set AFTER calibration runs")
check("_cosmetic_args(n_frames)" in ca,
      "and it decides the arguments")
check("self._cc_used[filt]" in ca,
      "what was really sent is recorded, so the report cannot quote the "
      "constant instead of the run")
drv2 = body("_stack_all_filters")
check("n_frames=n_linked" in drv2,
      "the single-pass path passes the staged count")
cip = _cls_method("StackWorker", "_calibrate_in_parts")
check("n_total = sum(" in cip and "n_frames=n_total" in cip,
      "and the split path passes the filter's TOTAL — the parts are "
      "merged again before stacking, so a 4-frame part of a 60-frame "
      "filter is not a small stack")

print("\n33) the aligned channels are checked for overlay, not just size")
ov = _fn_src("_overlay_error_px")
check("all_pix2world" in ov and "all_world2pix" in ov,
      "the check goes through the sky: pixel -> world -> pixel")
check("has_celestial" in ov and "return None" in ov,
      "a master without a usable solution is 'cannot tell', not agreement")
check("getheader" in ov and "getdata" not in ov,
      "headers only — no pixel data is read for this")
co = _cls_method("StackWorker", "_check_overlay")
check("len(aligned) < 2" in co,
      "one channel cannot disagree with itself")
check("if result is None" in co and "return" in co,
      "and 'cannot tell' stays silent rather than warning")
check("OVERLAY_MAX_PX" in co,
      "the threshold is named, not inlined")
am2 = _cls_method("StackWorker", "_align_masters")
check("self._check_overlay(aligned)" in am2,
      "it runs at the end of the alignment, on the set that becomes the "
      "composite")


# --------------------------------------------------------------------
print("\n34) 1.7.17 — the frame-loss warning uses the PESSIMISTIC estimate")
# Survivors pass EVERY filter, so min(shares) is an upper bound on them
# and therefore a LOWER bound on the loss -- the wrong direction for a
# warning about losing too much.  On one NGC 6946 run it predicted
# 13-14% dropped against 21-23% real, and stayed silent on all four
# channels.
_w = _QF(_opts("percent", f_wfwhm=90, f_round=87))
_WARN = float(re.search(r"^FILTER_WARN_FRACTION = ([\d.]+)",
                        src, re.M).group(1))
for _f, _n, _real in (("BLUE", 74, 57), ("GREEN", 70, 55),
                      ("LUMINOS", 190, 148), ("RED", 66, 52)):
    _opt = _w._effective_frame_count(_n)
    _pes = _w._projected_frame_count(_n)
    check(_pes <= _real + 1 and _pes >= _real - 2,
          f"{_f}: projected {_pes} is within a frame of the real {_real}",
          f"optimistic bound said {_opt}")
    check((_n - _pes) / _n > _WARN,
          f"{_f}: the note fires ({(_n - _pes) / _n:.1%} > {_WARN:.0%})",
          f"with the old estimate it was {(_n - _opt) / _n:.1%}")
check(_w._projected_frame_count(74) < _w._effective_frame_count(74),
      "the two estimates bracket the truth from opposite sides")
reg_src = _cls_method("StackWorker", "_register")
check("_projected_frame_count(n_in)" in reg_src,
      "and the warning reads the pessimistic one")
check("_effective_frame_count" not in reg_src,
      "not the optimistic one, which is for reporting an upper bound")
# k-sigma cannot be predicted at all and must not be guessed at.
check(_QF(_opts("k-sigma", f_wfwhm=3))._projected_frame_count(40) == 40,
      "k-sigma returns the full count rather than inventing a number")

print("\n35) 1.7.17 — a filter that never reaches Siril says so")
# The spin boxes accept 1-100.  Asking for the best 15% of 25 frames
# produced no filter AND no message: the full stack, silently.
for _val, _want in ((20, True), (16, True), (15, False), (10, False)):
    _a, _sk, _ = _QF(_opts("percent", f_wfwhm=_val))._quality_filter_plan(25)
    check(bool(_a) == _want and bool(_sk) != _want,
          f"{_val}% -> {'applied' if _want else 'skipped AND reported'}",
          f"args={_a} skipped={_sk}")
_a, _sk, _ = _QF(_opts("percent", f_wfwhm=10))._quality_filter_plan(25)
check(_sk and "-filter-wfwhm" in _sk[0][0] and str(MIN := 4) in _sk[0][2],
      f"the reason names the floor it hit: {_sk[0][2] if _sk else '-'}")
check("was NOT applied" in reg_src,
      "and the run says it out loud rather than shipping a shorter list")
check("still in the stack" in reg_src,
      "naming the consequence: those frames were all integrated")

print("\n36) 1.7.17 — a longer dark is not the same mistake as a shorter one")
# Dark current grows with exposure.  A longer dark OVER-subtracts, the
# background goes negative, and Siril clamps to [0,1] -- the faint signal
# in those pixels is gone.  A shorter one leaves a pedestal the
# background extraction removes anyway.
cd_src = _cls_method("StackWorker", "_closest_dark")
ns_d = {}
for _k in ("DARK_EXPOSURE_TOLERANCE", "DARK_OVERSHOOT_TOLERANCE"):
    ns_d[_k] = float(re.search(rf"^{_k} = ([\d.]+)", src, re.M).group(1))
check(ns_d["DARK_OVERSHOOT_TOLERANCE"] < ns_d["DARK_EXPOSURE_TOLERANCE"],
      f"a longer dark has the tighter bound "
      f"({ns_d['DARK_OVERSHOOT_TOLERANCE']:.0%} against "
      f"{ns_d['DARK_EXPOSURE_TOLERANCE']:.0%})")
check("abs(float(have) - float(want))" not in cd_src,
      "the selection is no longer symmetric in |delta|")
check("1 if longer else 0" in cd_src,
      "ties go to the SHORTER dark — under-subtraction is the "
      "recoverable half")
check("over-subtracts" in cd_src and "under-subtracts" in cd_src,
      "and the message names which way it went, not just how far")


# --------------------------------------------------------------------
print("\n37) 1.7.17 — a star count sitting on Siril's ceiling is not a "
      "measurement")
# The manual gives -maxstars as "must be between 100 and 2000", so 2000 is
# the ceiling.  On a star-rich field every frame hits it, and then
# -weight=nbstars gives them all the same weight.
_cap = int(re.search(r"^SIRIL_MAX_STARS = (\d+)", src, re.M).group(1))
check(_cap == 2000, f"the ceiling is Siril's documented maximum ({_cap})")
sq = _cls_method("StackWorker", "_seq_quality")
check("SIRIL_MAX_STARS" in sq and "capped" in sq,
      "the registration read notices when the count is the ceiling")
check("not a measurement" in sq,
      "and says so where the number is printed")
check('_weight_token(self._opts) == "nbstars"' in sq,
      "the warning is tied to the weighting that the cap actually breaks")
check("'Noise' or" in sq or "Noise" in sq,
      "and names the two modes that still separate these frames")
# wFWHM scales FWHM, which still varies, so it must NOT be warned about.
check("wfwhm" not in sq.lower().replace("weighted fwhm", ""),
      "wFWHM is not swept into the same warning — it still discriminates")
wd = _cls_method("StackWorker", "_write_docs")
check("_stars_capped" in wd and "†" in wd,
      "the report marks the capped figure rather than printing it plain")

print("\n38) 1.7.17 — the flat noise floor does not straddle time")
fs = _fn_src("_spread_sample")
check("step = n / float(limit)" in fs,
      "the sample is spread by an even stride, not taken from the head")
_ss: dict = {}
exec(fs, _ss)
_got = _ss["_spread_sample"](list(range(20)), 8)
check(len(_got) == 8 and _got[0] == 0 and _got[-1] >= 15,
      f"20 items capped at 8 now span the run: {_got}")
check(_got == sorted(_got),
      "order is preserved — the caller interleaves the result afterwards")
check(_ss["_spread_sample"](list(range(5)), 8) == list(range(5)),
      "fewer items than the cap are returned untouched")
check("_spread_sample(paths, limit)" in _fn_src("_flat_shape"),
      "and the night maps are built from that spread sample")

print("\n39) 1.7.17 — the rejection fallback errs towards the gentler "
      "algorithm")
drv3 = body("_stack_all_filters")
check("n_stack = n_reg or self._projected_frame_count(n_linked)" in drv3,
      "an unreadable count falls back to the PESSIMISTIC estimate")
check("effective = n_reg or self._effective_frame_count(n_linked)" in drv3,
      "while the report keeps the optimistic one for its '<=N used'")
# The old fallback was n_linked itself: the full staged count, as if the
# quality filters had not run at all.
check("n_stack = n_reg or n_linked" not in drv3,
      "not the staged count, which ignored the filters entirely")

print("\n40) 1.7.17 — drizzle's warning matches the settings it ships with")
_pf = float(re.search(r"^DRIZZLE_PIXFRAC = ([\d.]+)", src, re.M).group(1))
check("-pixfrac={DRIZZLE_PIXFRAC:g}" in _cls_method("StackWorker",
                                                    "_register"),
      "pixfrac is the named constant, not a literal beside the warning")
reg3 = _cls_method("StackWorker", "_register")
# Only the MESSAGE matters: the comment above it is allowed to name the
# claim it replaced, and forbidding the word outright caught that too.
_msg = "\n".join(l for l in reg3.splitlines()
                 if not l.lstrip().startswith("#"))
check("unevenly filled" not in _msg and "patchy" not in _msg.lower(),
      f"the patchy-coverage claim is gone from the message — it cannot "
      f"happen at pixfrac {_pf:g}")
check("sample between the pixels" in reg3,
      "and the real reason is named: sub-pixel sampling")
check("correlated neighbours" in reg3,
      "together with what you do get instead")

print("\n41) 1.7.17 — every calibration tolerance carries its reasoning")
_head = src[:src.index("def _is_fits")]
for _c in ("DARK_EXPOSURE_TOLERANCE", "DARKFLAT_EXPOSURE_TOLERANCE",
           "DARK_OVERSHOOT_TOLERANCE", "CALIB_TEMP_TOLERANCE_C"):
    _i = re.search(rf"^{_c} = ", _head, re.M).start()
    _before = _head[:_i].rstrip().splitlines()[-1].strip()
    check(_before.startswith("#"),
          f"{_c} is explained on the line above it")
# Anchored on the ASSIGNMENT.  `index()` on the bare name finds the
# CHANGELOG, which now discusses this constant in prose -- the same trap
# that caught the docs suite one version ago.
_ti = re.search(r"^CALIB_TEMP_TOLERANCE_C = ", _head, re.M).start()
check("doubles" in _head[max(0, _ti - 900):_ti].lower(),
      "and the temperature one names the exponential it governs")


# --------------------------------------------------------------------
print("\n42) 1.7.17 — RBF is the wrong background model for line emission")
# Measured with siril-cli on a nebula filling 95% of the frame: the
# degree-1 polynomial keeps 99.9% of it, RBF keeps 18%.
_kept_rbf = float(re.search(r"^RBF_NARROWBAND_KEPT = ([\d.]+)",
                            src, re.M).group(1))
_kept_p1 = float(re.search(r"^POLY1_NARROWBAND_KEPT = ([\d.]+)",
                           src, re.M).group(1))
check(_kept_rbf < _kept_p1,
      f"the measurement is recorded: RBF keeps {_kept_rbf:.0%}, "
      f"degree 1 keeps {_kept_p1:.1%}")
ss = _cls_method("StackWorker", "_subsky")
check("narrowband: bool = False" in ss,
      "the model chooser is told whether the image is line emission")
check("RBF_NARROWBAND_KEPT" in ss,
      "and quotes the measured figure rather than an adjective")
check("_rbf_warned" in ss,
      "said once per place, not once per channel")
# It WARNS, it does not override: the setting is the user's.
check("self._opts.get(\"bg_rbf\", False)" in ss and "return" in ss,
      "RBF still runs when asked for — a silent swap would change images")
bem = _cls_method("StackWorker", "_bg_extract_master")
check("_filter_role(filt) in _LINE_NM" in bem,
      "a master knows it is narrowband from its own FILTER")
fin = _cls_method("StackWorker", "_finish_composite")
check("_NB_PALETTES.get(" in fin,
      "and the composite from its palette")
drv4 = body("_stack_all_filters")
check("_bg_extract_master(final, filt)" in drv4,
      "the filter reaches the extraction that needs it")

print("\n43) 1.7.17 — the colour-fit threshold is scale-free")
# sigma is the scatter of *Image* R/G, so it carries whatever scale the
# channels are on -- and `-output_norm` divides each master by its own
# brightest pixel.  Scaling the ratio by k scales slope and sigma alike.
ns_s: dict = {"re": re}
for _n in ("_parse_spcc_fit", "_spcc_relative_sigma"):
    exec("from __future__ import annotations\n" + _fn_src(_n), ns_s)
_off = ns_s["_parse_spcc_fit"](
    "Image B/G = -0.021290 + 1.174313 * Catalog B/G (sigma: 0.322732)")
_on = ns_s["_parse_spcc_fit"](
    "Image B/G = -0.012205 + 0.786050 * Catalog B/G (sigma: 0.216192)")
check(_off["slope"]["B/G"] == 1.174313 and _off["intercept"]["B/G"] == -0.02129,
      "the slope and intercept are parsed, not only the sigma")
_r_off = ns_s["_spcc_relative_sigma"](_off)["B/G"]
_r_on = ns_s["_spcc_relative_sigma"](_on)["B/G"]
check(abs(_r_off - _r_on) < 0.001,
      f"two real runs of the SAME target agree once scaled out: "
      f"{_r_off:.4f} vs {_r_on:.4f}",
      f"raw sigma differed by {abs(0.322732 - 0.216192) / 0.322732:.0%}")
check(abs(0.322732 - 0.216192) > 0.1,
      "while the raw sigmas they came from did not")
check(ns_s["_spcc_relative_sigma"]({"sigma": {"R/G": 1.0},
                                    "slope": {"R/G": 0.0}}) == {},
      "a slope of zero is left out rather than dividing by it")
check(ns_s["_spcc_relative_sigma"]({"sigma": {"R/G": 1.0}}) == {},
      "and a missing slope is not guessed at")
rs = _cls_method("StackWorker", "_read_spcc_fit")
check("_spcc_relative_sigma(fit)" in rs,
      "the warning is judged on the scale-free number")
check("of its own slope" in rs,
      "and says which number it is judging")
# Two fragments: the sentence spans a line break in the source.
check('self._opts.get("output_norm", True)' in rs
      and "its own brightest pixel before this fit" in rs
      and "a measurement of the filters or the sensor" in rs,
      "and output normalisation is disclosed where the factors are printed")


# --------------------------------------------------------------------
print("\n44) a part too small to be a sequence does not take the split down")
# Siril cannot build a sequence from one file, so a one-frame part fails
# `calibrate` and the WHOLE split falls back to a pooled pass -- after
# having stacked a master flat per night that nothing then reads.  Seen
# on IC 1805: OIII arrived 8 + 1, two per-night flats were built, both
# thrown away, and the log carried an error that looks like a defect.
cs = _cls_method("StackWorker", "_calib_split")
check("len(v) < 2" in cs and "_split_refused" in cs,
      "a part under two frames refuses the split before it is attempted")
check(cs.index("thin =") < cs.index("out = []"),
      "decided BEFORE the parts are built, not after Siril rejects one")
drv5 = body("_stack_all_filters")
check("_split_refused" in drv5 and "was NOT attempted" in drv5,
      "and the run says so — discovery had announced per-night "
      "calibration, and that announcement must not be left standing")
check("cannot form a Siril sequence" in drv5,
      "naming the cause rather than only the outcome")

ns_sp: dict = {"KIND_DARK": "dark", "_safe": lambda s: str(s),
               "_exp_tag": lambda e: f"{e:g}s",
               "_night_of": lambda p, n: n.get(p, "")}
for _m in ("_calib_split", "_part_tag", "_part_label"):
    exec("from __future__ import annotations\n"
         + textwrap.dedent(_cls_method("StackWorker", _m)), ns_sp)


class _SP:
    _calib_split = ns_sp["_calib_split"]
    _part_tag = staticmethod(ns_sp["_part_tag"])
    _part_label = staticmethod(ns_sp["_part_label"])

    def __init__(self, counts):
        files, nights = [], {}
        for night, n in counts.items():
            for i in range(n):
                f = f"{night}_{i}"
                files.append(f)
                nights[f] = night
        self._opts = {"calibrate": True}
        self._groups = {"F": {"by_exp": {600.0: files},
                              "info": {"exp_s": 600.0}}}
        self._nights, self._masters = nights, {"dark": {"x": 1}}
        self._flat_nights = {"F": {k: "/m.fit" for k in counts}}
        self._split_refused = {}


for _counts, _want, _why in (
        ({"2026-09-07": 8, "2026-09-08": 1}, False, "the real OIII case"),
        ({"2026-09-07": 4, "2026-09-08": 6}, True, "the real SII case"),
        ({"2026-09-07": 2, "2026-09-08": 2}, True, "two frames is enough"),
        ({"2026-09-07": 9, "2026-09-08": 0}, True,
         "an empty night never becomes a part at all")):
    _w = _SP(_counts)
    _got = bool(_w._calib_split("F"))
    check(_got == _want,
          f"{_why}: {'splits' if _want else 'refuses'}  {_counts}",
          f"refused={_w._split_refused}")
_w = _SP({"2026-09-07": 8, "2026-09-08": 1})
_w._calib_split("F")
check(_w._split_refused.get("F") == [("2026-09-08", 1)],
      f"the reason names the part and its size: {_w._split_refused.get('F')}")

print("\n45) the tightened-cosmetic note is said once per filter")
# A split calls `_calibrate_args` per part, and OIII said the same
# sentence three times in one run.
ca2 = _cls_method("StackWorker", "_calibrate_args")
check("self._cc_said.get(filt) != cc_label" in ca2,
      "the note is gated on what was already said for this filter")
check("self._cc_said[filt] = cc_label" in ca2,
      "and records it")
# The ARGUMENTS must still be produced every time -- only the message is
# deduplicated.
check(ca2.index("args += cc") < ca2.index("self._cc_said.get"),
      "the arguments are appended before the gate, so every part is "
      "still corrected")


# --------------------------------------------------------------------
print("\n46) the record marks the steps Siril never saw")
# Read back from disk, not from the source: the point is what a user
# opening commands.ssf is told.  A run whose lights are split per night
# exercises both staging paths and the copy out of the work folder.
w, res, tmp = run(
    {"HA": group({300.0: ["2026-09-07/a1", "2026-09-07/a2",
                          "2026-09-08/b1", "2026-09-08/b2"]})},
    {"dark": {("s",): ("/d.fit", {})}},
    flat_nights={"HA": {"2026-09-07": "/f7.fit", "2026-09-08": "/f8.fit"}})
ssf = open(os.path.join(tmp, "commands.ssf"), encoding="utf-8").read()
lines = ssf.splitlines()
check(any(l.startswith("# ") and "staged into" in l for l in lines),
      "the staged light frames are named before the `link` that reads them")
# Every `link` must be preceded by a note, or the record still reads as
# though Siril filled that directory itself.
links = [i for i, l in enumerate(lines) if l.startswith("link ")]
check(links, f"{len(links)} link command(s) recorded")
unmarked = [lines[i] for i in links
            if not any(lines[j].startswith("# staged")
                       or "staged into" in lines[j]
                       for j in range(max(0, i - 3), i))]
check(not unmarked,
      "every `link` is preceded by the staging that filled its folder",
      str(unmarked[:2]))
check(sum(1 for l in lines if "copied by the script" in l) >= 1,
      "and the master copied out of the work folder is marked too")
check(any("where Siril wrote it" in l for l in lines),
      "naming both ends of that copy, so the two paths cannot be confused")
# The notes are comments, so Siril skips them -- a record that breaks
# the file it claims to be would be worse than no record.
check(all(l.startswith("#") for l in lines if "by the script" in l),
      "every note is a comment line Siril will ignore")
check(ssf.count("requires 1.4.0") == 1 and "A RECORD" in ssf,
      "the header is written once, and says what the file is")
shutil.rmtree(tmp, ignore_errors=True)


print("\n47) the narrowband warning does not invent a target size")
# 1.7.19.  The warning fired on the FILTER and then spoke about the
# TARGET: "on a target this size most of what it removes is your signal".
# The constants block above RBF_NARROWBAND_KEPT says the opposite holds
# for a compact target and that the pixels cannot tell the two apart, so
# the sentence was a claim the script had no way to make.
sub = _cls_method("StackWorker", "_subsky")
check("this size" not in sub,
      "_subsky no longer says anything about the size of the target")
check("_rbf_narrowband_advice(where, fov_arcmin)" in sub,
      "it hands the wording to the helper, with the field it was given")
check("fov_arcmin" in sub.split("def _subsky")[1].split(")")[0]
      or "fov_arcmin: float = 0.0" in sub,
      "and the field of view is a parameter, not a guess inside")
# Both callers have a path on disk at that moment, so both can read it --
# and neither may pay for the read when the image is not narrowband.
for meth, where in (("_bg_extract_master", "master"),
                    ("_finish_composite", "composite")):
    body_src = _cls_method("StackWorker", meth)
    check("_frame_fov_arcmin(path) if nb else 0.0" in body_src,
          f"{meth} reads the field from the file, and only when narrowband")
# The measured figures keep the condition they were measured under, and
# the helper is the only place that wording lives.
adv = _fn_src("_rbf_narrowband_advice")
check("95%" in adv and "COMPACT" in adv,
      "the helper carries both the 95%-fill measurement and the other case")
check("RBF_NARROWBAND_KEPT" in adv and "POLY1_NARROWBAND_KEPT" in adv,
      "and quotes the constants rather than repeating their numbers")
check("POLY1_NARROWBAND_KEPT:.1%" in adv,
      "99.9% is printed as 99.9%, not rounded up to 100%")

print("\n48) the results folder goes where the menu says")
# 1.7.20.  Every path the run and the finish dialog use comes from the one
# level the user chose; nothing may rebuild "<root>/output" on its own.
ui_cls = next(k for k in tree.body if isinstance(k, ast.ClassDef)
              and any(isinstance(f, ast.FunctionDef) and f.name == "_set_root"
                      for f in k.body))
ui = ui_cls.name
starter = next(f.name for f in ui_cls.body if isinstance(f, ast.FunctionDef)
               and "self._run_out_dir = out_dir"
               in (ast.get_source_segment(src, f) or ""))
check("os.path.join(self._root, STACKS_DIRNAME)" not in src,
      "no code path builds the results folder behind the level menu's back")
check("out_dir = self._output_path()" in _cls_method(ui, starter),
      f"{starter} hands the run the path from the menu")
check("_run_out_dir" in _cls_method(ui, "_on_stack_done"),
      "the finish dialog reports the folder the run was given")
check("_skip_in_discovery(dirpath, d)" in _cls_method("AnalyzeWorker", "_scan"),
      "discovery prunes through the one rule, old name included")
check("_looks_like_results(path)" in _cls_method(ui, "_looks_like_our_output"),
      "the picker guard uses the same test as the pruning")
check("self.cmb_out_level" in _cls_method(ui, "_set_left_enabled"),
      "the menu is locked while a run goes")
check('"output_level"' in _cls_method(ui, "_save_settings")
      and '"output_level"' in _cls_method(ui, "_load_settings"),
      "the chosen level is saved and restored")
check("_out_level_pref =" not in _cls_method(ui, "_fill_out_levels"),
      "refilling the menu for a new folder never overwrites the choice")

print("\n49) three things the NGC 7380 run said wrong or not at all")
ui_cls = next(k for k in tree.body if isinstance(k, ast.ClassDef)
              and any(isinstance(f, ast.FunctionDef) and f.name == "_set_root"
                      for f in k.body))
ca = _cls_method("StackWorker", "_calibrate_args")
check("_no_flat_said" in ca and "no flat" in ca,
      "the run names a filter calibrated without a flat, once per filter")
check('self._opts.get("use_flats", True)' in ca.split("_no_flat_said")[0],
      "and stays quiet when flats are switched off on purpose")
check("_filters_without_flats(" in _cls_method(ui_cls.name,
                                              "_show_calib_summary"),
      "the analysis names it before anything is stacked")
fc = _cls_method("StackWorker", "_finish_composite")
check(fc.index("will_resolve = ") < fc.index("plate-solve skipped"),
      "whether a re-solve follows is decided before 'skipped' may be said")
check("elif inherited:" in fc and "if inherited and will_resolve:" in fc,
      "'no new solve was needed' is only written when none follows")
check("if solved and will_resolve:" in fc,
      "the re-solve uses the same decision, so the two cannot disagree")
pm = _cls_method(ui_cls.name, "_apply_palette_mapping")
check("and not missing" in pm.split("will blend")[0].rsplit("elif", 1)[1],
      "HaRGB's 'will blend' needs the palette to be buildable first")

print("\n50) a calibration master is reused only while it fits its frames")
# 1.7.20.  An OIII flat master from 12 frames was reused with 20 flats in
# the folder: reuse asked only whether the file name existed.
sg = body("_stack_calib_group")
check("_calib_master_stale(_frame_record(files), recorded, count)" in sg,
      "the reuse decision compares the frames, not just the name")
check("_read_frame_record(dest)" in sg and "_fits_stackcnt(dest)" in sg,
      "the record decides, STACKCNT stands in for an older master")
check(sg.index("_read_frame_record(dest)") < sg.index("_fits_stackcnt(dest)"),
      "and the header is only read when there is no record")
check("built is None and stale and os.path.exists(dest)" in sg,
      "a failed rebuild falls back to the master it was replacing")
check("Rebuilding master" in sg,
      "a rebuild is said, with the reason")
bm = body("_build_calib_master")
check(bm.count("self._write_frame_record(dest, kind,") == 2,
      "both ways a master comes into being write its record")
check("used.append(src)" in bm and "_write_frame_record(dest, kind, used)" in bm,
      "the record lists the frames actually staged, not the ones offered")

print()
if fails:
    print(f"{len(fails)} FAILURE(S)")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ALL BEHAVIOUR CHECKS PASSED")
