#!/bin/bash
# REMOVE THE FOUR CLOSED EXPERIMENTS FROM THE SHIPPED bayrepack.  Idempotent; safe to re-run.
#
# THE FIRST VERSION OF THIS SCRIPT SHIPPED A BROKEN MODULE, and the way it did that is the
# reason the verification at the bottom now looks the way it does.
#
# The BRK_WISH excision was written as "delete everything from the DIRECTED VARIANT comment to
# `wts = []`".  That span does not contain only the wish block -- it also contains cand, isres,
# windows() and blocks_in, roughly 180 lines of the operator's core.  The result parsed, it
# imported, it contained none of the dead names and all of the live ones, and it died on the
# first actual call with `NameError: name 'cand' is not defined`.  repack's caller catches
# Exception and returns None, so brk would have silently done nothing on every instance and P3
# would have drifted back to 96,990 with no error anywhere.  It was committed and pushed.
#
# Every check the old script ran was TRUE of that module.  A NameError in a function body is a
# run-time event; nothing that only reads text can see it.  So this script now ends by CALLING
# repack on a real instance and requiring a solution back.  Text checks catch the wrong thing.
#
# WHAT GOES, with the cut bounded to each construct exactly:
#
#   _wish + its call site   ~90 lines.  A CP-SAT Hamming-ball reassignment that chose the target
#                           bay and outsider set instead of pressure + single-move gain.
#                           Measured and beaten; every current result uses the undirected path.
#   BRK_LINW                Linearised seat weights instead of the leave-one-out delta.  Beaten.
#   BRK_OLDTIER             The budget-ratio tier rule the measured predictor replaced.
#   BRK_TARGET              A bay pin for diagnostics, with no business in a submission.
#
# None is reachable in a shipped path -- each is an env var nothing sets -- so removing them
# cannot change a result.  That is the point: four branches a future bug can hide behind, in the
# one file whose job is to be auditable.
#
# Refuses to run while the experiment lock is held: bayrepack is imported by whatever is
# measuring, and swapping it mid-queue scores later arms on different code than earlier ones.
set -u
cd "$(dirname "$0")/.." || exit 1

exec 9>/tmp/ogc_experiment.lock
if ! flock -n 9; then
    echo "a measurement is running -- refusing to modify bayrepack.py underneath it"
    exit 1
fi

cp bayrepack.py /tmp/bayrepack.before-prune.py

python3.12 - <<'PY' || { echo "prune failed; restoring"; cp /tmp/bayrepack.before-prune.py bayrepack.py; exit 1; }
import sys
s = open("bayrepack.py").read()
before = len(s.splitlines())
if "BRK_WISH" not in s and "BRK_LINW" not in s and "BRK_TARGET" not in s:
    print("already pruned (%d lines)" % before); sys.exit(0)

def cut(text, start, end, repl=""):
    """Delete [start, end) by literal markers, asserting each appears exactly where expected."""
    a = text.index(start)
    b = text.index(end, a)
    return text[:a] + repl + text[b:]

# 1) the _wish function and the comment block above it
i = s.index("def _wish(")
j = s.index("\ndef ", i + 1)
k = s.rindex("\n\n\n", 0, i)
s = s[:k + 1] + s[j + 1:]

# 2) its call site -- from the DIRECTED VARIANT comment to the `if wcands:` that consumes it.
#    The branch itself collapses: `if wcands: ... elif cands:` becomes `if cands:`.
s = cut(s, "        # DIRECTED VARIANT.", "        if wcands:\n")
a = s.index("        if wcands:\n")
b = s.index("        elif cands:\n", a)
s = s[:a] + s[b:].replace("        elif cands:\n", "        if cands:\n", 1)
# the debug line names which path chose the target; only one path is left
s = s.replace('% ("wish" if wcands else "pressure", TGT, len(res), len(outs), msg),',
              '% ("pressure", TGT, len(res), len(outs), msg),')

# 3) BRK_LINW -- the elif below it becomes the if
a = s.index('            if os.environ.get("BRK_LINW") == "1":')
b = s.index("            elif isres[i]:", a)
s = s[:a] + s[b:].replace("            elif isres[i]:", "            if isres[i]:", 1)

# 4) BRK_OLDTIER
s = cut(s, '        elif os.environ.get("BRK_OLDTIER") == "1":', "        else:\n            # DEFERRED.")
# the tier chooser guards on the same knob; with the arm gone only _forced can skip it
s = s.replace('if not _forced and os.environ.get("BRK_OLDTIER") != "1":', 'if not _forced:', 1)

# 5) BRK_TARGET -- the pin goes, the pressure order stays
b = s.index("\n", s.index("if cur[b] == j))))")) + 1
a = s.index("        # BRK_TARGET pins the bay")
s = s[:a] + ("        _order = sorted(range(m), key=lambda j: -(u[j] * sum(wl[b]\n"
             "                        for b in range(n) if cur[b] == j)))\n") + s[b:]

for dead in ("BRK_WISH", "BRK_LINW", "BRK_OLDTIER", "BRK_TARGET", "def _wish", "wcands"):
    assert dead not in s, dead
open("bayrepack.py", "w").write(s)
print("bayrepack.py %d -> %d lines (-%d)" % (before, len(s.splitlines()), before - len(s.splitlines())))
PY

# THE CHECK THAT WOULD HAVE CAUGHT THE LAST FAILURE: run the operator, and run the ORIGINAL
# beside it.  "repack must return a solution" was the wrong bar -- rejecting a repack is normal
# and the unpruned module returns None on this very input (admitted 2, displaced 3, obj 99,385
# against a base of 86,665 -> reject).  What must hold is not success, it is EQUIVALENCE: the
# removed branches are unreachable, so every deterministic decision has to come out the same.
#
# Compared: the target bay, the resident count, the outsider count, the real column count the
# packer built, and whether a solution came back at all.  Between them those cover all four
# removals -- BRK_TARGET picks the bay, BRK_WISH picks the bay AND the outsiders, BRK_OLDTIER
# picks the tier (hence the column count), BRK_LINW changes the seat weights and so the accept
# or reject.  All are fixed before or by the deterministic part of the call.
cp bayrepack.py /tmp/bayrepack.pruned.py
_probe() {   # $1 = module file to test under the name bayrepack
    cp "$1" bayrepack.py
    BRK_DEBUG=1 BRK_STEP=6 BRK_NOUT=10 BRK_NENT=1 timeout 300 python3.12 -c "
import json, sys
sys.path.insert(0, '.')
import myalgorithm as A, bayrepack as R
d = json.load(open('data/hidden/prob_3.json'))
sol = json.load(open('results/p3_incumbent.json'))
sol['operations'] = {int(k): v for k, v in sol['operations'].items()}
out = R.repack(d, sol, 20.0, A._total, A._build_operations, A._ogc_fast_engine, hard=40.0)
print('RESULT', 'solution' if out else 'None')
" 2>&1 | grep -oE "real_ncol=[0-9]+|tgt=[0-9]+ res=[0-9]+ outs=[0-9]+|RESULT (solution|None)"
}
REF="$(_probe /tmp/bayrepack.before-prune.py)"
NEW="$(_probe /tmp/bayrepack.pruned.py)"
if [ "$REF" != "$NEW" ]; then
    echo "EQUIVALENCE FAILED -- restoring the pre-prune file"
    printf 'before: %s\nafter : %s\n' "$REF" "$NEW"
    cp /tmp/bayrepack.before-prune.py bayrepack.py
    exit 1
fi
echo "equivalence check passed, identical on every deterministic decision:"
echo "$NEW" | sed 's/^/    /'
