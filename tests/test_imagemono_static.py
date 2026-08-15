"""Static sweeps over Svenesis ImageMono Train.

Defect classes that are cheap to check and expensive to find by hand:
forgotten f-strings, duplicate dict keys, unreachable code, dead handlers,
shadowing, mutation while iterating, unquoted paths in Siril commands, and
the settings round-trip.

Run:  python3 tests/test_imagemono_static.py
"""
import ast
import builtins
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "Svenesis-ImageMono-Train.py")
src = open(SRC).read()
tree = ast.parse(src)
lines = src.splitlines()

fails = []


def check(ok, msg, detail=""):
    print(("   ok   " if ok else "   FAIL ") + msg + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(msg)


print("1) it compiles")
compile(src, SRC, "exec")
check(True, f"{len(lines)} lines parse")

print("\n2) plain strings that look like forgotten f-strings")
hits = [(n.lineno, n.value[:60]) for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and re.search(r"\{[A-Za-z_][A-Za-z_0-9.\[\]'\"()]*\}", n.value)
        and "{{" not in n.value]
check(not hits, "no string interpolates without an f prefix", str(hits[:3]))

print("\n3) duplicate keys in dict literals")
dups = []
for n in ast.walk(tree):
    if isinstance(n, ast.Dict):
        keys = [k.value for k in n.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)]
        dups += [(n.lineno, k) for k in set(keys) if keys.count(k) > 1]
check(not dups, "no dict literal repeats a key", str(dups[:3]))

print("\n4) mutable default arguments")
bad = [(f.lineno, f.name) for f in ast.walk(tree)
       if isinstance(f, ast.FunctionDef)
       for d in f.args.defaults + [x for x in f.args.kw_defaults if x]
       if isinstance(d, (ast.List, ast.Dict, ast.Set))]
check(not bad, "no function carries a mutable default", str(bad))

print("\n5) unreachable statements after return / raise / continue / break")
dead = []
for node in ast.walk(tree):
    for attr in ("body", "orelse", "finalbody"):
        body = getattr(node, attr, None)
        if not isinstance(body, list):
            continue
        for i, stmt in enumerate(body[:-1]):
            if isinstance(stmt, (ast.Return, ast.Raise, ast.Continue,
                                 ast.Break)):
                dead.append((body[i + 1].lineno,
                             type(stmt).__name__.lower()))
check(not dead, "nothing follows an unconditional exit", str(dead[:3]))

print("\n6) except clauses shadowed by a broader one before them")
RANK = {"Exception": 0, "OSError": 1, "ValueError": 1, "TypeError": 1,
        "AttributeError": 1, "RuntimeError": 1, "IndexError": 1,
        "KeyError": 1, "NotImplementedError": 2, "FileNotFoundError": 2}
shadowed = []
for t in ast.walk(tree):
    if not isinstance(t, ast.Try):
        continue
    seen = None
    for h in t.handlers:
        names = ([h.type.id] if isinstance(h.type, ast.Name)
                 else [e.id for e in getattr(h.type, "elts", [])
                       if isinstance(e, ast.Name)])
        ranks = [RANK[x] for x in names if x in RANK]
        if not ranks:
            continue
        rank = min(ranks)
        if seen is not None and seen < rank:
            shadowed.append((h.lineno, names))
        seen = rank if seen is None else min(seen, rank)
check(not shadowed, "narrow handlers come before broad ones",
      str(shadowed[:3]))

print("\n7) float equality, shadowed builtins, mutation while iterating")
feq = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Compare)
       for op, c in zip(n.ops, n.comparators)
       if isinstance(op, (ast.Eq, ast.NotEq))
       and isinstance(c, ast.Constant) and isinstance(c.value, float)]
check(not feq, "no float compared with == / !=", str(feq))

RISKY = {"list", "dict", "set", "str", "int", "float", "type", "filter",
         "map", "next", "id", "min", "max", "sum", "sorted", "len",
         "format", "open", "range"} & set(dir(builtins))
shadow = [(n.lineno, t.id) for f in ast.walk(tree)
          if isinstance(f, ast.FunctionDef)
          for n in ast.walk(f) if isinstance(n, ast.Assign)
          for t in n.targets if isinstance(t, ast.Name) and t.id in RISKY]
check(not shadow, "no local shadows a builtin we use", str(shadow[:3]))

mutated = []
for loop in ast.walk(tree):
    if not isinstance(loop, ast.For):
        continue
    it = (ast.get_source_segment(src, loop.iter) or "").strip()
    if not it or "(" in it:
        continue
    for n in ast.walk(loop):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr in ("append", "pop", "remove", "add",
                                    "clear", "update", "setdefault"):
            if (ast.get_source_segment(src, n.func.value) or "").strip() == it:
                mutated.append((n.lineno, it))
check(not mutated, "no container is mutated while iterated", str(mutated[:3]))

