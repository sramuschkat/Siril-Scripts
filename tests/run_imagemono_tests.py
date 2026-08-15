"""Run every Svenesis ImageMono Train check and report the total.

    python3 tests/run_imagemono_tests.py

Each suite is a standalone script and can be run on its own; this only
runs them in order and sums the result.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUITES = ("test_imagemono_static.py",       # AST sweeps, settings symmetry
          "test_imagemono_helpers.py",      # pure helpers on hostile input
          "test_imagemono_behaviour.py",    # the run, on a stubbed Siril
          "test_imagemono_docs.py",         # version + four documents
          "test_imagemono_flat_offset.py")  # per-filter flat offset

failed = []
for name in SUITES:
    proc = subprocess.run([sys.executable, os.path.join(HERE, name)],
                          capture_output=True, text=True)
    oks = proc.stdout.count("   ok   ")
    print(f"{'PASS' if proc.returncode == 0 else 'FAIL'}  {name:34s} "
          f"{oks:3d} checks")
    if proc.returncode != 0:
        failed.append(name)
        print(proc.stdout[-1500:])
        print(proc.stderr[-800:])

print()
if failed:
    print(f"{len(failed)} of {len(SUITES)} suites FAILED: "
          + ", ".join(failed))
    sys.exit(1)
print(f"all {len(SUITES)} suites passed")
