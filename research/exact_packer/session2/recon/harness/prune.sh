#!/bin/bash
# REMOVE THE FOUR CLOSED EXPERIMENTS FROM THE SHIPPED bayrepack.  Idempotent; safe to re-run.
#
# This exists as a committed script rather than as an edit I make by hand, because today an edit
# that lived only on disk was reverted twice -- once by a keepalive hook, once by my own
# `git checkout` when a queue turned out to be using the file.  A script in git cannot be lost
# by either, and re-applying it is one command instead of a reconstruction from memory.
#
# WHAT GOES, and why each is dead rather than merely unused:
#
#   _wish + BRK_WISH   70 lines.  A CP-SAT Hamming-ball reassignment that chose the target bay
#                      and the outsider set instead of pressure + single-move gain.  Measured
#                      and beaten; the undirected operator is what every current result uses.
#   BRK_LINW           Linearised seat weights instead of the leave-one-out objective delta.
#                      Measured and beaten.
#   BRK_OLDTIER        The budget-ratio tier rule the measured predictor replaced.  Kept once so
#                      the two could be scored inside a single queue; that comparison is done.
#   BRK_TARGET         Pins the bay so a diagnostic can sweep all of them.  A harness knob that
#                      has no business in a submission.
#
# None of them is reachable in any shipped path -- every one is an env var nothing sets -- so
# removing them cannot change a result.  That is exactly why it is worth doing: they are four
# branches a future bug can hide behind, in a file whose whole job is to be auditable.
#
# SAFETY.  Refuses to run while the experiment lock is held, because bayrepack is imported by
# whatever is measuring and swapping it mid-queue means the later arms are scored on different
# code than the earlier ones.  That is the mistake this guard exists to prevent.
set -u
cd "$(dirname "$0")/.." || exit 1

exec 9>/tmp/ogc_experiment.lock
if ! flock -n 9; then
    echo "a measurement is running -- refusing to modify bayrepack.py underneath it"
    exit 1
fi

python3.12 - <<'PY' || exit 1
import sys
s = open("bayrepack.py").read()
before = len(s.splitlines())
if "BRK_WISH" not in s and "BRK_LINW" not in s and "BRK_TARGET" not in s:
    print("already pruned (%d lines)" % before); sys.exit(0)

# 1) the _wish function, with the comment block above it
i = s.index("def _wish(")
j = s.index("\ndef ", i + 1)
k = s.rindex("\n\n\n", 0, i)
s = s[:k + 1] + s[j + 1:]

# 2) its call site
a = s.index("        # DIRECTED VARIANT.")
b = s.index("        wts = []", a)
s = s[:a] + s[b:]

# 3) BRK_LINW -- the elif below it becomes the if
a = s.index('            if os.environ.get("BRK_LINW") == "1":')
b = s.index("            elif isres[i]:", a)
s = s[:a] + s[b:].replace("            elif isres[i]:", "            if isres[i]:", 1)

# 4) BRK_OLDTIER
a = s.index('        elif os.environ.get("BRK_OLDTIER") == "1":')
b = s.index("        else:\n            # DEFERRED.", a)
s = s[:a] + s[b:]

# 5) BRK_TARGET -- the pin disappears, the pressure order stays
a = s.index('        # BRK_TARGET pins the bay')
b = s.index("\n", s.index("if cur[b] == j))))", a)) + 1
s = s[:a] + ("        _order = sorted(range(m), key=lambda j: -(u[j] * sum(wl[b]\n"
             "                        for b in range(n) if cur[b] == j)))\n") + s[b:]

open("bayrepack.py", "w").write(s)
print("bayrepack.py %d -> %d lines (-%d)" % (before, len(s.splitlines()), before - len(s.splitlines())))
PY

python3.12 -c "
import ast, importlib, sys
src = open('bayrepack.py').read()
ast.parse(src)
for dead in ('BRK_WISH', 'BRK_LINW', 'BRK_OLDTIER', 'BRK_TARGET', 'def _wish'):
    assert dead not in src, dead
# the three fixes that matter must all still be there
for live in ('_ask = max(_MINASK, _cap)', 'def _ne_of(_frac)', 'int(r[9]) == 1',
             '_TIERS = [(4, 40, 1.0)'):
    assert live in src, live
sys.path.insert(0, '.')
importlib.import_module('bayrepack')
print('pruned module parses, imports, keeps every live fix, and carries no dead branch')" || exit 1