print("\n8) duplicate definitions (the later one silently wins)")
redef = []
for scope in [tree] + [n for n in tree.body if isinstance(n, ast.ClassDef)]:
    seen = {}
    for n in scope.body:
        if isinstance(n, ast.FunctionDef):
            if n.name in seen:
                redef.append((n.lineno, n.name))
            seen[n.name] = n.lineno
check(not redef, "no function or method is defined twice", str(redef))

print("\n9) every Siril command argument that carries a path is quoted")
suspect = []
for n in ast.walk(tree):
    if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "_cmd"):
        continue
    for a in n.args[1:]:
        seg = ast.get_source_segment(src, a) or ""
        if any(t in seg for t in ("dir", "path", "_out", "os.path.join",
                                  "library")) and '"' not in seg:
            suspect.append((n.lineno, seg[:50]))
check(not suspect, "no unquoted path reaches Siril", str(suspect[:3]))

print("\n9b) a Siril argument that embeds a path is quoted WHOLE")
# The quotes go around the entire argument, flag included:
#   "-flat=/path with a space/x.fit"   not   -flat="..."
# A folder like "Eagle Nebula" otherwise splits the argument and Siril
# reports the truncated path as not found.  These are built in helper
# functions and splatted into _cmd, so the call-site check above cannot
# see them.
PATH_FLAGS = ("flat", "dark", "bias", "lum", "disto")
unquoted = []
for n in ast.walk(tree):
    if not isinstance(n, ast.JoinedStr):
        continue
    seg = (ast.get_source_segment(src, n) or "").strip()
    # Only whole arguments, not prose that happens to mention a flag.
    m = re.match(r"""^f(['"])"?-(%s)=""" % "|".join(PATH_FLAGS), seg)
    if not m:
        continue
    if "rel(" in seg:
        # `rgbcomp` does not honour quoting at all; _rgbcomp cd's into the
        # masters folder and passes relative, space-free names instead.
        continue
    if not seg.startswith(('f\'"-', 'f""-')):
        unquoted.append((n.lineno, seg[:60]))
check(not unquoted, "every path-carrying Siril flag is quoted whole",
      str(unquoted))

print("\n10) the settings round-trip is symmetric")


def _keys(fn, pat):
    node = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == fn)
    return set(re.findall(pat, ast.get_source_segment(src, node)))


save = _keys("_save_settings", r'st\.setValue\("(\w+)"')
load = _keys("_load_settings", r'st\.value\("(\w+)"')
print(f"   {len(save)} saved, {len(load)} loaded")
check(save == load, "every saved setting is loaded and vice versa",
      f"only saved={sorted(save - load)} only loaded={sorted(load - save)}")

widgets = _keys("_all_setting_widgets", r'"(\w+)":')
presets = _keys("_preset_widgets", r'"(\w+)":')
check((widgets | presets) <= save,
      "every widget in the settings maps is persisted",
      str(sorted((widgets | presets) - save)))

print("\n11) every preset-mapped key is one the presets actually define")
P = next(ast.literal_eval(n.value) for n in tree.body
         if isinstance(n, ast.Assign)
         and getattr(n.targets[0], "id", "") == "PRESETS")
defined = set().union(*[set(d) for d in P.values()])
check(presets == defined,
      "the preset widget map and the presets agree exactly",
      f"map-only={sorted(presets - defined)} "
      f"preset-only={sorted(defined - presets)}")
check(all(set(d) == defined for d in P.values()),
      f"all {len(P)} presets define the same {len(defined)} keys")

print("\n12) every option read by the worker is one the UI builds")
built = _keys("_current_opts", r'"(\w+)"\s*:')
read = {n.args[0].value for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "get" and n.args
        and isinstance(n.args[0], ast.Constant)
        and isinstance(n.func.value, ast.Attribute)
        and n.func.value.attr == "_opts"}
check(read <= built, "no option is read that nothing builds",
      str(sorted(read - built)))

print("\n13) the over-long-line count does not grow")
# A ratchet, not a clean-slate rule.  The file carries 57 lines over 79
# characters from before this was measured -- 19 of them one packed CSS
# stylesheet, the rest strings that overrun by a handful.  Rewrapping them
# all would be churn; letting new ones in would not.  Lower the ceiling
# when you clean some up; never raise it.
LONG_LINE_CEILING = 57
long = [(i + 1, len(ln)) for i, ln in enumerate(lines) if len(ln) > 79]
print(f"   {len(long)} lines over 79 (ceiling {LONG_LINE_CEILING}, "
      f"longest {max([w for _n, w in long], default=0)})")
check(len(long) <= LONG_LINE_CEILING,
      "no new over-long line was added",
      f"now {len(long)}: {[n for n, _ in long[:5]]}")

print()
if fails:
    print(f"{len(fails)} FAILURE(S)")
    sys.exit(1)
print("ALL STATIC CHECKS PASSED")
