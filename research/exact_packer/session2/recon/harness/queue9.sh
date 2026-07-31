#!/bin/bash
# HEIGHT-MATCHED CONTACT.  The mechanism behind "less full is better", charged directly.
#
# WHAT THE DESCENT RULE RATIONS.  A landing block's layer k is refused by anything resting at a
# layer j >= k in the same column, so at a cell whose current stack height is h, the layer
# indices still usable are exactly k >= h.  Occupancy is not the resource; HEIGHT is.  A
# one-layer resident is nearly free ground for an overhang; a four-layer one sterilises its
# cells against every layer of everything.
#
# That is not a marginal case on this problem.  Measured on the real hidden P3: blocks carry 1
# to 4 layers, and 1,352 of the 1,588 (block, orientation) pairs have an upper layer extending
# past their own layer 0.  Overhangs are the norm.
#
# WHY IT EXPLAINS conw.  Turning candidate contact off is the best P3 setting measured (87,560
# against 96,990) and the worst P4 one (+25.9%).  A block always lands on cells that are
# completely free, so the total sterilised volume it creates is identical wherever it goes --
# position cannot change how much height is added, only where.  What contact gets wrong is not
# that it packs tightly; it is that it does not care WHOM it packs against.  A four-layer block
# pressed against a one-layer block scores exactly as well as against another four-layer one,
# and leaves a height cliff where a broad low plateau could have been.  Overhangs need the
# plateau.  conw=0.0 fixes this by abandoning tightness outright, which is precisely why it
# cannot survive an instance that needs every cell.
#
# hmatch charges the mean |my height - neighbour's height| over the boundary cells that touch
# something.  Walls and free neighbours are skipped -- a wall matches anything, free ground has
# no height to clash with -- so the block still wants to nestle, it merely chooses a neighbour
# of its own height.  Nothing is taken away from an instance that needs tightness.
#
# The engine is installed under this lock, not while a queue is running, and only after a
# deterministic single-beam check confirms hmatch=0.0 reproduces the current engine exactly.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1
EXT="cpython-312-x86_64-linux-gnu.so"
NEW="/tmp/ogc_hmatch.$EXT"
[ -f "$NEW" ] || { echo "new engine not built"; exit 1; }

# ---- identity check: hmatch=0.0 must reproduce the installed engine, beam for beam ----
if [ ! -s results/q9_identity.log ]; then
{
  cp -f "ogc_fast.$EXT" "/tmp/ogc_installed.$EXT"
  for W in installed hmatch; do
      cp -f "/tmp/ogc_${W}.$EXT" "ogc_fast.$EXT"
      python3.12 - "$W" <<'PY'
import json, os, sys, time
sys.path.insert(0, os.getcwd())
import myalg_orig as SC
d = json.load(open("data/hidden/prob_3.json"))
# one beam, one axis, fixed budget: no pool, no bandit, no timing-dependent allocation, so the
# two engines must agree to the digit or the change is not neutral at hmatch=0.
cfg = dict(Bmul=1.0, K=4, pos_lam=0.10, order="defer_big", fut_beta=1.0, prefw=0.0, w3mul=1.0)
t = time.time(); s = SC._beam_once(d, 40.0, cfg); el = time.time() - t
o = SC._total(d, s)[0] if s is not None else float("inf")
print("%-10s single beam obj=%d  in %.1fs" % (sys.argv[1], int(o), el), flush=True)
PY
  done
  cp -f "/tmp/ogc_installed.$EXT" "ogc_fast.$EXT"
} > results/q9_identity.log 2>&1
fi
cat results/q9_identity.log
python3.12 - <<'PY' || { echo "IDENTITY CHECK FAILED -- not installing"; exit 1; }
import re
L = [l for l in open("results/q9_identity.log") if "single beam obj=" in l]
assert len(L) == 2, "identity check did not produce two lines: %r" % L
a, b = (int(re.search(r"obj=(-?\d+)", l).group(1)) for l in L)
assert a == b, "hmatch=0.0 engine returns %d, installed returns %d -- NOT neutral" % (b, a)
print("identity ok: both engines return %d on one deterministic beam" % a)
PY
cp -f "$NEW" "ogc_fast.$EXT"
echo "hmatch engine installed  $(date -u +%H:%M:%S)"

run () {  # module tag outfile
    [ -s "results/$3" ] && return
    echo "=== $3  ($2)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "$1" 3 240 "$2" > "results/$3" 2>&1
    tail -1 "results/$3"
    ( cd .. && git add -f "session2/recon/results/$3" >/dev/null 2>&1 )
}

# The sweep runs on the FASTOBJ base, because that is where the rest of the night lives and a
# lever measured against a base you have already moved past says nothing about whether it
# stacks.  hmatch=0.0 is included as the control on the same engine and the same build, so the
# comparison is not against a remembered number.
for H in 0.0 0.5 2.0 8.0; do
    OGC_DK=0 OGC_FASTOBJ=1 OGC_HMATCH="$H" \
        python3.12 harness/mkbase.py 0.3 "myalg_hm${H/./_}.py" 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
done
python3.12 -c "
import myalg_hm0_0 as A, myalg_hm2_0 as B, myalg_hm8_0 as C, inspect
assert all(a.get('hmatch', 0.0) == 0.0 for a in A._AXES), A._AXES
assert all(a.get('hmatch') == 2.0 for a in B._AXES) and all(a.get('hmatch') == 8.0 for a in C._AXES)
assert all(a.get('conw', 1.0) == 1.0 for a in B._AXES), 'contact must stay at full strength'
assert 'def _fast_obj' in inspect.getsource(B)
print('hmatch arms verified on the fastobj base, contact untouched')" || exit 1

for rep in 1 2; do
    for H in 0.0 0.5 2.0 8.0; do
        run "myalg_hm${H/./_}" "hmatch=$H r$rep" "q9_hm${H}_r${rep}.log"
    done
done
echo "queue9done  $(date -u +%H:%M:%S)"
