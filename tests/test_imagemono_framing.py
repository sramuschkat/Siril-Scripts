"""_reg_frame_sizes / _check_framing EXECUTED on real FITS files.

`-framing=min` is accepted by Siril on the astrometric (plate-solve)
registration path and then not applied: the exported frames come back
in differing sizes, `stack` says "Forcing to maximize framing", and the
master ends up LARGER than any sub -- the union, with the ragged edges
the crop exists to remove.  Nothing raises, so only the frames
themselves can tell the run what happened.  The sizes below are the
ones an NGC 6946 run really produced.

Run:  python3 tests/test_imagemono_framing.py
"""
import ast
import math
import os
import re
import sys
import tempfile
import types
import numpy as np
from astropy.io import fits

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "Svenesis-ImageMono-Train.py")
src = open(SRC, encoding="utf-8").read()
tree = ast.parse(src)

def fn(name):
    return ast.get_source_segment(src, next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name))

def meth(cls_name, name):
    k = next(n for n in tree.body
             if isinstance(n, ast.ClassDef) and n.name == cls_name)
    return ast.get_source_segment(src, next(
        m for m in k.body if isinstance(m, ast.FunctionDef) and m.name == name))

ns = {"os": os, "re": re, "np": np, "fits": fits, "math": math,
      "_log_swallowed": lambda exc: None,
      "LogColor": types.SimpleNamespace(BLUE=0, GREEN=1, SALMON=2, RED=3)}
code = "from __future__ import annotations\n" + fn("_read_header")
for m in ("_reg_frame_sizes", "_check_framing"):
    code += "\n" + meth("StackWorker", m)
exec(code, ns)

class W:
    _ext = ".fit"
    _reg_frame_sizes = ns["_reg_frame_sizes"]
    _check_framing = ns["_check_framing"]
    def __init__(self):
        self._reg_degraded = {}
        self._reg_degraded_why = {}
        self.said = []
    def _emit(self, msg, color=None):
        self.said.append(msg)

d = tempfile.mkdtemp()
def write(seq, idx, w, h):
    p = os.path.join(d, f"{seq}_{idx:05d}.fit")
    fits.PrimaryHDU(np.zeros((h, w), np.float32)).writeto(p, overwrite=True)
    return p

ok = True
def check(label, cond, extra=""):
    """Same output shape the other suites use, so the runner can count."""
    global ok
    ok &= bool(cond)
    print(("   ok   " if cond else "   FAIL ") + label
          + (f"  {extra}" if extra and not cond else ""))

# --- the case the NGC 6946 run showed: astrometric path, sizes drift -----
for i, (w, h) in enumerate(
        [(3011, 3010), (3012, 3009), (3008, 3011), (3013, 3014)], 1):
    write("r_merged_BLUE", i, w, h)
w = W()
w._check_framing("BLUE", d, "r_merged_BLUE")
check("differing sizes are detected", w._reg_degraded == {"BLUE": ["-framing=min"]},
      str(w._reg_degraded))
check("...with the 'accepted but not applied' reason, not the refusal",
      "accepted the argument" in w._reg_degraded_why.get("BLUE", ""))
check("...and the log names the plate-solve path as the cause",
      any("plate-solve registration path" in m for m in w.said))
# It stops at the FIRST disagreement, so it quotes the two sizes that
# proved the point and marks the rest with an ellipsis -- reading all 190
# frames to list sizes nobody acts on would be the wasteful answer.
check("...and quotes the two sizes that proved it, with an ellipsis",
      any("3011×3010, 3012×3009…" in m for m in w.said), w.said[:1])

# --- the case -framing=min really worked: one canvas ---------------------
d2 = tempfile.mkdtemp()
for i in range(1, 6):
    p = os.path.join(d2, f"r_masters_{i:05d}.fit")
    fits.PrimaryHDU(np.zeros((3045, 3038), np.float32)).writeto(p, overwrite=True)
w2 = W()
w2._check_framing("LUMINOS", d2, "r_masters")
check("one common size stays silent", w2._reg_degraded == {} and not w2.said)

# --- a refusal already recorded is not overwritten -----------------------
w3 = W()
w3._reg_degraded["BLUE"] = ["-framing=min", "-filter-wfwhm=90%"]
w3._check_framing("BLUE", d, "r_merged_BLUE")
check("an already-degraded channel keeps its own (more specific) story",
      w3._reg_degraded["BLUE"] == ["-framing=min", "-filter-wfwhm=90%"]
      and "BLUE" not in w3._reg_degraded_why and not w3.said)

# --- degenerate input ----------------------------------------------------
w4 = W()
w4._check_framing("X", os.path.join(d, "nope"), "r_x")
check("an unreadable directory is 'cannot tell', not a warning",
      w4._reg_degraded == {} and not w4.said)
w5 = W()
w5._check_framing("X", d, "r_something_else")
check("a sequence with no frames says nothing",
      w5._reg_degraded == {} and not w5.said)

# --- it stops early on the first disagreement ---------------------------
sizes = W()._reg_frame_sizes.__get__(W())(d, "r_merged_BLUE")
check("exactly two sizes are reported, then it stops", len(sizes) == 2, str(sizes))

print()
if not ok:
    print("FAILURES")
    sys.exit(1)
print("ALL FRAMING CHECKS PASSED")
