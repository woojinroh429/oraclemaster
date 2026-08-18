#!/bin/bash
# ANCHOR THE REGROW ON AN EXACT ASSIGNMENT INSTEAD OF ON THE INCUMBENT.
#
# W2BEAM established that the beam's weakness is not the weight on balance.  Told to chase
# balance less it DOES trade Z2 for Z3 -- 2522 -> 3464 and 582 -> 556 on P3 -- but at a bad
# price:
#
#     the beam's trade      Z2 +942  for Z3 -26     36 units of Z2 per unit of Z3
#     the objective's price                         30 units of Z2 per unit of Z3
#     the optimum's trade   Z2 +769  for Z3 -278     2.8 units of Z2 per unit of Z3
#
# Thirteen times worse.  The beam gives up preference on whatever block is in front of it; the
# optimum gives it up only where it pays.  So the missing input is WHICH blocks, not how hard.
#
# _regrow already re-derives a beam from (bay per block, dispatch order) with a decaying
# stay-weight, migrating a block only where migrating lowers the objective.  It is simply always
# handed the incumbent's own assignment by _anchor_of.  OGC_MANCH hands it a CP-SAT optimum
# instead, under per-bay CARDINALITY caps read off the incumbent -- so the target is one the
# geometry has already shown it can hold.  On P3 at the incumbent's own counts that optimum is
# 59,715 (Z2 3903, Z3 268) against our 97,570 (Z2 3134, Z3 546).
#
# Cardinality rather than area on purpose: area was measured worthless here (first-choice demand
# over capacity is 0.48 / 0.12 / 0.15, so the row forbids nothing) while cardinality is what the
# packer actually ran out of -- bay 0 saturates at 55-56.
#
# Nothing new is searched and nothing is gated.  It is the existing regrow with a better anchor,
# scored on the true objective like every other operator and discarded when it loses.
#
# NOISE FLOOR, measured today: the same lean configuration gives 96,990 / 97,570 / 99,910 on P3
# -- 2,920 points, 3.0%.  Anything smaller than that is not a result.  Two reps each, and the
# control has to land inside that band or the arm is not what it says it is.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 OGC_MANCH=6.0 python3.12 harness/mkbase.py 0.3 myalg_m.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
OGC_DK=0 OGC_FASTOBJ=1                python3.12 harness/mkbase.py 0.3 myalg_a.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_m as M, myalg_a as A
m, a = inspect.getsource(M), inspect.getsource(A)
assert 'def _master_anchor' in m and '\"manch\"' in m, 'the anchored operator is missing'
assert m.count('_master_anchor(') == 2, 'defined and used exactly once each'
assert 'cardinality' not in a and '_master_anchor' not in a, 'the control must not carry it'
assert 'bayrepack' not in m and 'bayrepack' not in a, 'keep brk out of this comparison'
print('anchored arm and control verified')" || exit 1

run () {  # module tag outfile
    [ -s "results/$3" ] && return
    echo "=== $3  ($2)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "$1" 3 240 "$2" > "results/$3" 2>&1
    tail -1 "results/$3"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$3" >/dev/null 2>&1 \
      && git commit -q -m "manch: $2" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

for rep in 1 2; do
    run myalg_m "manch r$rep" "mn_on_r${rep}.log"
    run myalg_a "ctl   r$rep" "mn_off_r${rep}.log"
done
echo "manch done  $(date -u +%H:%M:%S)"
